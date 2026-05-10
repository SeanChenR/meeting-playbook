"""PlaybookRepository — the single access path for playbook rows.

Per design.md (slice-04-playbook-editor):
- All higher layers (router + future advisor / summary slices) MUST go
  through this repository so that ownership scoping, the 1:1-with-meeting
  invariant, and updated_at advancement cannot be bypassed.
- `get_or_create_for_meeting` is idempotent: first call inserts an empty
  row, subsequent calls return the same row.
- `upsert_for_meeting` performs a full replacement of the seven content
  fields and stamps `updated_at` to the current server time.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.playbooks.models import Playbook


class PlaybookUpsertPayload(TypedDict):
    free_form_markdown: str
    objective: str
    counterparty_profile: str
    anticipated_topics: str
    anticipated_objections: str
    talking_points: str
    red_lines: str


_CONTENT_FIELDS = (
    "free_form_markdown",
    "objective",
    "counterparty_profile",
    "anticipated_topics",
    "anticipated_objections",
    "talking_points",
    "red_lines",
)


class PlaybookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_for_meeting(self, meeting_id: str) -> Playbook:
        """Return the playbook for `meeting_id`, inserting an empty row if missing.

        The INSERT runs `ON CONFLICT (meeting_id) DO NOTHING`, then a SELECT
        retrieves whichever row is now in the table. This collapses
        existence-check + insert into a single round-trip and remains correct
        under concurrency.
        """
        now = datetime.now(UTC)
        stmt = (
            pg_insert(Playbook)
            .values(
                id=f"pb_{secrets.token_urlsafe(16)}",
                meeting_id=meeting_id,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["meeting_id"])
        )
        await self._session.execute(stmt)
        await self._session.commit()

        result = await self._session.execute(
            select(Playbook).where(Playbook.meeting_id == meeting_id)
        )
        playbook = result.scalar_one()
        return playbook

    async def upsert_for_meeting(self, meeting_id: str, payload: PlaybookUpsertPayload) -> Playbook:
        """Full upsert of the seven content fields; stamps updated_at = now()."""
        now = datetime.now(UTC)
        values = {
            "id": f"pb_{secrets.token_urlsafe(16)}",
            "meeting_id": meeting_id,
            "created_at": now,
            "updated_at": now,
            **{field: payload[field] for field in _CONTENT_FIELDS},  # type: ignore[literal-required]
        }
        stmt = (
            pg_insert(Playbook)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["meeting_id"],
                set_={
                    **{field: values[field] for field in _CONTENT_FIELDS},
                    "updated_at": now,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

        # Bypass any cached ORM instance from a prior get_or_create call so
        # the returned Playbook reflects the values just written.
        result = await self._session.execute(
            select(Playbook)
            .where(Playbook.meeting_id == meeting_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()
