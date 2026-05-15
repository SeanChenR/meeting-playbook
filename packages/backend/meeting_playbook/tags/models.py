"""SQLAlchemy models for the slice-17 tag system.

`Tag` mirrors the `tag` table created by migration 0013; `MeetingTag` is the
N:M junction. `Meeting.tags` exposes the many-to-many traversal so the
meetings router can `selectinload(Meeting.tags)` and avoid N+1 queries.

Per design.md (slice-17) — Decision: Repository cascade walks the DB FK; the
ORM relationship is read-only and does NOT issue manual DELETEs against the
junction (the FK ON DELETE CASCADE takes care of cleanup).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from meeting_playbook.meetings.models import Base, Meeting


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class MeetingTag(Base):
    __tablename__ = "meeting_tag"
    __table_args__ = (PrimaryKeyConstraint("meeting_id", "tag_id", name="meeting_tag_pkey"),)

    meeting_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("meeting.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tag.id", ondelete="CASCADE"),
        nullable=False,
    )
    attached_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


# Attach the many-to-many relationship to `Meeting` after both models are
# defined. We use `lazy="noload"` — when callers do NOT eagerly load with
# `selectinload(Meeting.tags)`, accessing `meeting.tags` returns an empty
# list rather than raising or silently issuing a lazy SELECT in an async
# context (a common N+1 / async-IO foot-gun in SQLAlchemy 2.0). The
# meetings list / detail endpoints both use `selectinload` so they see the
# real tag rows; legacy callers (rerun runtime, background tasks) that
# don't need tags get an empty list instead of an error.
Meeting.tags = relationship(  # type: ignore[attr-defined]
    Tag,
    secondary=MeetingTag.__table__,
    primaryjoin=Meeting.id == MeetingTag.meeting_id,
    secondaryjoin=Tag.id == MeetingTag.tag_id,
    order_by=MeetingTag.attached_at.asc(),
    viewonly=True,
    lazy="noload",
)
