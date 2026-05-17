"""MeetingLinkRepository — deep module hiding bidirectional row direction.

Per slice-21 design "`MeetingLinkRepository` interface (deep module)":

- `create(from_meeting_id, to_meeting_id)` writes one DB row directionally;
  the partial unique index on `(LEAST, GREATEST)` collapses both `(A, B)`
  and `(B, A)` into the same key, so a duplicate insert in either direction
  raises `MeetingLinkDuplicate` (translated from PostgreSQL `UniqueViolation`).
  Self-reference (`from_meeting_id == to_meeting_id`) raises
  `MeetingLinkSelfReference` before the DB is touched.
- `list_for_meeting(meeting_id)` returns the "other-meeting perspective" view —
  every row whose `from_meeting_id` OR `to_meeting_id` equals `meeting_id`,
  with the `other_meeting_id` projected via a CASE expression so callers
  never see row direction.
- `get(link_id)` returns the raw row (or None) so the router can inspect
  ownership before allowing a delete.
- `delete(link_id)` returns True iff one row was removed (idempotent at the
  row level).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meeting_links.models import MeetingLink
from meeting_playbook.meeting_links.schemas import MeetingLinkView


class MeetingLinkDuplicate(Exception):
    """Raised by :meth:`MeetingLinkRepository.create` when a link between the
    same pair of meetings already exists (in either direction).

    Mapped to HTTP 409 + ``error_code = "meeting_link.duplicate"`` at the
    router layer.
    """


class MeetingLinkSelfReference(Exception):
    """Raised by :meth:`MeetingLinkRepository.create` when
    ``from_meeting_id == to_meeting_id``.

    Mapped to HTTP 422 + ``error_code = "meeting_link.self_reference"`` at
    the router layer.
    """


# SQL for the bidirectional list query (per slice-21 design "Bidirectional
# query 實作 SQL"). The CASE expression projects the OTHER side of the link
# so the caller never has to know which column holds `meeting_id`.
_LIST_FOR_MEETING_SQL = text(
    """
    SELECT
      ml.id AS link_id,
      CASE WHEN ml.from_meeting_id = :id THEN ml.to_meeting_id ELSE ml.from_meeting_id END
        AS other_meeting_id,
      m.title AS other_meeting_title,
      m.scheduled_start_at AS other_meeting_scheduled_start_at,
      ml.link_type,
      ml.created_at
    FROM meeting_link ml
    JOIN meeting m
      ON m.id = CASE
                  WHEN ml.from_meeting_id = :id THEN ml.to_meeting_id
                  ELSE ml.from_meeting_id
                END
    WHERE ml.from_meeting_id = :id OR ml.to_meeting_id = :id
    ORDER BY ml.created_at DESC
    """
)


class MeetingLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        from_meeting_id: str,
        to_meeting_id: str,
        link_type: str = "related",
    ) -> MeetingLink:
        """Insert a single `meeting_link` row.

        Raises
        ------
        MeetingLinkSelfReference
            When ``from_meeting_id == to_meeting_id``.
        MeetingLinkDuplicate
            When the pair (in either direction) already exists. The DB
            partial unique index on (LEAST, GREATEST) raises
            `UniqueViolation`; we translate it to the domain exception so
            the router stays decoupled from psycopg / asyncpg internals.
        """
        if from_meeting_id == to_meeting_id:
            raise MeetingLinkSelfReference(f"Cannot link meeting {from_meeting_id!r} to itself")

        # Let the DB assign id + created_at via server defaults — we then
        # need the inserted row back so the router can return its id.
        # The IntegrityError can be raised by either the execute (immediate
        # constraint check) or the commit (deferred), so the try/except has
        # to wrap both.
        try:
            result = await self._session.execute(
                text(
                    """
                    INSERT INTO meeting_link (from_meeting_id, to_meeting_id, link_type)
                    VALUES (:from_id, :to_id, :link_type)
                    RETURNING id, from_meeting_id, to_meeting_id, link_type, created_at
                    """
                ).bindparams(from_id=from_meeting_id, to_id=to_meeting_id, link_type=link_type),
            )
            row = result.one()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # Gemini PR #39 review #1: narrow the IntegrityError mapping
            # to the two violations we actually want to translate into
            # domain exceptions. Any other IntegrityError (e.g. a FK
            # violation from a concurrently-deleted meeting) re-raises
            # so the router surfaces a 500 instead of misleading the
            # caller with `meeting_link.duplicate`.
            text_exc = str(exc.orig) if exc.orig is not None else str(exc)
            if "meeting_link_no_self_reference" in text_exc:
                # CHECK constraint defense-in-depth; the application-
                # level check above normally catches self-reference
                # first, but route through here too in case a caller
                # bypasses it.
                raise MeetingLinkSelfReference(text_exc) from exc
            if "meeting_link_pair_uidx" in text_exc:
                raise MeetingLinkDuplicate(text_exc) from exc
            raise

        # Build a model instance from the returning row so callers get the
        # same shape as a SQLAlchemy-loaded object.
        link = MeetingLink(
            id=row.id,
            from_meeting_id=row.from_meeting_id,
            to_meeting_id=row.to_meeting_id,
            link_type=row.link_type,
            created_at=row.created_at,
        )
        return link

    async def list_for_meeting(self, meeting_id: str) -> list[MeetingLinkView]:
        """Return every link touching ``meeting_id``, projected with the
        OPPOSITE meeting on each row. Sorted by `created_at` DESC.

        Empty list when the meeting has no links — never raises.
        """
        result = await self._session.execute(_LIST_FOR_MEETING_SQL, {"id": meeting_id})
        return [
            MeetingLinkView(
                link_id=r.link_id,
                other_meeting_id=r.other_meeting_id,
                other_meeting_title=r.other_meeting_title,
                other_meeting_scheduled_start_at=r.other_meeting_scheduled_start_at,
                link_type=r.link_type,
                created_at=r.created_at,
            )
            for r in result.all()
        ]

    async def get(self, link_id: UUID) -> MeetingLink | None:
        """Return the raw row or None — used by DELETE for ownership checks."""
        result = await self._session.execute(select(MeetingLink).where(MeetingLink.id == link_id))
        return result.scalar_one_or_none()

    async def delete(self, link_id: UUID) -> bool:
        """Delete the row by id; True if one row was removed, False otherwise.

        Idempotent at the row level — a second call on the same id returns
        False without raising.
        """
        result = await self._session.execute(delete(MeetingLink).where(MeetingLink.id == link_id))
        await self._session.commit()
        return (result.rowcount or 0) > 0
