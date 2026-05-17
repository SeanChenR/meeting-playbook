"""meeting_attachment table — slice-20a task 1.1.

Revision ID: 0016_meeting_attachment
Revises: 0015_chunk_text_edited_at
Create Date: 2026-05-15

Per slice-20a design "Schema：`meeting_attachment` 獨立表 + `kind` enum":
- New table `meeting_attachment` carries per-meeting attachment metadata.
- FK on `meeting_id` ON DELETE CASCADE — deleting a meeting wipes its
  attachments automatically.
- `kind` is constrained via a CHECK constraint (not a pg enum type) so
  S20c can extend the set without an `ALTER TYPE` migration.
- `bytes > 0` CHECK keeps zero-size uploads out of the table.
- Composite index `(meeting_id, deleted_at)` supports the list endpoint
  query `WHERE meeting_id = ? AND deleted_at IS NULL`.
- Downgrade drops the table cleanly.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_meeting_attachment"
down_revision: str | None = "0015_chunk_text_edited_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting_attachment",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Text(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "deleted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "kind IN ('image', 'pdf', 'docx', 'text', 'markdown')",
            name="meeting_attachment_kind_check",
        ),
        sa.CheckConstraint(
            "bytes > 0",
            name="meeting_attachment_bytes_positive_check",
        ),
    )
    op.create_index(
        "meeting_attachment_meeting_id_deleted_at_idx",
        "meeting_attachment",
        ["meeting_id", "deleted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "meeting_attachment_meeting_id_deleted_at_idx",
        table_name="meeting_attachment",
    )
    op.drop_table("meeting_attachment")
