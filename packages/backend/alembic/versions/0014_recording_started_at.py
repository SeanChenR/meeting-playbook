"""recording.started_at — backfill from created_at + SET NOT NULL (slice-16).

Revision ID: 0014_recording_started_at
Revises: 0012_meeting_start_not_null
Create Date: 2026-05-15

Per slice-16 design Decision *Migration: `recording.started_at TIMESTAMPTZ
NOT NULL` + backfill 為 `created_at`*:
- S14 added `started_at` as a nullable column (offline ingest writes the
  user-supplied "actual_started_at"; live capture left it NULL pending
  this slice).
- Pre-existing rows where `started_at IS NULL` get back-filled with their
  `created_at` value so the AudioRangeServer can compute every chunk's
  byte offset relative to a known wall-clock anchor.
- After backfill the column becomes `NOT NULL` — the audio playback
  endpoint can rely on the column without `?? created_at` fallback.
- Downgrade only drops `NOT NULL`; back-filled values stay.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_recording_started_at"
down_revision: str | None = "0012_meeting_start_not_null"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE recording SET started_at = created_at WHERE started_at IS NULL")
    op.alter_column(
        "recording",
        "started_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "recording",
        "started_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        nullable=True,
    )
