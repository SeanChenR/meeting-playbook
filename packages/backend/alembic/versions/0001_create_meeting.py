"""create meeting table.

Revision ID: 0001_create_meeting
Revises:
Create Date: 2026-05-07

Per design.md (slice-03-meeting-crud):
- TEXT id (compatible with Better Auth user.id)
- FK on user_id ON DELETE CASCADE
- CHECK constraint on status (avoids PG enum alter pain)
- (user_id, created_at DESC) index supports the list-page primary query
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_create_meeting"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("counterparty_display_name", sa.Text(), nullable=False),
        sa.Column("me_display_name", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'scheduled'"),
        ),
        sa.Column(
            "asr_provider",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'whisper'"),
        ),
        sa.Column("calendar_event_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'completed')",
            name="meeting_status_check",
        ),
    )
    # Primary list-page query: SELECT … WHERE user_id = $1 ORDER BY created_at DESC.
    op.execute(
        "CREATE INDEX meeting_user_id_created_at_desc_idx ON meeting (user_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS meeting_user_id_created_at_desc_idx")
    op.drop_table("meeting")
