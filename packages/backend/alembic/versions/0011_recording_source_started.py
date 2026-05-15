"""recording.source + recording.started_at — distinguish live vs offline + carry wall-clock origin (slice-14).

Revision ID: 0011_recording_source_started
Revises: 0010_relax_chunk_speaker_check
Create Date: 2026-05-15

Per slice-14 design Decision 4:
- `source` distinguishes live capture from offline ingest; existing rows
  back-fill to `'live'` via the server-side DEFAULT.
- `started_at` carries the wall-clock moment audio capture began. Live
  recordings will be back-filled in a future slice; offline ingest writes
  the user-supplied "actual_started_at" at insert time. Nullable here so
  pre-existing live recordings continue to round-trip.
- CHECK constraint pins `source` to the two-value enum so future code can
  pattern-match without defensive validation.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_recording_source_started"
down_revision: str | None = "0010_relax_chunk_speaker_check"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recording",
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'live'"),
        ),
    )
    op.create_check_constraint(
        "recording_source_check",
        "recording",
        "source IN ('live', 'offline')",
    )
    op.add_column(
        "recording",
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_constraint("recording_source_check", "recording", type_="check")
    op.drop_column("recording", "source")
    op.drop_column("recording", "started_at")
