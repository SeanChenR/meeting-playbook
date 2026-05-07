"""SQLAlchemy 2.0 declarative model for the `meeting` table.

Columns mirror the migration in `alembic/versions/0001_create_meeting.py`.
Per design.md (slice-03-meeting-crud), Meeting is the deep-module root that
all subsequent vertical slices FK into.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import TIMESTAMP, CheckConstraint, Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MeetingStatus = Literal["scheduled", "in_progress", "completed"]


class Base(DeclarativeBase):
    """Application-table declarative base. Auth tables live outside this base."""


class Meeting(Base):
    __tablename__ = "meeting"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'completed')",
            name="meeting_status_check",
        ),
        # Mirrors meeting_user_id_created_at_desc_idx in the migration.
        Index(
            "meeting_user_id_created_at_desc_idx",
            "user_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # FK to user.id is declared at the DB level by the migration; the auth
    # `user` table lives outside this MetaData (managed by Better Auth).
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    counterparty_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    me_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MeetingStatus] = mapped_column(Text, nullable=False, default="scheduled")
    asr_provider: Mapped[str] = mapped_column(Text, nullable=False, default="whisper")
    calendar_event_id: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
