"""meeting.asr_provider default → qwen3 (slice-11).

Revision ID: 0008_asr_default_qwen3
Revises: 0007_add_recording_deleted_at
Create Date: 2026-05-11

Per slice-11 design Decision 2:
- Change ONLY the column DEFAULT clause from 'whisper' to 'qwen3'.
- Do NOT issue a UPDATE — pre-existing meetings stay 'whisper' so the
  meeting.asr_provider value reflects the engine that actually produced
  that meeting's transcript_chunk rows. (Sean can flip individual rows
  via the detail-page selector + re-run if he wants to upgrade them.)

Revision id was shortened from the original
`0008_meeting_asr_provider_default_qwen3` (41 chars) to fit Alembic's
default VARCHAR(32) `alembic_version.version_num` column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_asr_default_qwen3"
down_revision: str | None = "0007_add_recording_deleted_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "meeting",
        "asr_provider",
        server_default=sa.text("'qwen3'"),
        existing_type=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "meeting",
        "asr_provider",
        server_default=sa.text("'whisper'"),
        existing_type=sa.Text(),
        existing_nullable=False,
    )
