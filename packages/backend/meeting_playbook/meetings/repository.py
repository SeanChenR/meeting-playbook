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

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.models import Meeting

# Allowed forward-only meeting status transitions (slice-06).
# Any pair NOT in this set raises MeetingStatusConflict.
_ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("scheduled", "in_progress"),
        ("in_progress", "completed"),
    }
)


class MeetingStatusConflict(Exception):
    """Raised when `transition_status` cannot apply the requested transition.

    Carries the requested (from, to) pair so callers can map to a typed
    error code or log diagnostics.
    """

    def __init__(self, *, meeting_id: str, expected_from: str, target: str) -> None:
        self.meeting_id = meeting_id
        self.expected_from = expected_from
        self.target = target
        super().__init__(
            f"Cannot transition meeting {meeting_id} from {expected_from!r} "
            f"to {target!r}: row missing or current status differs."
        )


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

    async def transition_status(
        self,
        *,
        meeting_id: str,
        expected_from: str,
        target: str,
    ) -> None:
        """Atomically advance `meeting.status` from one state to the next.

        Slice-06: this is the SOLE write path for the `status` column. Any
        transition not in `_ALLOWED_TRANSITIONS` raises immediately. The
        UPDATE filters by both id AND current status — if the RETURNING is
        empty, either the row is missing OR the status was already past the
        expected_from state, both of which surface as `MeetingStatusConflict`
        so concurrent attempts and stale callers fail loudly.
        """
        if (expected_from, target) not in _ALLOWED_TRANSITIONS:
            raise MeetingStatusConflict(
                meeting_id=meeting_id,
                expected_from=expected_from,
                target=target,
            )

        result = await self._session.execute(
            text(
                """
                UPDATE meeting
                   SET status = :target,
                       updated_at = now()
                 WHERE id = :mid
                   AND status = :expected_from
             RETURNING id
                """
            ),
            {"mid": meeting_id, "expected_from": expected_from, "target": target},
        )
        if result.first() is None:
            raise MeetingStatusConflict(
                meeting_id=meeting_id,
                expected_from=expected_from,
                target=target,
            )
