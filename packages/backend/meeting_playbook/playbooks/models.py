"""SQLAlchemy 2.0 model for the `playbook` table.

Mirrors `alembic/versions/0002_create_playbook.py`. The seven content fields
are stored as plain `Text` columns so Slice 5's LLM generation can set
individual fields without JSON manipulation.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, Text
from sqlalchemy.orm import Mapped, mapped_column

from meeting_playbook.meetings.models import Base


class Playbook(Base):
    __tablename__ = "playbook"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # FK to meeting.id is declared at the DB level by the migration.
    meeting_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    free_form_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    counterparty_profile: Mapped[str] = mapped_column(Text, nullable=False, default="")
    anticipated_topics: Mapped[str] = mapped_column(Text, nullable=False, default="")
    anticipated_objections: Mapped[str] = mapped_column(Text, nullable=False, default="")
    talking_points: Mapped[str] = mapped_column(Text, nullable=False, default="")
    red_lines: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Slice-20c: snapshot of the attachment-set hash captured at generation
    # time. NULL on legacy rows; the application layer treats NULL as the
    # canonical empty-set hash when computing the `is_stale` flag.
    attachment_hash_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
