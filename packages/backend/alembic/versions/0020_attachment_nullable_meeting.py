"""meeting_attachment: nullable meeting_id + user_id column — slice-24 task 1.1.

Revision ID: 0020_attachment_nullable_meeting
Revises: 0019_meeting_link
Create Date: 2026-05-17

Renumbered from 0019 → 0020 after slice-21 (which also claimed 0019_meeting_link)
landed on main first. The schema change itself is unrelated to slice-21 —
this migration just sits on top of it in the chain.

Per slice-24 design D1 (sustain `meeting_attachment` + nullable meeting_id)
and D2 (add `user_id` column on `meeting_attachment` for staged-row
ownership scoping when `meeting_id IS NULL`):

Upgrade steps:
  1. ALTER `meeting_attachment.meeting_id` DROP NOT NULL — staged rows
     (meeting_id IS NULL) become legal.
  2. ADD COLUMN `user_id TEXT NOT NULL DEFAULT ''` — temp default so the
     ADD COLUMN does not fail on existing rows.
  3. UPDATE backfill `user_id` from the row's existing `meeting.user_id`
     via JOIN. After backfill, every row has a non-empty user_id.
  4. ALTER `user_id` DROP DEFAULT — prevent future inserts from sneaking
     in an empty string.
  5. ADD FK CONSTRAINT user_id → user.id (no ON DELETE rule; Better Auth
     owns user deletion semantics).
  6. CREATE INDEX `meeting_attachment_user_meeting_uploaded_idx`
     ON `(user_id, meeting_id, uploaded_at DESC)` — speeds up the
     staging-list query `WHERE user_id = ? AND meeting_id IS NULL`
     and the per-meeting list query alike.

Downgrade is data-destructive for staged rows:
  1. DELETE WHERE meeting_id IS NULL — clears the orphan rows the new
     nullable schema permitted. SET NOT NULL would otherwise fail on
     any staged row.
  2. DROP INDEX `meeting_attachment_user_meeting_uploaded_idx`.
  3. DROP FK on user_id, DROP COLUMN user_id.
  4. ALTER `meeting_id` SET NOT NULL — restores the pre-slice-24 shape.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_attachment_nullable_meeting"
down_revision: str | None = "0019_meeting_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. meeting_id becomes nullable so staged rows can exist.
    op.alter_column(
        "meeting_attachment",
        "meeting_id",
        existing_type=sa.Text(),
        nullable=True,
    )

    # 2. Add user_id with a temp default so the ADD COLUMN succeeds on
    #    existing rows. PostgreSQL fills every existing row with `''`
    #    instantly thanks to the constant default.
    op.add_column(
        "meeting_attachment",
        sa.Column("user_id", sa.Text(), nullable=False, server_default=""),
    )

    # 3. Backfill user_id from the row's meeting (every existing row has
    #    meeting_id IS NOT NULL at this point; staged rows did not yet
    #    exist).
    op.execute(
        """
        UPDATE meeting_attachment ma
           SET user_id = m.user_id
          FROM meeting m
         WHERE ma.meeting_id = m.id
        """
    )

    # 4. Drop the temp default so future inserts MUST supply user_id.
    op.alter_column(
        "meeting_attachment",
        "user_id",
        existing_type=sa.Text(),
        server_default=None,
    )

    # 5. Add the FK to user.id. No ON DELETE rule — Better Auth manages
    #    user deletion and handles its own cascade semantics for
    #    auth-owned tables.
    op.create_foreign_key(
        "meeting_attachment_user_id_fkey",
        "meeting_attachment",
        "user",
        ["user_id"],
        ["id"],
    )

    # 6. Composite index for the two main lookup paths:
    #    - list staged for user: WHERE user_id = ? AND meeting_id IS NULL
    #    - list attached for meeting + scope by owner.
    op.execute(
        """
        CREATE INDEX meeting_attachment_user_meeting_uploaded_idx
            ON meeting_attachment (user_id, meeting_id, uploaded_at DESC)
        """
    )


def downgrade() -> None:
    # 1. Purge staged rows so SET NOT NULL succeeds.
    op.execute("DELETE FROM meeting_attachment WHERE meeting_id IS NULL")

    # 2. Drop the composite index.
    op.execute("DROP INDEX IF EXISTS meeting_attachment_user_meeting_uploaded_idx")

    # 3. Drop FK + column.
    op.drop_constraint(
        "meeting_attachment_user_id_fkey",
        "meeting_attachment",
        type_="foreignkey",
    )
    op.drop_column("meeting_attachment", "user_id")

    # 4. Restore meeting_id NOT NULL.
    op.alter_column(
        "meeting_attachment",
        "meeting_id",
        existing_type=sa.Text(),
        nullable=False,
    )
