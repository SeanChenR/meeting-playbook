"""Meeting REST router — POST/GET list/GET id/DELETE four-piece set.

Per spec (slice-03-meeting-crud):
- Every endpoint scopes by the gateway-injected `X-User-Id` header.
- Cross-user reads / deletes return 404 with no existence leak.
- POST is create-only this slice (no PATCH).

The router takes its DB session via `get_session_dependency` so tests can
override it to point at the test DB.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.meetings.schemas import MeetingCreate, MeetingRead

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MeetingRead)
async def create_meeting(
    body: MeetingCreate,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> MeetingRead:
    repo = MeetingRepository(session)
    meeting = await repo.create(
        user_id=user_id,
        title=body.title,
        counterparty_display_name=body.counterparty_display_name,
        me_display_name=body.me_display_name,
        scheduled_start_at=body.scheduled_start_at,
        scheduled_end_at=body.scheduled_end_at,
    )
    return MeetingRead.model_validate(meeting)


@router.get("", response_model=list[MeetingRead])
async def list_meetings(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> list[MeetingRead]:
    repo = MeetingRepository(session)
    rows = await repo.list_by_user(user_id)
    return [MeetingRead.model_validate(m) for m in rows]


@router.get("/{meeting_id}", response_model=MeetingRead)
async def get_meeting(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> MeetingRead:
    repo = MeetingRepository(session)
    meeting = await repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        # Hide the missing-vs-other-owner distinction (ownership isolation).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )
    return MeetingRead.model_validate(meeting)


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
