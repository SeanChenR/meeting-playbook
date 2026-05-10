"""SummaryRepository — write path for summary rows + stale-flag SQL.

Per design.md (slice-10-post-meeting-summary):
- Decision 1: 4-column schema; UNIQUE on meeting_id; upsert via ON CONFLICT
- Decision 8: separate AsyncSession per background task (caller's responsibility)
- Decision 9: stale flag computed in a single SQL via MAX() subqueries on
  transcript_chunk / playbook / chat_message timestamps
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.summarization.models import Summary


@dataclass(frozen=True)
class SummaryWithStale:
    """Summary row plus the computed `is_stale` boolean from the GET response.

    `is_stale` is True iff any of (latest transcript_chunk.created_at,
    playbook.updated_at, latest chat_message.created_at) is strictly later
    than the summary's `generated_at`. Stale = the user should consider
    regenerating because their context has moved on.
    """

    id: str
    meeting_id: str
    markdown: str
    generated_at: datetime
    is_stale: bool


_STALE_QUERY = text(
    """
    SELECT
      s.id,
      s.meeting_id,
      s.markdown,
      s.generated_at,
      (
        s.generated_at < COALESCE(
          (SELECT MAX(created_at) FROM transcript_chunk WHERE meeting_id = s.meeting_id),
          '-infinity'::timestamptz
        )
        OR s.generated_at < COALESCE(
          (SELECT updated_at FROM playbook WHERE meeting_id = s.meeting_id),
          '-infinity'::timestamptz
        )
        OR s.generated_at < COALESCE(
          (SELECT MAX(created_at) FROM chat_message WHERE meeting_id = s.meeting_id),
          '-infinity'::timestamptz
        )
      ) AS is_stale
    FROM summary s
    WHERE s.meeting_id = :meeting_id
    """
)


class SummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_meeting(self, meeting_id: str) -> Summary | None:
        """Return the summary row for the meeting, or None if absent."""
        result = await self._session.execute(
            select(Summary).where(Summary.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def get_with_stale_flag(self, meeting_id: str) -> SummaryWithStale | None:
        """Single SQL fetch of the summary row + computed is_stale flag.

        Returns None when no summary row exists for the meeting.
        """
        result = await self._session.execute(_STALE_QUERY, {"meeting_id": meeting_id})
        row = result.first()
        if row is None:
            return None
        return SummaryWithStale(
            id=row.id,
            meeting_id=row.meeting_id,
            markdown=row.markdown,
            generated_at=row.generated_at,
            is_stale=bool(row.is_stale),
        )

    async def upsert(self, *, meeting_id: str, markdown: str) -> Summary:
        """Atomic upsert via PostgreSQL ON CONFLICT (meeting_id) DO UPDATE.

        On conflict, replaces `markdown` and stamps `generated_at = now()`.
        Always returns the resulting (inserted or updated) row.
        """
        new_id = f"sm_{secrets.token_urlsafe(16)}"
        # Use SQL `now()` for both first-insert and conflict-update so the
        # timestamp is monotonic per the DB clock (avoids client-side time
        # drift between calls landing in the same wall-clock millisecond).
        stmt = (
            pg_insert(Summary)
            .values(
                id=new_id,
                meeting_id=meeting_id,
                markdown=markdown,
                generated_at=text("now()"),
            )
            .on_conflict_do_update(
                index_elements=["meeting_id"],
                set_={"markdown": markdown, "generated_at": text("now()")},
            )
            .returning(Summary)
        )
        # `populate_existing=True` overwrites the session's identity-map row
        # with the values returned by RETURNING. Without it, an upsert that
        # collides on meeting_id returns the cached pre-update Python object
        # (markdown still pointing at the prior value).
        result = await self._session.execute(stmt, execution_options={"populate_existing": True})
        await self._session.commit()
        return result.scalar_one()


__all__ = ["SummaryRepository", "SummaryWithStale"]
