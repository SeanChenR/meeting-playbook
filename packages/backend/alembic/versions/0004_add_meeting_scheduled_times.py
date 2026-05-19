"""add meeting.scheduled_start_at + scheduled_end_at.

Revision ID: 0004_add_meeting_scheduled_times
Revises: 0003_create_session_tables
Create Date: 2026-05-10

Per design.md (slice-07-dualstream-and-ui-bundle): the `meeting` table needs
two optional timestamp columns capturing when a meeting is *planned* to occur
(distinct from `created_at` / `started_at` / `ended_at`). These are required
by the new calendar view (which renders meetings on a month/week grid) and
are populated automatically by the Calendar import endpoint. Existing rows
remain NULL — no backfill.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_add_meeting_scheduled_times"
down_revision: str | Sequence[str] | None = "0003_create_session_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meeting",
        sa.Column("scheduled_start_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "meeting",
        sa.Column("scheduled_end_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("meeting", "scheduled_end_at")
    op.drop_column("meeting", "scheduled_start_at")
