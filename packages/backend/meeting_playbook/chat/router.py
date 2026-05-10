"""Chat HTTP router — GET /api/meetings/{id}/chat_messages.

Per spec tactical-advisor ADDED requirement "GET /api/meetings/{id}/chat_messages
returns persisted chat history". The gateway-injected `X-User-Id` header
authorizes ownership; non-owner / non-existent meeting returns 404 with the
shared `meeting.not_found` envelope.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.chat.repository import ChatMessageRepository
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository

router = APIRouter(tags=["chat"])


@router.get("/api/meetings/{meeting_id}/chat_messages")
async def list_chat_messages(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> list[dict]:
    """Per-meeting chat history, ordered by `created_at` ASC."""
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )

    rows = await ChatMessageRepository(session).list_for_meeting(meeting_id)
    return [
        {
            "id": m.id,
            "meeting_id": m.meeting_id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]
