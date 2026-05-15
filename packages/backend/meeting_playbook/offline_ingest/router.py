"""FastAPI router for offline ingest (slice-14).

Exposes the tus 1.0 protocol endpoints under
`/api/meetings/{id}/recordings/offline_upload` plus the progress polling
endpoint `/api/meetings/{id}/offline_ingest_progress`. Per-method
handlers live in `tus_protocol`; this module only wires HTTP routes and
performs auth + meeting-scope checks.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.config import get_settings
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.models import Meeting
from meeting_playbook.offline_ingest import runtime
from meeting_playbook.offline_ingest.tus_protocol import (
    TusSession,
    TusValidationError,
    decode_upload_metadata,
    get_session,
    invoke_completion_handler,
    new_upload_id,
    register_session,
    tus_capability_headers,
    validate_creation_metadata,
)
from meeting_playbook.sessions.models import Recording

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/meetings", tags=["offline-ingest"])


def _error(status_code: int, error_code: str, message: str) -> HTTPException:
    """Build the project-standard `{error_code, message}` envelope."""
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code, "message": message},
    )


@router.options(
    "/{meeting_id}/recordings/offline_upload",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
async def options_offline_upload(
    meeting_id: str,
    _user_id: Annotated[str, Depends(get_user_id_dependency)],
) -> Response:
    """Tus 1.0 OPTIONS — advertise resumable-upload capabilities.

    Per spec the response carries `Tus-Resumable`, `Tus-Version`,
    `Tus-Max-Size`, and `Tus-Extension`. Auth via the gateway-injected
    `X-User-Id` header is required so unauthenticated callers cannot
    discover capabilities anonymously (consistent with every other
    `/api/*` endpoint).
    """
    settings = get_settings()
    headers = tus_capability_headers(settings.offline_upload_max_bytes)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)


async def _verify_banner_conditions(
    *,
    db: AsyncSession,
    meeting_id: str,
    user_id: str,
    now: datetime,
) -> Meeting:
    """Re-check the banner display conditions server-side at POST time.

    The frontend hides the upload entry unless three conditions hold; we
    re-verify them here because the client state may be stale by the time
    the user actually submits (per spec scenario
    `Banner conditions no longer met returns 409`).

    Returns the loaded `Meeting` so the caller can stash it on the session
    without a second round-trip.
    """
    row = (await db.execute(select(Meeting).where(Meeting.id == meeting_id))).scalar_one_or_none()
    if row is None or row.user_id != user_id:
        # 404 for both "no such meeting" and "not your meeting" so we never
        # leak meeting existence across users.
        raise _error(
            status.HTTP_404_NOT_FOUND,
            "offline_ingest.not_found",
            f"Meeting {meeting_id!r} not found.",
        )

    conditions_ok = (
        row.status == "scheduled"
        and row.scheduled_end_at is not None
        and row.scheduled_end_at < now
    )
    if not conditions_ok:
        raise _error(
            status.HTTP_409_CONFLICT,
            "offline_ingest.conditions_not_met",
            "Offline ingest is only allowed when the meeting is still "
            "`scheduled` and its `scheduled_end_at` is already past.",
        )

    existing_recording = (
        await db.execute(select(Recording.id).where(Recording.meeting_id == meeting_id))
    ).scalar_one_or_none()
    if existing_recording is not None:
        raise _error(
            status.HTTP_409_CONFLICT,
            "offline_ingest.conditions_not_met",
            "Meeting already has a recording; offline ingest is not allowed.",
        )

    return row


@router.post(
    "/{meeting_id}/recordings/offline_upload",
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def post_create_upload(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    db: Annotated[AsyncSession, Depends(get_session_dependency)],
    upload_length: Annotated[int | None, Header(alias="Upload-Length")] = None,
    upload_metadata: Annotated[str | None, Header(alias="Upload-Metadata")] = None,
    tus_resumable: Annotated[str | None, Header(alias="Tus-Resumable")] = None,
) -> Response:
    """Tus 1.0 POST creation — open a new resumable upload session.

    Per spec, on success returns 201 + `Location: <upload session URL>`.
    Returns the four rejection paths (`too_large`, `unsupported_format`,
    `invalid_started_at`, `conditions_not_met`) before any disk write so a
    rejected request never leaks staging files.
    """
    if upload_length is None:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "offline_ingest.missing_upload_length",
            "Tus POST creation requires the `Upload-Length` header.",
        )
    if upload_length < 0:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "offline_ingest.invalid_upload_length",
            "Upload-Length must be a non-negative integer.",
        )

    metadata = decode_upload_metadata(upload_metadata or "")

    settings = get_settings()
    now = datetime.now(UTC)
    try:
        actual_started_at = validate_creation_metadata(
            upload_length=upload_length,
            metadata=metadata,
            max_bytes=settings.offline_upload_max_bytes,
            now=now,
        )
    except TusValidationError as exc:
        raise _error(exc.status_code, exc.error_code, exc.message) from exc

    await _verify_banner_conditions(db=db, meeting_id=meeting_id, user_id=user_id, now=now)

    upload_dir = Path(settings.offline_upload_dir).expanduser()
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_id = new_upload_id()
    staging_path = upload_dir / f"{upload_id}.partial"

    session = TusSession(
        upload_id=upload_id,
        meeting_id=meeting_id,
        user_id=user_id,
        upload_length=upload_length,
        current_offset=0,
        metadata=metadata,
        staging_path=staging_path,
        actual_started_at=actual_started_at,
    )
    register_session(session)

    location = f"/api/meetings/{meeting_id}/recordings/offline_upload/{upload_id}"
    logger.info(
        "tus_session_created",
        extra={
            "meeting_id": meeting_id,
            "user_id": user_id,
            "upload_id": upload_id,
            "upload_length": upload_length,
        },
    )
    return Response(
        status_code=status.HTTP_201_CREATED,
        headers={
            "Tus-Resumable": "1.0.0",
            "Location": location,
        },
    )


def _tus_404(message: str) -> Response:
    """HEAD/PATCH 404 responses MUST still carry `Tus-Resumable` so the
    tus-js-client can distinguish a missing-session 404 from a non-tus
    server returning HTML. Body intentionally empty (HEAD requests).
    """
    return Response(
        status_code=status.HTTP_404_NOT_FOUND,
        headers={"Tus-Resumable": "1.0.0"},
        content=message,
        media_type="text/plain",
    )


@router.head(
    "/{meeting_id}/recordings/offline_upload/{upload_id}",
    include_in_schema=False,
)
async def head_offline_upload(
    meeting_id: str,
    upload_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
) -> Response:
    """Tus 1.0 HEAD — return the current `Upload-Offset` for a session.

    Per spec: response carries `Upload-Offset`, `Upload-Length`, and
    `Tus-Resumable`. The session must belong to the calling user and the
    meeting in the path (defense against an attacker guessing an
    `upload_id` belonging to someone else).
    """
    session = get_session(upload_id)
    if session is None or session.user_id != user_id or session.meeting_id != meeting_id:
        return _tus_404(f"Upload session {upload_id!r} not found.")

    return Response(
        status_code=status.HTTP_200_OK,
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": str(session.current_offset),
            "Upload-Length": str(session.upload_length),
            "Cache-Control": "no-store",
        },
    )


@router.patch(
    "/{meeting_id}/recordings/offline_upload/{upload_id}",
    include_in_schema=False,
)
async def patch_offline_upload(
    request: Request,
    meeting_id: str,
    upload_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    upload_offset: Annotated[int | None, Header(alias="Upload-Offset")] = None,
    content_type: Annotated[str | None, Header(alias="Content-Type")] = None,
) -> Response:
    """Tus 1.0 PATCH — append `Content-Length` bytes at `Upload-Offset`.

    Per spec:
    - mismatched `Upload-Offset` vs server's `current_offset` → 409 and
      the staging file MUST NOT be truncated
    - successful append → 204 with the new `Upload-Offset` header
    - completion (`current_offset == upload_length`) → invoke the
      pipeline completion hook before responding
    """
    session = get_session(upload_id)
    if session is None or session.user_id != user_id or session.meeting_id != meeting_id:
        return _tus_404(f"Upload session {upload_id!r} not found.")

    if upload_offset is None:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "offline_ingest.missing_upload_offset",
            "Tus PATCH requires the `Upload-Offset` header.",
        )
    if content_type != "application/offset+octet-stream":
        raise _error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "offline_ingest.unsupported_content_type",
            "Tus PATCH requires Content-Type: application/offset+octet-stream.",
        )

    if upload_offset != session.current_offset:
        # Offset mismatch — leave staging file untouched.
        raise _error(
            status.HTTP_409_CONFLICT,
            "offline_ingest.offset_mismatch",
            f"Upload-Offset {upload_offset} does not match server offset "
            f"{session.current_offset}; resume by HEADing first.",
        )

    body = await request.body()
    if not body:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "offline_ingest.empty_patch",
            "PATCH body must contain at least one byte of payload.",
        )

    new_offset = session.current_offset + len(body)
    if new_offset > session.upload_length:
        raise _error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "offline_ingest.too_large",
            f"Appending {len(body)} bytes would exceed Upload-Length {session.upload_length}.",
        )

    # Append to the staging file. Open in "ab" so we never truncate, even
    # if the file was created by a prior PATCH call.
    session.staging_path.parent.mkdir(parents=True, exist_ok=True)
    with session.staging_path.open("ab") as fh:
        fh.write(body)

    session.current_offset = new_offset

    if session.current_offset == session.upload_length:
        try:
            await invoke_completion_handler(session)
        except Exception:
            logger.exception(
                "offline_ingest_pipeline_failed",
                extra={
                    "meeting_id": meeting_id,
                    "user_id": user_id,
                    "upload_id": upload_id,
                },
            )
            # Pipeline failures surface through the progress endpoint;
            # don't surface inside the PATCH response — the upload itself
            # succeeded.

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": str(session.current_offset),
        },
    )


@router.get("/{meeting_id}/offline_ingest_progress")
async def get_offline_ingest_progress(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    db: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict:
    """Polling-friendly snapshot of the offline-ingest pipeline state.

    Per spec: returns `{state, chunks_processed?, chunks_total?, error_code?}`.
    Access is restricted to the meeting owner; non-owners receive 404 (no
    leak of meeting existence). Unknown meeting ids also return 404.
    """
    meeting = (
        await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    ).scalar_one_or_none()
    if meeting is None or meeting.user_id != user_id:
        raise _error(
            status.HTTP_404_NOT_FOUND,
            "offline_ingest.not_found",
            f"Meeting {meeting_id!r} not found.",
        )

    return runtime.get_state(meeting_id)
