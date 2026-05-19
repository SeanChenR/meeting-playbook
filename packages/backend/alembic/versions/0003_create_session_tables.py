"""create session tables — transcript_chunk + recording, plus meeting.updated_at.

Revision ID: 0003_create_session_tables
Revises: 0002_create_playbook
Create Date: 2026-05-09

Per design.md (slice-06-mic-transcript-session):
- `transcript_chunk` stores one row per ~10s ASR chunk; `speaker` is a free
  text column with CHECK constraint so slice-7 can add `'counterparty'`
  without a migration; FK ON DELETE CASCADE so playbook + transcript +
  recording rows die with the parent meeting.
- `recording` stores one WAV-file pointer per stream per meeting (one row
  per meeting in slice-6, two in slice-7).
- `meeting.updated_at` is added so `MeetingRepository.transition_status`
  can record when status last changed; the column is nullable for the
  back-fill on existing rows but defaulted to now() for new inserts.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_create_session_tables"
down_revision: str | None = "0002_create_playbook"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add updated_at to meeting; back-fill existing rows with created_at.
    op.add_column(
        "meeting",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.execute("UPDATE meeting SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("meeting", "updated_at", nullable=False)

    # transcript_chunk
    op.create_table(
        "transcript_chunk",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("asr_provider_used", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "speaker IN ('me', 'counterparty', 'system')",
            name="transcript_chunk_speaker_check",
        ),
    )
    op.create_index(
        "transcript_chunk_meeting_started_idx",
        "transcript_chunk",
        ["meeting_id", "started_at"],
    )

    # recording
    op.create_table(
        "recording",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.String(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stream", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "stream IN ('me', 'counterparty')",
            name="recording_stream_check",
        ),
        sa.UniqueConstraint("meeting_id", "stream", name="recording_meeting_stream_unique"),
    )


def downgrade() -> None:
    op.drop_table("recording")
    op.drop_index("transcript_chunk_meeting_started_idx", table_name="transcript_chunk")
    op.drop_table("transcript_chunk")
    op.drop_column("meeting", "updated_at")
