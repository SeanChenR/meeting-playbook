"""create summary — per-meeting markdown summary (slice-10).

Revision ID: 0006_create_summary
Revises: 0005_create_chat_message
Create Date: 2026-05-11

Per design.md (slice-10-post-meeting-summary) Decision 1:
- 4-column schema (id, meeting_id, markdown, generated_at)
- UNIQUE constraint on meeting_id enforces 1:1 with meeting
- FK to meeting.id ON DELETE CASCADE so summary dies with the parent
- No status / error_code — failed generations don't write rows
  (same minimal-schema philosophy as slice-9 chat_message)
- Regenerate flow uses INSERT ... ON CONFLICT (meeting_id) DO UPDATE
  for atomic upsert at the SQL layer
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_create_summary"
down_revision: str | None = "0005_create_chat_message"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "summary",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column(
            "generated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("summary")
