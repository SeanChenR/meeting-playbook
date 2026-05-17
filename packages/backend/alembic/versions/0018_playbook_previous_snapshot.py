"""playbook previous-version snapshot columns — slice-23 task 1.1.

Revision ID: 0018_playbook_previous_snapshot
Revises: 0017_attachment_hash_snapshot
Create Date: 2026-05-17

Per slice-23 design D1 "Snapshot 存在 row column 不另開表":
- ADD COLUMN `previous_free_form_markdown TEXT NULL` to `playbook`
- ADD COLUMN `previous_updated_at TIMESTAMPTZ NULL` to `playbook`
- ADD COLUMN `previous_attachment_hash_snapshot TEXT NULL` to `playbook`

Legacy rows naturally land at `previous_* = NULL` (no backfill), which the
application layer treats as "no previous version exists". Only the
regenerate path writes these columns; user-save upserts MUST leave them
untouched per spec `playbook-management`.

Downgrade drops the three columns. The drop is data-destructive (snapshot
state is lost) but the rest of the row stays intact, so the schema is
backward-compatible with slice-20c behavior.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_playbook_previous_snapshot"
down_revision: str | None = "0017_attachment_hash_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "playbook",
        sa.Column("previous_free_form_markdown", sa.Text(), nullable=True),
    )
    op.add_column(
        "playbook",
        sa.Column("previous_updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "playbook",
        sa.Column("previous_attachment_hash_snapshot", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("playbook", "previous_attachment_hash_snapshot")
    op.drop_column("playbook", "previous_updated_at")
    op.drop_column("playbook", "previous_free_form_markdown")
