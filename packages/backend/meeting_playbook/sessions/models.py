"""SQLAlchemy models for transcript_chunk + recording (slice-06 schema)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from meeting_playbook.meetings.models import Base


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunk"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("meeting.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    asr_provider_used: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Slice-16: PATCH /api/meetings/.../transcript_chunks stamps this on
    # successful text edit. NULL = chunk text untouched since ASR wrote it.
    text_edited_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )


class Recording(Base):
    __tablename__ = "recording"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("meeting.id", ondelete="CASCADE"),
        nullable=False,
    )
    stream: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Slice-11: NULL → recording wav still on disk; NOT NULL → cleanup job
    # has unlinked the wav at this timestamp. Row itself is never deleted.
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    # Slice-14: distinguishes live capture from offline ingest. CHECK enforced
    # at the DB layer (`recording_source_check`); the only valid values are
    # 'live' and 'offline'. Defaults to 'live' so existing rows back-fill.
    source: Mapped[str] = mapped_column(Text, nullable=False, default="live")
    # Slice-14 added this nullable; slice-16 migration 0014 backfills any
    # remaining NULL rows from `created_at` and tightens to NOT NULL. The
    # AudioRangeServer uses this as the wall-clock anchor for computing
    # byte offsets relative to a chunk's `started_at`.
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
