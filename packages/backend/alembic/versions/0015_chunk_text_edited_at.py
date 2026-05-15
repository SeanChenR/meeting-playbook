"""transcript_chunk.text_edited_at — add nullable timestamp column (slice-16).

Revision ID: 0015_chunk_text_edited_at
Revises: 0014_recording_started_at
Create Date: 2026-05-15

Per slice-16 design *transcript_chunk gains text_edited_at column*:
- Newly inserted ASR chunks leave `text_edited_at = NULL` — captures the
  fact that the chunk's text was never touched after ASR wrote it.
- `PATCH /api/meetings/{id}/transcript_chunks/{chunk_id}` stamps
  `text_edited_at = now()` on successful update, so the UI can mark
  edited chunks (and a future audit slice can surface the edit history).
- Downgrade drops the column entirely.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_chunk_text_edited_at"
down_revision: str | None = "0014_recording_started_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transcript_chunk",
        sa.Column(
            "text_edited_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("transcript_chunk", "text_edited_at")
