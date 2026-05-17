"""SQLAlchemy 2.0 declarative model for the `meeting_link` table.

Mirrors migration `alembic/versions/0019_meeting_link.py`. Per slice-21
design "Schema: single-row + bidirectional Repository abstraction", the row
captures `(from_meeting_id, to_meeting_id)` directionally; bidirectional
semantics live in :class:`MeetingLinkRepository`, not the model.

FK column type is TEXT to match `meeting.id` (shape `m_<urlsafe-token>`).
The row's own `id` column is UUID — see the migration's docstring for the
rationale on the spec-vs-implementation mismatch on column types.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from meeting_playbook.meetings.models import Base


class MeetingLink(Base):
    __tablename__ = "meeting_link"
    __table_args__ = (
        CheckConstraint(
            "from_meeting_id <> to_meeting_id",
            name="meeting_link_no_self_reference",
        ),
        CheckConstraint(
            "link_type IN ('related')",
            name="meeting_link_link_type_check",
        ),
        # Secondary B-tree indexes are declared at the migration layer
        # (not via SQLAlchemy Index here) because we need them as explicit
        # named indexes — see 0019_meeting_link.py.
        Index("meeting_link_from_meeting_id_idx", "from_meeting_id"),
        Index("meeting_link_to_meeting_id_idx", "to_meeting_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    from_meeting_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("meeting.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_meeting_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("meeting.id", ondelete="CASCADE"),
        nullable=False,
    )
    link_type: Mapped[str] = mapped_column(Text, nullable=False, default="related")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
