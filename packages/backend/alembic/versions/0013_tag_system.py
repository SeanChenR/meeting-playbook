"""create tag + meeting_tag tables — slice-17 tag system.

Revision ID: 0013_tag_system
Revises: 0012_meeting_start_not_null
Create Date: 2026-05-15

Per slice-17 design "Schema: `tag` + `meeting_tag` 雙表, case-insensitive
uniqueness 用 expression index":
- `tag` is the per-user tag definition; case-insensitive uniqueness is
  enforced at the DB level via a `(user_id, lower(name))` expression index
  so the "客戶X / 客戶x" race cannot persist twice.
- `meeting_tag` is the N:M junction; both FKs cascade so deleting a tag
  removes it from every meeting and deleting a meeting drops its tags.

Downgrade order: drop `meeting_tag` first (it FKs into `tag`), then `tag`.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_tag_system"
down_revision: str | None = "0012_meeting_start_not_null"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tag",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Expression unique index — case-insensitive name uniqueness per user.
    op.execute("CREATE UNIQUE INDEX uq_tag_user_lower_name ON tag (user_id, lower(name))")

    op.create_table(
        "meeting_tag",
        sa.Column(
            "meeting_id",
            sa.Text(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            sa.Text(),
            sa.ForeignKey("tag.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attached_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("meeting_id", "tag_id", name="meeting_tag_pkey"),
    )


def downgrade() -> None:
    op.drop_table("meeting_tag")
    op.execute("DROP INDEX IF EXISTS uq_tag_user_lower_name")
    op.drop_table("tag")
