"""create voice_enrollment table — slice-13 / ADR-0029 voice enrollment.

Revision ID: 0009_create_voice_enrollment
Revises: 0008_asr_default_qwen3
Create Date: 2026-05-14

Per slice-13 design "`voice_enrollment.embedding` 儲存：bytea + numpy.tobytes":
- user_id is the PRIMARY KEY (per-user enrollment, at most one row)
- FK to user.id with ON DELETE CASCADE — deleting a user removes their
  voice enrollment automatically
- embedding stored as BYTEA via `numpy.ndarray.tobytes()` (float32);
  shape is recovered as `len(bytes) // 4` at read time (1-D, single speaker)
- sample_wav_path is the path on disk under VOICE_ENROLLMENT_DIR; row is
  authoritative even if file is missing (the file is a debugging aid)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_create_voice_enrollment"
down_revision: str | None = "0008_asr_default_qwen3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "voice_enrollment",
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sample_wav_path", sa.Text(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("voice_enrollment")
