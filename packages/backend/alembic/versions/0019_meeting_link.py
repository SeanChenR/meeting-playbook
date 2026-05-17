"""create meeting_link table — slice-21 manual related-meetings linking.

Revision ID: 0019_meeting_link
Revises: 0018_playbook_previous_snapshot
Create Date: 2026-05-15

Per slice-21 design *Schema: single-row + bidirectional Repository abstraction*:

- One DB row physically captures `(from_meeting_id, to_meeting_id)`. Bidirectional
  semantics are enforced in the application layer (`MeetingLinkRepository`).
- `link_type` is frozen to `'related'` in v1.1 (CHECK constraint). The column
  is pre-allocated so future v1.2 work can lift the CHECK to allow
  `'follow_up'` / `'prep_for'` without a column add.
- Pair-uniqueness is order-independent: a UNIQUE INDEX on
  `(LEAST(from_meeting_id, to_meeting_id), GREATEST(from_meeting_id, to_meeting_id))`
  collapses both `(A, B)` and `(B, A)` into a single key, so the second insert
  fails with `UniqueViolation` regardless of direction.
- Both FK columns CASCADE on delete: dropping a meeting wipes its links.
- A CHECK forbids `from_meeting_id == to_meeting_id` at the DB level so the
  repository layer's `MeetingLinkSelfReference` is a defense-in-depth check.

Reserved number rationale: per parallel slice numbering (slice-17 attachments
took 0016/0017, slice-18 calendar preview reserved 0018), this migration is
slice-21 and lands at 0019. `down_revision` skips the unused 0013/0016–0018
numbers and points straight at the slice-16 head `0015_chunk_text_edited_at`.

FK column type rationale: `meeting.id` is TEXT (shape `m_<urlsafe-token>` per
`MeetingRepository.create`), NOT a real UUID. To keep FK column types matching
their target columns, `meeting_link.from_meeting_id` and `to_meeting_id` are
TEXT. The `meeting_link.id` PK itself stays UUID — it is a new column not
constrained by existing schema. This is an inline judgment call vs the spec
wording which uses "UUID" for all three; see slice-21 design notes.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_meeting_link"
down_revision: str | None = "0018_playbook_previous_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting_link",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "from_meeting_id",
            sa.Text(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_meeting_id",
            sa.Text(),
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "link_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'related'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "from_meeting_id <> to_meeting_id",
            name="meeting_link_no_self_reference",
        ),
        sa.CheckConstraint(
            "link_type IN ('related')",
            name="meeting_link_link_type_check",
        ),
    )

    # Order-independent pair uniqueness — both (A, B) and (B, A) collapse to
    # the same (LEAST, GREATEST) key, so the second insert fails with
    # UniqueViolation regardless of which side called first.
    op.execute(
        """
        CREATE UNIQUE INDEX meeting_link_pair_uidx
            ON meeting_link (
                LEAST(from_meeting_id, to_meeting_id),
                GREATEST(from_meeting_id, to_meeting_id)
            )
        """
    )

    # Secondary B-tree indexes so the bidirectional list query
    # `WHERE from_meeting_id = :id OR to_meeting_id = :id` can use a
    # BitmapOr over two index scans instead of a seq scan.
    op.execute("CREATE INDEX meeting_link_from_meeting_id_idx ON meeting_link (from_meeting_id)")
    op.execute("CREATE INDEX meeting_link_to_meeting_id_idx ON meeting_link (to_meeting_id)")


def downgrade() -> None:
    # FK CASCADE means rows go away with the table; explicit index drops
    # are unnecessary because `DROP TABLE` removes them too, but keep an
    # IF EXISTS guard in case the migration is partially applied.
    op.execute("DROP INDEX IF EXISTS meeting_link_pair_uidx")
    op.execute("DROP INDEX IF EXISTS meeting_link_from_meeting_id_idx")
    op.execute("DROP INDEX IF EXISTS meeting_link_to_meeting_id_idx")
    op.drop_table("meeting_link")
