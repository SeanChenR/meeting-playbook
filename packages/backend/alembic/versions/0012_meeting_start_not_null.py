"""meeting.scheduled_start_at — backfill from created_at + SET NOT NULL (slice-15).

Revision ID: 0012_meeting_start_not_null
Revises: 0011_recording_source_started
Create Date: 2026-05-15

Per slice-15 design Decision *Migration `0012_meeting_start_not_null`*:
- Pre-existing rows where `scheduled_start_at IS NULL` (created before
  slice-7 added the column, or rows that bypassed the form validation)
  get back-filled with their `created_at` value — preserves the row
  count + gives downstream UI a non-null timestamp to sort by.
- After backfill, the column becomes `NOT NULL` so the meetings-list /
  Kanban / calendar views can drop their `?? created_at` fallback.
- Downgrade only drops `NOT NULL`; back-filled values stay (data is not
  reverted to NULL because we cannot recover which rows were NULL pre-
  upgrade).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_meeting_start_not_null"
down_revision: str | None = "0011_recording_source_started"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE meeting SET scheduled_start_at = created_at WHERE scheduled_start_at IS NULL"
    )
    # NOT NULL + DEFAULT now(): the API enforces required at the Pydantic
    # boundary (`MeetingCreate` / `MeetingPatch`). The server-side default
    # is a safety net for legacy SQL paths (calendar import that lacks an
    # event start, direct repo inserts in tests) so the column never sees
    # a literal NULL — `meetings-card` / `kanban` / `calendar` can drop
    # their `?? created_at` fallback safely.
    op.alter_column(
        "meeting",
        "scheduled_start_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "meeting",
        "scheduled_start_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        nullable=True,
        server_default=None,
    )
