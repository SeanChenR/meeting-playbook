"""Verify the create_playbook Alembic migration matches the spec schema.

Per design.md (slice-04-playbook-editor) — Decision: Alembic migration:
playbook table schema. The schema invariants this test pins down:

- All seven content columns + meeting_id + created_at + updated_at exist
  and are NOT NULL with appropriate defaults
- UNIQUE(meeting_id) — at most one playbook per meeting
- FK meeting_id -> meeting(id) ON DELETE CASCADE
- Inserting a second playbook for the same meeting violates the UNIQUE
  constraint (exercises Requirement: "Each meeting has at most one
  playbook scoped to that meeting")
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

_EXPECTED_COLUMNS = {
    "id",
    "meeting_id",
    "free_form_markdown",
    "objective",
    "counterparty_profile",
    "anticipated_topics",
    "anticipated_objections",
    "talking_points",
    "red_lines",
    "created_at",
    "updated_at",
    # Slice-20c: nullable on legacy rows; treated as empty-set canonical hash.
    "attachment_hash_snapshot",
    # Slice-23: previous-version snapshot (all nullable); only the
    # regenerate path + discard/restore endpoints touch these.
    "previous_free_form_markdown",
    "previous_updated_at",
    "previous_attachment_hash_snapshot",
}

# Slice-20c + slice-23: only the snapshot columns are nullable; the rest are NOT NULL.
_NULLABLE_COLUMNS = {
    "attachment_hash_snapshot",
    "previous_free_form_markdown",
    "previous_updated_at",
    "previous_attachment_hash_snapshot",
}
_NOT_NULL_COLUMNS = _EXPECTED_COLUMNS - _NULLABLE_COLUMNS


@pytest.mark.asyncio
async def test_playbook_table_exists_with_expected_columns(migrated_engine: AsyncEngine):
    """Migration creates `playbook` with every spec'd column NOT NULL."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'playbook'
                """
            )
        )
        columns = {row.column_name: row.is_nullable for row in rows}

    assert set(columns) == _EXPECTED_COLUMNS, (
        f"Unexpected playbook columns. extra={set(columns) - _EXPECTED_COLUMNS}, "
        f"missing={_EXPECTED_COLUMNS - set(columns)}"
    )
    nulls = {col: nullable for col, nullable in columns.items() if nullable == "NO"}
    assert set(nulls) == _NOT_NULL_COLUMNS


@pytest.mark.asyncio
async def test_playbook_meeting_id_fk_cascades_on_delete(migrated_engine: AsyncEngine):
    """playbook.meeting_id -> meeting.id ON DELETE CASCADE."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT confdeltype
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_class ref ON c.confrelid = ref.oid
                WHERE t.relname = 'playbook'
                  AND c.contype = 'f'
                  AND ref.relname = 'meeting'
                """
            )
        )
        fks = list(rows)

    assert fks, "Expected an FK from playbook.meeting_id to meeting.id"

    def _as_char(v: bytes | str) -> str:
        return v.decode() if isinstance(v, bytes) else v

    assert any(_as_char(row.confdeltype) == "c" for row in fks), (
        f"playbook.meeting_id FK is not ON DELETE CASCADE. fks={fks}"
    )


@pytest.mark.asyncio
async def test_playbook_meeting_id_is_unique(migrated_engine: AsyncEngine):
    """Inserting a second playbook for the same meeting violates UNIQUE."""
    async with migrated_engine.begin() as conn:
        # Provide a user + meeting to satisfy FKs.
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('u_pb_unique', 'U', 'u_pb_unique@example.com', true)
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
                VALUES ('m_pb_unique', 'u_pb_unique', 'T', 'C', 'M')
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO playbook (id, meeting_id)
                VALUES ('pb_first', 'm_pb_unique')
                """
            )
        )

    async with migrated_engine.connect() as conn:
        with pytest.raises(IntegrityError):
            async with conn.begin():
                await conn.execute(
                    text(
                        """
                        INSERT INTO playbook (id, meeting_id)
                        VALUES ('pb_second', 'm_pb_unique')
                        """
                    )
                )


@pytest.mark.asyncio
async def test_playbook_content_columns_default_to_empty_string(migrated_engine: AsyncEngine):
    """Inserting only id + meeting_id leaves the seven content fields as ''."""
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('u_pb_default', 'U', 'u_pb_default@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
                VALUES ('m_pb_default', 'u_pb_default', 'T', 'C', 'M')
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO playbook (id, meeting_id)
                VALUES ('pb_default', 'm_pb_default')
                """
            )
        )
        row = (
            await conn.execute(
                text(
                    """
                    SELECT free_form_markdown, objective, counterparty_profile,
                           anticipated_topics, anticipated_objections,
                           talking_points, red_lines
                    FROM playbook WHERE id = 'pb_default'
                    """
                )
            )
        ).first()

    assert row is not None
    for value in row:
        assert value == "", f"Expected default empty string, got {value!r}"
