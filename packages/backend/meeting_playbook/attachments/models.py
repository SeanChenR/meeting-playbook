"""SQLAlchemy 2.0 declarative model for the `meeting_attachment` table.

Columns mirror migrations `0016_meeting_attachment.py` and
`0019_attachment_nullable_meeting.py`.

Slice-20a originally scoped attachments per-meeting (FK CASCADE +
soft-delete via `deleted_at`). Slice-24 opens the table to a staged
(orphan) state — `meeting_id IS NULL` rows owned by `user_id` until the
caller creates a meeting and attaches them. See ADR-free design docs
under openspec/changes/slice-24-attachment-staging-at-create.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import TIMESTAMP, CheckConstraint, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from meeting_playbook.meetings.models import Base

AttachmentKind = Literal["image", "pdf", "docx", "text", "markdown"]


class MeetingAttachment(Base):
    __tablename__ = "meeting_attachment"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('image', 'pdf', 'docx', 'text', 'markdown')",
            name="meeting_attachment_kind_check",
        ),
        CheckConstraint("bytes > 0", name="meeting_attachment_bytes_positive_check"),
        Index(
            "meeting_attachment_meeting_id_deleted_at_idx",
            "meeting_id",
            "deleted_at",
        ),
        # Slice-24: composite index speeding up the staging-list query
        # `WHERE user_id = ? AND meeting_id IS NULL` and per-meeting list.
        Index(
            "meeting_attachment_user_meeting_uploaded_idx",
            "user_id",
            "meeting_id",
            "uploaded_at",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # Slice-24: nullable for staged rows. FK to meeting.id ON DELETE CASCADE
    # is enforced by the migration; the ORM model only mirrors columns.
    meeting_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Slice-24: explicit user_id for ownership scoping when meeting_id IS
    # NULL. FK to "user".id is enforced by the migration.
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[AttachmentKind] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )


__all__ = ["AttachmentKind", "MeetingAttachment"]
