"""create chat_message — per-meeting conversation history (slice-09).

Revision ID: 0005_create_chat_message
Revises: 0004_add_meeting_scheduled_times
Create Date: 2026-05-10

Per design.md (slice-09-advisor-chatbox) Decision 1:
- Five-column schema (id, meeting_id, role, content, created_at)
- FK to meeting.id ON DELETE CASCADE so chat history dies with the parent
- CHECK constraint on role IN ('user', 'advisor')
- Composite index (meeting_id, created_at) for chronological list queries
- No status / error_code — failed advice doesn't write rows (Decision 2)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_create_chat_message"
down_revision: str | None = "0004_add_meeting_scheduled_times"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_message",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "role IN ('user', 'advisor')",
            name="chat_message_role_check",
        ),
    )
    op.create_index(
        "chat_message_meeting_created_idx",
        "chat_message",
        ["meeting_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("chat_message_meeting_created_idx", table_name="chat_message")
    op.drop_table("chat_message")
