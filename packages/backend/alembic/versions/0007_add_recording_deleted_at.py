"""recording.deleted_at — soft-deletion timestamp for retention cleanup (slice-11).

Revision ID: 0007_add_recording_deleted_at
Revises: 0006_create_summary
Create Date: 2026-05-11

Per slice-11 design Decision 5:
- NULL = recording wav is still on disk (current default for all rows)
- NOT NULL = retention cleanup has unlinked the wav at this timestamp;
  the row itself is preserved as a historical record
- No backfill: every existing row keeps `deleted_at IS NULL`
- No index: cleanup runs daily as a background sweep, not a hot path
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_add_recording_deleted_at"
down_revision: str | None = "0006_create_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recording",
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("recording", "deleted_at")
