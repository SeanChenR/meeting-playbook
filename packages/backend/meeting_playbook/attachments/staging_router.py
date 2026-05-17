"""Staged attachment REST router — slice-24 tasks 3.1 + 3.2.

Three endpoints under `/api/attachments` for user-scoped (not meeting-
scoped) attachment lifecycle:

- `POST /api/attachments/staging`
  Multipart upload → writes to `ATTACHMENT_DIR/_staging/<user>/<id><ext>`,
  inserts a `meeting_attachment` row with `meeting_id=NULL,
  user_id=<current>`. Per-user staging quota (10 files / 60 MiB) enforced
  before the file hits disk so an over-quota POST never leaks bytes.

- `GET /api/attachments?status=pending`
  Lists the caller's active staged rows oldest-first. Any other (or
  missing) `status` query value → 422 `attachment.invalid_status_filter`
  so the contract is explicit instead of silently returning everything.

- `DELETE /api/attachments/{attachment_id}`
  Soft-deletes a staged row owned by the caller and unlinks the on-disk
  file. Attached rows (`meeting_id IS NOT NULL`), cross-user ids, and
  unknown ids all collapse onto 404 `attachment.not_found` so we don't
  leak whether an id exists or to whom.

Auth: every endpoint pulls `X-User-Id` via `get_user_id_dependency` and
defers ownership scoping to `AttachmentRepository`.
"""

from __future__ import annotations

import contextlib
import logging
import secrets
from pathlib import Path
from typing import Annotated, Any

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.attachments.repository import AttachmentRepository
from meeting_playbook.attachments.validation import (
    AttachmentValidationError,
    canonical_extension,
    validate_staging_upload,
)
from meeting_playbook.config import get_settings
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/attachments", tags=["attachments-staging"])


def _attachment_dir() -> Path:
    """Resolve `ATTACHMENT_DIR` with `~` expanded + symlinks resolved."""
    settings = get_settings()
    return Path(settings.attachment_dir).expanduser().resolve()


def _staging_dir(user_id: str) -> Path:
    """Per-user staging directory: `ATTACHMENT_DIR/_staging/<user_id>/`.

    `_staging` collides with no meeting id (meetings use `m_<token>` ids,
    `_` is not a valid leading character) so the namespace is safe.
    """
    return _attachment_dir() / "_staging" / user_id


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


@router.post("/staging", status_code=status.HTTP_201_CREATED)
async def upload_staged_attachment(
    file: UploadFile,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, Any]:
    """Validate + persist a staged (orphan) attachment.

    Order of operations matches the per-meeting upload path:
      (1) Read the body in full so the validator can measure declared
          bytes (single-file cap + per-user quota).
      (2) Validate whitelist + per-file size + per-user staging quota.
      (3) Compute the staging path + write the file.
      (4) Insert the row; on failure unlink the file (best-effort).
    """
    body = await file.read()
    if len(body) == 0:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "attachment.unsupported_format",
            "Uploaded file is empty.",
        )

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    filename = file.filename or ""

    repo = AttachmentRepository(session)
    staged_count, staged_bytes = await repo.count_staged_for_user(user_id=user_id)

    try:
        kind = validate_staging_upload(
            content_type=content_type,
            filename=filename,
            declared_bytes=len(body),
            staged_count=staged_count,
            staged_bytes=staged_bytes,
        )
    except AttachmentValidationError as exc:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            exc.error_code,
            str(exc),
        ) from exc

    attachment_id = f"att_{secrets.token_urlsafe(16)}"
    ext = canonical_extension(kind, filename, content_type)
    target_dir = _staging_dir(user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{attachment_id}{ext}"

    try:
        await anyio.to_thread.run_sync(target_path.write_bytes, body)
    except OSError as exc:
        logger.error("staged attachment write failed: %s", exc)
        raise _http_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "common.internal_error",
            "Failed to persist staged attachment.",
        ) from exc

    try:
        att = await repo.create(
            attachment_id=attachment_id,
            meeting_id=None,
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


@router.get("")
async def list_pending_attachments(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> dict[str, Any]:
    """List the caller's staged attachments when `status=pending`.

    Any other value (including no value) is rejected explicitly so
    callers must opt in to the staging view. Future status filters
    (`archived`, etc.) can be added without breaking this contract.
    """
    if status_filter != "pending":
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "attachment.invalid_status_filter",
            "status query must be 'pending'.",
        )
    repo = AttachmentRepository(session)
    rows = await repo.list_staged_for_user(user_id=user_id)
    return {"attachments": [_serialize(a) for a in rows]}


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staged_attachment(
    attachment_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> Response:
    """Soft-delete a staged row + unlink the file. 404 for any non-match.

    Refuses to act on attached rows: the caller must use the
    `/api/meetings/{id}/attachments/{att_id}` endpoint, which carries
    different ownership semantics (FK CASCADE on meeting delete).
    """
    repo = AttachmentRepository(session)
    deleted = await repo.delete_staged(attachment_id=attachment_id, user_id=user_id)
    if deleted is None:
        raise _http_error(
            status.HTTP_404_NOT_FOUND,
            "attachment.not_found",
            "Attachment not found",
        )
    with contextlib.suppress(OSError):
        Path(deleted.file_path).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
