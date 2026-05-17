"""Meeting attachment REST router — slice-20a tasks 3.1 + 3.2 + 3.3.

Four endpoints under `/api/meetings/{meeting_id}/attachments`:

- `GET ""` → list active attachments for the meeting owner.
- `POST ""` → multipart upload. Validates whitelist + quota; persists file
  under `{ATTACHMENT_DIR}/{meeting_id}/{attachment_id}.<ext>`; inserts row.
  On validation failure, staged file is unlinked before responding.
- `DELETE "/{attachment_id}"` → soft-delete row + unlink file (idempotent
  via `missing_ok=True`).
- `GET "/{attachment_id}/download"` → stream file with `Content-Disposition:
  attachment; filename="<original>"`. 410 when the row is active but the
  file is missing from disk (retention cleanup race).

Auth: every endpoint pulls `X-User-Id` via `get_user_id_dependency` and
defers ownership scoping to `AttachmentRepository`.
"""

from __future__ import annotations

import contextlib
import logging
import secrets
import urllib.parse
from pathlib import Path
from typing import Annotated, Any

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.attachments.repository import AttachmentRepository
from meeting_playbook.attachments.validation import (
    AttachmentValidationError,
    canonical_extension,
    validate_upload,
)
from meeting_playbook.config import get_settings
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meetings", tags=["meeting-attachments"])


_KIND_TO_CONTENT_TYPE: dict[str, str] = {
    "image": "application/octet-stream",  # overridden per-file by extension below
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text": "text/plain",
    "markdown": "text/markdown",
}

_IMAGE_EXT_TO_CONTENT_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _attachment_dir() -> Path:
    """Resolve `ATTACHMENT_DIR` to an absolute path with `~` expanded."""
    settings = get_settings()
    return Path(settings.attachment_dir).expanduser().resolve()


def _content_type_for(kind: str, file_path: str) -> str:
    if kind == "image":
        ext = Path(file_path).suffix.lower()
        return _IMAGE_EXT_TO_CONTENT_TYPE.get(ext, "application/octet-stream")
    return _KIND_TO_CONTENT_TYPE.get(kind, "application/octet-stream")


def _http_error(status_code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code, "message": message},
    )


def _serialize(att: Any) -> dict[str, Any]:
    return {
        "id": att.id,
        "kind": att.kind,
        "original_name": att.original_name,
        "bytes": att.bytes,
        "uploaded_at": att.uploaded_at.isoformat(),
    }


async def _assert_meeting_owned(session: AsyncSession, *, meeting_id: str, user_id: str) -> None:
    """Raise 404 when the meeting doesn't exist OR isn't owned by user_id.

    The same error_code is used regardless so the response shape does
    not distinguish "not found" from "not owned" (ownership-isolation
    pattern shared with `/api/meetings/{id}`).
    """
    repo = MeetingRepository(session)
    meeting = await repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _http_error(
            status.HTTP_404_NOT_FOUND,
            "meeting.not_found",
            "Meeting not found",
        )


@router.get("/{meeting_id}/attachments")
async def list_attachments(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, Any]:
    """List active attachments for the meeting owner."""
    await _assert_meeting_owned(session, meeting_id=meeting_id, user_id=user_id)
    repo = AttachmentRepository(session)
    rows = await repo.list_for_meeting(meeting_id=meeting_id, user_id=user_id)
    return {"attachments": [_serialize(a) for a in rows]}


@router.post("/{meeting_id}/attachments")
async def upload_attachment(
    meeting_id: str,
    file: UploadFile,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, Any]:
    """Validate, persist, and return the new attachment row."""
    await _assert_meeting_owned(session, meeting_id=meeting_id, user_id=user_id)

    body = await file.read()
    if len(body) == 0:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "attachment.unsupported_format",
            "Uploaded file is empty.",
        )

    repo = AttachmentRepository(session)
    existing = await repo.list_for_meeting(meeting_id=meeting_id, user_id=user_id)

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    filename = file.filename or ""

    try:
        kind = validate_upload(
            content_type=content_type,
            filename=filename,
            declared_bytes=len(body),
            existing_attachments=existing,
        )
    except AttachmentValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            exc.error_code,
            str(exc),
        ) from exc

    # Generate the attachment id up-front so the on-disk filename matches
    # what the row will carry. token_urlsafe(16) → ~22 chars, URL-safe.
    attachment_id = f"att_{secrets.token_urlsafe(16)}"
    ext = canonical_extension(kind, filename, content_type)
    target_dir = _attachment_dir() / meeting_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{attachment_id}{ext}"

    # Persist file BEFORE inserting the row so a write failure leaves the
    # DB clean. If the row insert then fails we unlink the file (best-effort
    # cleanup so failed uploads don't accumulate).
    try:
        await anyio.to_thread.run_sync(target_path.write_bytes, body)
    except OSError as exc:
        logger.error("attachment write failed: %s", exc)
        raise _http_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "common.internal_error",
            "Failed to persist attachment.",
        ) from exc

    try:
        att = await repo.create(
            attachment_id=attachment_id,
            meeting_id=meeting_id,
            user_id=user_id,
            kind=kind,
            original_name=filename or "attachment",
            file_path=str(target_path),
            bytes_=len(body),
        )
    except Exception:
        with contextlib.suppress(OSError):
            target_path.unlink()
        raise

    return _serialize(att)


