"""MeetingRepository — the single access path for meeting CRUD.

Per design.md (slice-03-meeting-crud):
- All higher layers (router + future slices) MUST go through this repository
  so that ownership scoping cannot be bypassed.
- `get_for_user` and `delete_for_user` collapse the "missing" and "owned by
  someone else" cases into a single signal so the API layer can return 404
  uniformly without leaking existence (Requirement: ownership isolation).
- IDs are generated locally with `secrets.token_urlsafe(16)` to keep the same
  string shape as Better Auth's user.id.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.models import Meeting


class MeetingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: str,
        title: str,
        counterparty_display_name: str,
        me_display_name: str,
        asr_provider: str = "whisper",
    ) -> Meeting:
        meeting = Meeting(
            id=f"m_{secrets.token_urlsafe(16)}",
            user_id=user_id,
            title=title,
            counterparty_display_name=counterparty_display_name,
            me_display_name=me_display_name,
            status="scheduled",
            asr_provider=asr_provider,
            calendar_event_id=None,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(meeting)
        await self._session.commit()
        await self._session.refresh(meeting)
        return meeting

    async def list_by_user(self, user_id: str) -> list[Meeting]:
        result = await self._session.execute(
            select(Meeting).where(Meeting.user_id == user_id).order_by(Meeting.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, *, user_id: str, meeting_id: str) -> Meeting | None:
        result = await self._session.execute(
            select(Meeting).where(
                Meeting.id == meeting_id,
                Meeting.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_for_user(self, *, user_id: str, meeting_id: str) -> bool:
        result = await self._session.execute(
            delete(Meeting).where(
                Meeting.id == meeting_id,
                Meeting.user_id == user_id,
            )
        )
        await self._session.commit()
        return (result.rowcount or 0) > 0
