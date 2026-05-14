"""SQLAlchemy model for voice_enrollment (slice-13 / ADR-0029).

Matches migration `0009_create_voice_enrollment`:
- user_id PK + FK to user.id CASCADE
- sample_wav_path: path on disk under VOICE_ENROLLMENT_DIR
- embedding: BYTEA (LargeBinary) — float32 ndarray serialized via tobytes()
- created_at: timestamp of the most recent enrollment (replaced on re-upload)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column

from meeting_playbook.meetings.models import Base


class VoiceEnrollment(Base):
    __tablename__ = "voice_enrollment"

    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sample_wav_path: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