@router.delete(
    "/{meeting_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attachment(
    meeting_id: str,
    attachment_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> Response:
    """Soft-delete the row + unlink the file. 404 when not found / not owned."""
    await _assert_meeting_owned(session, meeting_id=meeting_id, user_id=user_id)
    repo = AttachmentRepository(session)
    deleted = await repo.soft_delete(attachment_id=attachment_id, user_id=user_id)
    if deleted is None:
        raise _http_error(
            status.HTTP_404_NOT_FOUND,
            "attachment.not_found",
            "Attachment not found",
        )
    if deleted.meeting_id != meeting_id:
        # Defensive: the attachment exists but belongs to a different meeting.
        # The repository already scoped by user_id; this guards against the
        # rare case where the user owns both meetings but the URL referenced
        # the wrong one.
        raise _http_error(
            status.HTTP_404_NOT_FOUND,
            "attachment.not_found",
            "Attachment not found",
        )
    with contextlib.suppress(OSError):
        Path(deleted.file_path).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{meeting_id}/attachments/{attachment_id}/download")
async def download_attachment(
    meeting_id: str,
    attachment_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> FileResponse:
    """Stream the file with the original filename in Content-Disposition."""
    await _assert_meeting_owned(session, meeting_id=meeting_id, user_id=user_id)
    repo = AttachmentRepository(session)
    att = await repo.get_for_download(attachment_id=attachment_id, user_id=user_id)
    if att is None or att.meeting_id != meeting_id:
        raise _http_error(
            status.HTTP_404_NOT_FOUND,
            "attachment.not_found",
            "Attachment not found",
        )

    path = Path(att.file_path)
    if not path.exists():
        # Row is active but the file has been swept by retention cleanup
        # (or hand-removed). Surface a stable error_code so the UI can
        # display "attachment has expired".
        raise _http_error(
            status.HTTP_410_GONE,
            "attachment.expired",
            "Attachment file has expired and is no longer available.",
        )

    media_type = _content_type_for(att.kind, att.file_path)
    # Content-Disposition: send both forms.
    # - `filename*=UTF-8''<pct>` (RFC 5987) is what modern browsers read; it
    #   survives non-ASCII characters via percent-encoding.
    # - `filename="<ascii-safe>"` is the legacy fallback. Per RFC 6266 /
    #   RFC 2616 it MUST be a quoted-string: `"` and `\` must be
    #   backslash-escaped, control chars (0x00-0x1F, 0x7F) and bare
    #   non-ASCII are not allowed. Non-ASCII gets replaced with `_` so the
    #   fallback stays parseable; the `filename*` form preserves the real
    #   name.
    safe_name = urllib.parse.quote(att.original_name)
    legacy_name = _ascii_safe_quoted_filename(att.original_name)
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=att.original_name,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{legacy_name}\"; filename*=UTF-8''{safe_name}"
            ),
        },
    )


def _ascii_safe_quoted_filename(name: str) -> str:
    """Return `name` sanitized for use inside a Content-Disposition
    `filename="..."` quoted-string per RFC 6266 / RFC 2616.

    Steps:
    1. Replace any non-ASCII or control character with `_` — the legacy
       parameter only allows printable ASCII; the `filename*` parameter
       preserves the real name for modern clients.
    2. Backslash-escape the two characters that have special meaning
       inside a quoted-string: `"` (closes the string) and `\\` (escape).
    """
    cleaned_chars: list[str] = []
    for ch in name:
        codepoint = ord(ch)
        if codepoint < 0x20 or codepoint == 0x7F or codepoint > 0x7E:
            cleaned_chars.append("_")
        elif ch == "\\" or ch == '"':
            cleaned_chars.append("\\" + ch)
        else:
            cleaned_chars.append(ch)
    return "".join(cleaned_chars)


__all__ = ["router"]
