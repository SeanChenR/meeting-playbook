"""SQLAlchemy model for summary (slice-10 schema).

Per spec meeting-summary ADDED requirement "summary table persists per-meeting
markdown summary" + design.md Decision 1: 4 columns, FK CASCADE, UNIQUE on
meeting_id (1:1 with meeting), no status / error_code (failed generations
don't write rows — same minimal-schema philosophy as slice-9 chat_message).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from meeting_playbook.meetings.models import Base


class Summary(Base):
    __tablename__ = "summary"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("meeting.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


__all__ = ["Summary"]
