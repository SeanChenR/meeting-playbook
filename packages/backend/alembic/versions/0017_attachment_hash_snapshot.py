"""attachment_hash_snapshot columns on playbook + summary — slice-20c task 1.1.

Revision ID: 0017_attachment_hash_snapshot
Revises: 0016_meeting_attachment
Create Date: 2026-05-16

Per slice-20c design "Stale-tracking：附件集合 hash snapshot 寫進
playbook / summary row"：
- ADD COLUMN `attachment_hash_snapshot TEXT NULL` to `playbook` and
  `summary`. NULL on existing rows; the application layer treats NULL as
  "empty-set canonical hash" so legacy rows stay non-stale by default.
- Downgrade drops the columns cleanly.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_attachment_hash_snapshot"
down_revision: str | None = "0016_meeting_attachment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "playbook",
        sa.Column("attachment_hash_snapshot", sa.Text(), nullable=True),
    )
    op.add_column(
        "summary",
        sa.Column("attachment_hash_snapshot", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("summary", "attachment_hash_snapshot")
    op.drop_column("playbook", "attachment_hash_snapshot")
