"""SQLAlchemy 2.0 declarative model for the `meeting_attachment` table.

Columns mirror migration `0016_meeting_attachment.py`. Per slice-20a design
"Schema：`meeting_attachment` 獨立表 + `kind` enum", attachments are scoped
per meeting with FK CASCADE and soft-delete via `deleted_at`.
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
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # FK on meeting.id ON DELETE CASCADE — declared in the migration; the
    # ORM model only mirrors columns, not constraints, since FK enforcement
    # is the database's job (see meetings/models.py for the same pattern).
    meeting_id: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[AttachmentKind] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )


__all__ = ["AttachmentKind", "MeetingAttachment"]
