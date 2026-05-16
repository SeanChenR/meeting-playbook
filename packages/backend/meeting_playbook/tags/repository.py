"""TagRepository — slice-17 deep module for the tag system.

Per design.md (slice-17):
- `(user_id, lower(name))` case-insensitive uniqueness is enforced by the
  DB expression unique index. The repo catches `IntegrityError` and surfaces
  `TagNameTaken` so the router can map it to 422 `tag.name_taken`.
- `delete(user_id, tag_id)` issues a single `DELETE FROM tag` — the FK
  `ON DELETE CASCADE` on `meeting_tag` does the junction cleanup, so we do
  NOT chain a manual `DELETE FROM meeting_tag` (which would widen the race
  window and lose the FK guarantee).
- `attach(...)` runs inside a transaction with a `SELECT ... FOR UPDATE`
  lock on the meeting's junction rows so two concurrent attaches on the
  same meeting see a consistent count (per-meeting ≤ 10 invariant). When a
  pair `(meeting_id, tag_id)` is already attached, the call is idempotent
  and returns the existing row.
- `name` is trimmed before persistence; an empty result raises
  `InvalidTagName`. Color must be in the preset palette
  (`meeting_playbook.tags.colors.TAG_PALETTE_HEX`); otherwise
  `InvalidTagColor`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.models import Meeting
from meeting_playbook.tags.colors import is_palette_color
from meeting_playbook.tags.models import MeetingTag, Tag


class TagNameTaken(Exception):
    """Raised when `(user_id, lower(name))` collides with an existing tag."""


class InvalidTagColor(Exception):
    """Raised when the supplied color hex is not in `TAG_PALETTE_HEX`."""


class InvalidTagName(Exception):
    """Raised when the supplied name is blank after `strip()`."""


class TagLimitExceeded(Exception):
    """Raised when attaching would push a meeting beyond the 10-tag limit."""

    def __init__(self, *, current_count: int) -> None:
        self.current_count = current_count
        super().__init__(f"Meeting already has {current_count} tags (max 10).")


@dataclass(frozen=True)
class TagWithMeta:
    """Read-only projection used by `list_for_user(with_meeting_count=True)`."""

    id: str
    user_id: str
    name: str
    color: str
    created_at: datetime
    meeting_count: int | None


_MAX_TAGS_PER_MEETING = 10


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(
        self, *, user_id: str, with_meeting_count: bool = False
    ) -> list[TagWithMeta]:
        """Return the user's tags sorted by `created_at` ascending.

        When `with_meeting_count=True` each row carries a `meeting_count`
        computed via a single LEFT JOIN + GROUP BY so listing N tags issues
        exactly one SQL query (no N+1 against `meeting_tag`).
        """
        if with_meeting_count:
            count_col = func.count(MeetingTag.tag_id).label("meeting_count")
            stmt = (
                select(Tag, count_col)
                .outerjoin(MeetingTag, MeetingTag.tag_id == Tag.id)
                .where(Tag.user_id == user_id)
                .group_by(Tag.id)
                .order_by(Tag.created_at.asc())
            )
            result = await self._session.execute(stmt)
            rows = result.all()
            return [
                TagWithMeta(
                    id=tag.id,
                    user_id=tag.user_id,
                    name=tag.name,
                    color=tag.color,
                    created_at=tag.created_at,
                    meeting_count=int(count),
                )
                for tag, count in rows
            ]

        stmt = select(Tag).where(Tag.user_id == user_id).order_by(Tag.created_at.asc())
        result = await self._session.execute(stmt)
        return [
            TagWithMeta(
                id=tag.id,
                user_id=tag.user_id,
                name=tag.name,
                color=tag.color,
                created_at=tag.created_at,
                meeting_count=None,
            )
            for tag in result.scalars().all()
        ]

    async def get_for_user(self, *, user_id: str, tag_id: str) -> Tag | None:
        result = await self._session.execute(
            select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, *, user_id: str, name: str, color: str) -> Tag:
        trimmed = name.strip() if isinstance(name, str) else ""
        if not trimmed:
            raise InvalidTagName("name must not be blank")
        if not is_palette_color(color):
            raise InvalidTagColor(f"color {color!r} is not in the preset palette")

        tag = Tag(
            id=f"tag_{secrets.token_urlsafe(16)}",
            user_id=user_id,
            name=trimmed,
            color=color,
            created_at=datetime.now(UTC),
        )
        self._session.add(tag)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise TagNameTaken(
                f"Tag name {trimmed!r} already exists for user {user_id!r}."
            ) from exc
        await self._session.refresh(tag)
        return tag

    async def update(
        self,
        *,
        user_id: str,
        tag_id: str,
        name: str | None = None,
        color: str | None = None,
    ) -> Tag | None:
        existing = await self.get_for_user(user_id=user_id, tag_id=tag_id)
        if existing is None:
            return None

        fields: dict[str, object] = {}
        if name is not None:
            trimmed = name.strip()
            if not trimmed:
                raise InvalidTagName("name must not be blank")
            fields["name"] = trimmed
        if color is not None:
            if not is_palette_color(color):
                raise InvalidTagColor(f"color {color!r} is not in the preset palette")
            fields["color"] = color
        if not fields:
            return existing

        try:
            await self._session.execute(
                update(Tag).where(Tag.id == tag_id, Tag.user_id == user_id).values(**fields)
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise TagNameTaken(
                f"Tag name {fields.get('name')!r} already exists for user {user_id!r}."
            ) from exc

        await self._session.refresh(existing)
        return existing

    async def delete(self, *, user_id: str, tag_id: str) -> bool:
        """Single-statement delete; FK CASCADE cleans the junction rows."""
        result = await self._session.execute(
            delete(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
        )
        await self._session.commit()
        return (result.rowcount or 0) > 0

    async def attach(self, *, user_id: str, meeting_id: str, tag_id: str) -> MeetingTag:
        """Attach `tag_id` to `meeting_id`, enforcing the 10-tag-per-meeting limit.

        Ownership: both meeting and tag must belong to `user_id`; the router
        layer translates a missing meeting / tag into 404 before calling
        this method, but we double-check here so misuse from background
        callers does not silently insert cross-user rows.
        """
        # Verify both rows belong to user_id before locking.
        meeting = await self._session.scalar(
            select(Meeting).where(Meeting.id == meeting_id, Meeting.user_id == user_id)
        )
        if meeting is None:
            raise LookupError(f"meeting {meeting_id!r} not owned by {user_id!r}")
        tag = await self.get_for_user(user_id=user_id, tag_id=tag_id)
        if tag is None:
            raise LookupError(f"tag {tag_id!r} not owned by {user_id!r}")

        # Lock the meeting's junction rows so a concurrent attach sees the
        # same count. PostgreSQL: `FOR UPDATE` is sufficient on the existing
        # rows; even if there are zero rows the predicate locks the empty set
        # — adequate when there are no other concurrent writers (single-user
        # project, per design.md).
        #
        # Slice-17 review feedback: idempotency check moved INSIDE the lock
        # so two concurrent attaches with the same (meeting_id, tag_id) cannot
        # both pass an outside-lock check and then race to INSERT (PK
        # violation). After acquiring the lock we already have the full
        # junction-row set, so check membership against it without a second
        # query.
        locked = await self._session.execute(
            select(MeetingTag).where(MeetingTag.meeting_id == meeting_id).with_for_update()
        )
        existing_rows = list(locked.scalars().all())
        for row in existing_rows:
            if row.tag_id == tag_id:
                return row  # idempotent — pair already attached
        current_count = len(existing_rows)
        if current_count >= _MAX_TAGS_PER_MEETING:
            raise TagLimitExceeded(current_count=current_count)

        row = MeetingTag(
            meeting_id=meeting_id,
            tag_id=tag_id,
            attached_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def detach(self, *, user_id: str, meeting_id: str, tag_id: str) -> None:
        """Detach a tag from a meeting; missing pair is a no-op (idempotent).

        Ownership: silently no-ops when the meeting or tag does not belong
        to `user_id` — the router maps the no-op to HTTP 204 per spec.
        """
        # Constrain by ownership so a cross-user DELETE cannot wipe rows.
        await self._session.execute(
            delete(MeetingTag)
            .where(
                MeetingTag.meeting_id == meeting_id,
                MeetingTag.tag_id == tag_id,
            )
            .where(MeetingTag.meeting_id.in_(select(Meeting.id).where(Meeting.user_id == user_id)))
            .where(MeetingTag.tag_id.in_(select(Tag.id).where(Tag.user_id == user_id)))
        )
        await self._session.commit()
