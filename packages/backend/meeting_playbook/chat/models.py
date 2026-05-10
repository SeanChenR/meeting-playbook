"""SQLAlchemy model for chat_message (slice-09 schema).

Per spec tactical-advisor ADDED requirement "chat_message table persists
per-meeting conversation history" + design.md Decision 1 (5-column
schema, no status / error_code; FK CASCADE; composite index).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from meeting_playbook.meetings.models import Base


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("meeting.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


__all__ = ["ChatMessage"]
