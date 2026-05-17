"""Meeting REST router — POST/GET list/GET id/DELETE four-piece set.

Per spec (slice-03-meeting-crud):
- Every endpoint scopes by the gateway-injected `X-User-Id` header.
- Cross-user reads / deletes return 404 with no existence leak.
- POST is create-only this slice (no PATCH).

Slice-11 adds two more endpoints under the same prefix:
- POST `/{meeting_id}/rerun_asr` — spawn the re-run background task
- GET  `/{meeting_id}/rerun_asr_status` — polling-friendly progress shape

The router takes its DB session via `get_session_dependency` so tests can
override it to point at the test DB.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from meeting_playbook.asr.factory import get_asr_providers_for_meeting
from meeting_playbook.calendar.client import (
    CalendarClient,
    CalendarEventNotFound,
    CalendarNetworkError,
    CalendarNotConnected,
    CalendarTokenExpired,
)
from meeting_playbook.calendar.dependencies import (
    get_calendar_client_dependency,
    get_playbook_generator_dependency,
)
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_session_factory_dependency,
    get_user_email_dependency,
    get_user_id_dependency,
    get_user_name_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.meetings.schemas import (
    MeetingCreate,
    MeetingDetailRead,
    MeetingPatch,
    MeetingRead,
    RecordingSummary,
)
from meeting_playbook.playbook_generation.generator import (
    PlaybookGenerationFailed,
    PlaybookGenerationTimeout,
    PlaybookGenerator,
)
from meeting_playbook.playbooks.repository import PlaybookRepository
from meeting_playbook.rerun import runtime as rerun_runtime
from meeting_playbook.sessions.models import Recording

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def _calendar_error_to_http(exc: Exception) -> HTTPException:
    """Slice-20b: shared calendar-domain → HTTP envelope mapper for the
    meeting create endpoint.

    Mirrors `calendar.router._calendar_error_to_http` so the create endpoint
    surfaces the same error codes the frontend already knows how to render.
    Duplicated rather than imported because importing the calendar router's
    private helper would couple two routers together at the module level —
    cheaper to keep the mapping local and let the i18n contract enforce
    the shared error_code namespace.
    """
    if isinstance(exc, CalendarNotConnected):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "calendar.not_connected",
                "message": "User has not granted Google Calendar scope.",
            },
        )
    if isinstance(exc, CalendarTokenExpired):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "calendar.token_expired",
                "message": "Stored Calendar token is no longer valid.",
            },
        )
    if isinstance(exc, CalendarEventNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "calendar.event_not_found",
                "message": "Calendar event not found.",
            },
        )
    if isinstance(exc, CalendarNetworkError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "calendar.network_error",
                "message": "Could not reach the Google Calendar API.",
            },
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "common.internal_error",
            "message": "Unexpected calendar-domain error.",
        },
    )


def _generator_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, PlaybookGenerationTimeout):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error_code": "playbook.generation_timeout",
                "message": "Playbook generation exceeded the deadline.",
            },
        )
    if isinstance(exc, PlaybookGenerationFailed):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "playbook.generation_failed",
                "message": "Playbook generation produced an invalid response.",
            },
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "common.internal_error",
            "message": "Unexpected generator error.",
        },
    )


async def _validate_attachments_attachable(
    session: AsyncSession, *, user_id: str, attachment_ids: list[str]
) -> None:
    """Slice-20b: enforce ownership + meeting_id IS NULL before meeting create.

    Per spec `POST /api/meetings accepts an attachments list...`: every id
    MUST reference an attachment owned by the authenticated user AND with
    `meeting_id IS NULL`. Any failure aborts BEFORE the meeting row is
    written so the user does not end up with a half-attached meeting.

    The attachment table is owned by slice-20a; this helper does a raw SQL
    lookup so the meetings router does not need an attachment ORM model
    to land. If S20a has not deployed the table yet, the query raises
    `sqlalchemy.exc.ProgrammingError` — the caller surfaces that as a 500,
    which is the correct signal that the slice dependency is missing in
    deployment.
    """
    if not attachment_ids:
        return
    rows = await session.execute(
        text(
            """
            SELECT id, user_id, meeting_id
              FROM attachment
             WHERE id = ANY(:ids)
            """
        ),
        {"ids": attachment_ids},
    )
    found = {r.id: r for r in rows}
    for aid in attachment_ids:
        rec = found.get(aid)
        if rec is None or rec.user_id != user_id or rec.meeting_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "attachment.not_attachable",
                    "message": (
                        "One or more attachment ids are not owned by the "
                        "current user or are already attached to another meeting."
                    ),
                },
            )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MeetingRead)
async def create_meeting(
    body: MeetingCreate,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    user_name: Annotated[str, Depends(get_user_name_dependency)],
    user_email: Annotated[str, Depends(get_user_email_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    calendar: Annotated[CalendarClient, Depends(get_calendar_client_dependency)],
    generator: Annotated[PlaybookGenerator, Depends(get_playbook_generator_dependency)],
) -> MeetingRead:
    """Slice-20b: single create entry point for manual + calendar import paths.

    Order of operations per spec:
    (1) Pydantic validates request body.
    (2) If `attachments[]` non-empty → ownership + `meeting_id IS NULL`
        validation BEFORE meeting create (per spec
        `POST /api/meetings accepts an attachments list...`). Failure
        surfaces `attachment.not_attachable` 422 and no meeting is written.
    (3) If `calendar_event_id` non-null → fetch event detail. Calendar
        fetch failure surfaces the calendar error code and no meeting is
        written (matches design `Playbook 生成觸發點下移`).
    (4) Create meeting row (carries calendar_event_id when set).
    (5) Write back attachment.meeting_id for each id.
    (6) If `calendar_event_id` non-null → run generator + upsert playbook.
        Generator failure surfaces `playbook.generation_timeout` /
        `playbook.generation_failed` AFTER the meeting + attachment rows
        are committed (matches slice-05 semantics — meeting is recoverable).
    """
    # (2) Attachment validation BEFORE any DB write (per spec).
    await _validate_attachments_attachable(
        session,
        user_id=user_id,
        attachment_ids=body.attachments,
    )

    # (3) Calendar fetch BEFORE meeting create (so calendar errors do not
    # leave an orphan meeting). Captured event is reused at step (6).
    calendar_event = None
    if body.calendar_event_id is not None:
        try:
            calendar_event = await calendar.get_event(user_id, body.calendar_event_id)
        except (
            CalendarNotConnected,
            CalendarTokenExpired,
            CalendarEventNotFound,
            CalendarNetworkError,
        ) as exc:
            raise _calendar_error_to_http(exc) from exc

    # (4) Create the meeting row.
    repo = MeetingRepository(session)
    meeting = await repo.create(
        user_id=user_id,
        title=body.title,
        counterparty_display_name=body.counterparty_display_name,
        me_display_name=body.me_display_name,
        scheduled_start_at=body.scheduled_start_at,
        scheduled_end_at=body.scheduled_end_at,
        calendar_event_id=body.calendar_event_id,
    )

    # (5) Write back attachment.meeting_id. Already validated above so this
    # is a straight UPDATE — re-running the IS NULL filter as a defence in
    # depth against a concurrent attach that snuck in between (2) and here.
    if body.attachments:
        await session.execute(
            text(
                """
                UPDATE attachment
                   SET meeting_id = :mid
                 WHERE id = ANY(:ids)
                   AND user_id = :uid
                   AND meeting_id IS NULL
                """
            ),
            {"mid": meeting.id, "ids": body.attachments, "uid": user_id},
        )
        await session.commit()

    # (6) Generator + playbook upsert (only when calendar_event_id is set).
    if calendar_event is not None:
        try:
            draft = await generator.generate(
                calendar_event,
                viewer_email=user_email,
                viewer_name=user_name,
            )
        except (PlaybookGenerationTimeout, PlaybookGenerationFailed) as exc:
            # Meeting + attachments already committed — per spec the failure
            # MUST leave both persisted so the user can recover through the
            # manual playbook editor.
            raise _generator_error_to_http(exc) from exc
        await PlaybookRepository(session).upsert_for_meeting(meeting.id, draft)

    return MeetingRead.model_validate(meeting)


@router.get("", response_model=list[MeetingRead])
async def list_meetings(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    # Slice-17 — optional tag-AND filter. `?tag_ids=a,b,c` returns meetings
    # that carry every supplied tag id. Validation: any id not owned by the
    # caller raises 422 `tag.unknown_id` (silent drop would hide typos).
    tag_ids: str | None = None,
    # Slice-18 — home-page filter / order / limit. All optional. The
    # `status` query is aliased to the function parameter `meeting_status`
    # so the function body can still reference `fastapi.status` constants
    # without shadowing.
    scheduled_date: Annotated[str | None, Query()] = None,
    meeting_status: Annotated[str | None, Query(alias="status")] = None,
    pending: Annotated[bool, Query()] = False,
    order: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> list[MeetingRead]:
    """List meetings owned by the requesting user.

    Dispatches between the two repository entry points:
    - `tag_ids` present → `list_for_user` (tag-aware, eager-loads tags).
      Other slice-18 filter params are ignored on this path; combining
      tag + scheduled_date / pending / order / limit is intentionally
      not supported in this revision.
    - Slice-18 filters present → `list_by_user` (no tag eager-load).
    - Default (no filters at all) → `list_for_user(user_id)` so every
      list response keeps the slice-17 `tags` array eager-loaded.
    """
    repo = MeetingRepository(session)
    parsed_ids: list[str] = []
    if tag_ids:
        parsed_ids = [t for t in (chunk.strip() for chunk in tag_ids.split(",")) if t]
    has_filters = any(
        [
            scheduled_date is not None,
            meeting_status is not None,
            pending,
            order is not None,
            limit is not None,
        ]
    )
    if parsed_ids:
        from meeting_playbook.tags.models import Tag

        owned_rows = await session.execute(
            select(Tag.id).where(Tag.user_id == user_id, Tag.id.in_(parsed_ids))
        )
        owned_set = {row[0] for row in owned_rows.all()}
        if owned_set != set(parsed_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_code": "tag.unknown_id",
                    "message": "One or more tag_ids do not belong to this user.",
                },
            )
        rows = await repo.list_for_user(user_id, tag_ids=parsed_ids)
    elif has_filters:
        try:
            rows = await repo.list_by_user(
                user_id,
                scheduled_date=scheduled_date,
                status=meeting_status,
                pending=pending,
                order=order,
                limit=limit,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status_code_for_invalid_param(),
                detail={"error_code": "meeting.invalid_query_param", "message": str(e)},
            ) from e
    else:
        # Default path — preserve slice-17 tag eager-loading.
        rows = await repo.list_for_user(user_id)
    return [MeetingRead.model_validate(m) for m in rows]


def status_code_for_invalid_param() -> int:
    """Indirection so the value reads clearly at the call site."""
    return status.HTTP_400_BAD_REQUEST


@router.get("/{meeting_id}", response_model=MeetingDetailRead)
async def get_meeting(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> MeetingDetailRead:
    repo = MeetingRepository(session)
    meeting = await repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        # Hide the missing-vs-other-owner distinction (ownership isolation).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )

    # Slice-11 derived flags + slice-16 recordings list. We pull all
    # recording rows once so the audio player can locate the me-stream
    # WAV without a second round-trip.
    all_recordings = (
        (await session.execute(select(Recording).where(Recording.meeting_id == meeting_id)))
        .scalars()
        .all()
    )
    recordings_available = any(r.deleted_at is None for r in all_recordings)
    rerun_asr_pending = rerun_runtime.is_pending(meeting_id)

    base = MeetingRead.model_validate(meeting).model_dump()
    return MeetingDetailRead(
        **base,
        recordings_available=recordings_available,
        rerun_asr_pending=rerun_asr_pending,
        recordings=[RecordingSummary.model_validate(r) for r in all_recordings],
    )


@router.patch("/{meeting_id}", response_model=MeetingDetailRead)
async def patch_meeting(
    meeting_id: str,
    body: MeetingPatch,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> MeetingDetailRead:
    """Slice-15: partial update of any subset of `title`,
    `scheduled_start_at`, `scheduled_end_at`, `counterparty_display_name`,
    `me_display_name`, and `asr_provider`.

    Returns the same `MeetingDetailRead` shape as GET so the client can
    swap the cache row in place. ASR provider changes do NOT affect any
    live WebSocket session for this meeting (per slice-11 design
    Decision 1). Cross-field validation: when only one of the two
    scheduled timestamps is sent, the router merges the body with the
    persisted row before re-checking `scheduled_end_at >= scheduled_start_at`.
    """
    repo = MeetingRepository(session)
    fields = body.as_update_fields()

    if not fields:
        # No-op body — return current state as a 200 (idempotent).
        meeting = await repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
        if meeting is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
            )
        target = meeting
    else:
        # Cross-field time-range check when only one timestamp is sent —
        # merge body + current row before deciding. The model_validator on
        # `MeetingPatch` only fires when BOTH timestamps appear in the
        # same body.
        if ("scheduled_start_at" in fields and "scheduled_end_at" not in fields) or (
            "scheduled_end_at" in fields and "scheduled_start_at" not in fields
        ):
            current = await repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
            if current is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error_code": "meeting.not_found",
                        "message": "Meeting not found",
                    },
                )
            merged_start = fields.get("scheduled_start_at", current.scheduled_start_at)
            merged_end = fields.get("scheduled_end_at", current.scheduled_end_at)
            if merged_start is not None and merged_end is not None and merged_end < merged_start:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "error_code": "meeting.invalid_time_range",
                        "message": ("scheduled_end_at must be >= scheduled_start_at"),
                    },
                )

        target = await repo.update_for_user(user_id=user_id, meeting_id=meeting_id, fields=fields)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
            )

    # Slice-16: load full recording list so PATCH responses keep the
    # same shape as GET, including the recordings array.
    all_recordings = (
        (await session.execute(select(Recording).where(Recording.meeting_id == meeting_id)))
        .scalars()
        .all()
    )
    recordings_available = any(r.deleted_at is None for r in all_recordings)
    base = MeetingRead.model_validate(target).model_dump()
    return MeetingDetailRead(
        **base,
        recordings_available=recordings_available,
        rerun_asr_pending=rerun_runtime.is_pending(meeting_id),
        recordings=[RecordingSummary.model_validate(r) for r in all_recordings],
    )


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> Response:
    repo = MeetingRepository(session)
    deleted = await repo.delete_for_user(user_id=user_id, meeting_id=meeting_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Slice 11: ASR re-run endpoints ────────────────────────────────


async def _meeting_has_available_recording(session: AsyncSession, meeting_id: str) -> bool:
    """True iff the meeting has at least one recording row whose `deleted_at`
    is NULL AND whose wav file is still on disk.

    The DB check (`deleted_at IS NULL`) is the canonical "still available"
    predicate (per slice-11 design Decision 5); the Path.exists() pass
    catches the rare case where someone manually `rm`-ed the wav between
    last cleanup and now (the cleanup loop will self-heal it on the next
    sweep).
    """
    rows = await session.execute(
        select(Recording).where(
            Recording.meeting_id == meeting_id,
            Recording.deleted_at.is_(None),
        )
    )
    return any(Path(rec.file_path).exists() for rec in rows.scalars())


@router.post("/{meeting_id}/rerun_asr", status_code=status.HTTP_202_ACCEPTED)
async def rerun_asr(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    session_factory: Annotated[async_sessionmaker, Depends(get_session_factory_dependency)],
) -> dict[str, Any]:
    """Spawn a background ASR re-run for this meeting.

    Status code matrix (per spec asr-provider-selection ADDED requirement):
      * 202 + `{status: "pending"}` — task spawned
      * 404 `meeting.not_found`     — non-owner / unknown id
      * 422 `rerun.not_completed`   — meeting status != completed
      * 410 `rerun.recording_expired` — every recording has `deleted_at`
                                       set OR no recording rows exist
      * 409 `rerun.busy`            — task already in-flight
    """
    repo = MeetingRepository(session)
    meeting = await repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )
    if meeting.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "rerun.not_completed",
                "message": "Re-run is only available for completed meetings.",
            },
        )
    if not await _meeting_has_available_recording(session, meeting_id):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error_code": "rerun.recording_expired",
                "message": "All recordings for this meeting have expired.",
            },
        )

    me_provider, counterparty_provider = get_asr_providers_for_meeting(meeting.asr_provider)
    spawned = await rerun_runtime.spawn_rerun_task(
        meeting_id,
        providers={"me": me_provider, "counterparty": counterparty_provider},
        session_factory=session_factory,
    )
    if not spawned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "rerun.busy",
                "message": "A re-run for this meeting is already in progress.",
            },
        )
    return {"status": "pending"}


@router.get("/{meeting_id}/rerun_asr_status")
async def rerun_asr_status(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, Any]:
    """Polling-friendly progress shape for the in-flight re-run task.

    Always returns `{status, chunks_processed, chunks_total}` (status is
    "idle" | "pending" — "failed" is reserved for a future iteration when
    we surface the last terminal outcome).
    """
    repo = MeetingRepository(session)
    meeting = await repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )
    return rerun_runtime.get_status(meeting_id)
