"""Playbook REST router — GET (auto-create) + PUT (full upsert).

Per spec (slice-04-playbook-editor):
- Both endpoints scope by `MeetingRepository.get_for_user`; cross-user
  access returns 404 + `error_code: meeting.not_found` (no existence leak,
  reusing the slice-03 contract).
- GET auto-creates an empty playbook on first read so the UI always sees
  an editable surface.
- PUT performs a full upsert; missing fields are defaulted to '' by
  Pydantic (PlaybookUpsert).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.playbooks.repository import PlaybookRepository
from meeting_playbook.playbooks.schemas import PlaybookRead, PlaybookUpsert

router = APIRouter(prefix="/api/meetings", tags=["playbooks"])


def _meeting_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
    )


@router.get("/{meeting_id}/playbook", response_model=PlaybookRead)
async def get_playbook(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> PlaybookRead:
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    playbook = await PlaybookRepository(session).get_or_create_for_meeting(meeting_id)
    return PlaybookRead.model_validate(playbook)


@router.put("/{meeting_id}/playbook", response_model=PlaybookRead)
async def put_playbook(
    meeting_id: str,
    body: PlaybookUpsert,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> PlaybookRead:
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        raise _meeting_not_found()

    payload = body.model_dump()
    saved = await PlaybookRepository(session).upsert_for_meeting(meeting_id, payload)
    return PlaybookRead.model_validate(saved)
