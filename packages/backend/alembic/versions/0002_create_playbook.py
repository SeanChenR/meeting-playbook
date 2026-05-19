"""create playbook table.

Revision ID: 0002_create_playbook
Revises: 0001_create_meeting
Create Date: 2026-05-07

Per design.md (slice-04-playbook-editor):
- One playbook per meeting (UNIQUE meeting_id) tied to the meeting via FK +
  ON DELETE CASCADE
- Seven content fields stored as separate TEXT columns so Slice 5 (LLM
  generation) can set individual fields without round-tripping a JSON blob
- Content fields default to '' so the GET auto-create path inserts a row
  with no payload and the editor immediately has an editable surface
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_create_playbook"
down_revision: str | None = "0001_create_meeting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "playbook",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Text(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "free_form_markdown",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "objective",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "counterparty_profile",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "anticipated_topics",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "anticipated_objections",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "talking_points",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "red_lines",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("playbook")
