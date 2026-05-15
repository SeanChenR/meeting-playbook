"""PATCH /api/meetings/{id}/transcript_chunks/{chunk_id} — slice-16 task 5.1.

Per design *PATCH ... 只允許 `text`*: this endpoint exposes the single
mutable field on `transcript_chunk`. Everything else (speaker, timestamps,
asr_provider_used, confidence) is a capture-time fact that future audit
tooling must trust — the editor never moves them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.models import Meeting
from meeting_playbook.sessions.models import TranscriptChunk

router = APIRouter(tags=["transcript_edit"])


_ALLOWED_FIELDS = {"text"}
_IMMUTABLE_FIELDS = {
    "speaker",
    "started_at",
    "ended_at",
    "asr_provider_used",
    "confidence",
}
_TEXT_MAX_LEN = 10_000


def _detail(code: str, message: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"error_code": code, "message": message}
    body.update(extra)
    return body


@router.patch("/api/meetings/{meeting_id}/transcript_chunks/{chunk_id}")
async def patch_transcript_chunk(
    meeting_id: str,
    chunk_id: str,
    body: Annotated[dict[str, Any], Body()],
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> dict[str, Any]:
    """Update only `transcript_chunk.text`; reject any other field."""
    # Reject any unknown / immutable field BEFORE checking ownership so
    # the client gets the precise reason without burning a DB lookup.
    immutable_present = [k for k in body.keys() if k in _IMMUTABLE_FIELDS]
    if immutable_present:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail(
                "transcript_edit.immutable_field",
                "Only `text` is editable; rejected immutable fields: "
                + ", ".join(immutable_present),
            ),
        )
    unknown = [k for k in body.keys() if k not in _ALLOWED_FIELDS]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail(
                "transcript_edit.immutable_field",
                "Unknown fields rejected: " + ", ".join(unknown),
            ),
        )

    new_text = body.get("text")
    if not isinstance(new_text, str) or len(new_text) == 0 or len(new_text) > _TEXT_MAX_LEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail(
                "transcript_edit.invalid_text",
                f"`text` must be a non-empty string of <= {_TEXT_MAX_LEN} chars",
            ),
        )

    chunk = (
        await session.execute(select(TranscriptChunk).where(TranscriptChunk.id == chunk_id))
    ).scalar_one_or_none()
    if chunk is None or chunk.meeting_id != meeting_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_detail(
                "transcript_edit.chunk_not_found",
                f"Chunk {chunk_id} not found for meeting {meeting_id}",
            ),
        )

    meeting = (
        await session.execute(select(Meeting).where(Meeting.id == meeting_id))
    ).scalar_one_or_none()
    if meeting is None or meeting.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_detail(
                "transcript_edit.forbidden",
                "You do not own this chunk's meeting",
            ),
        )

    chunk.text = new_text
    chunk.text_edited_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(chunk)

    return {
        "id": chunk.id,
        "text": chunk.text,
        "text_edited_at": chunk.text_edited_at.isoformat() if chunk.text_edited_at else None,
    }
