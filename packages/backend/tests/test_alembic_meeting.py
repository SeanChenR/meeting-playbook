"""Verify the create_meeting Alembic migration produces the expected schema.

Per design.md (slice-03-meeting-crud) — Decision: Alembic migration: meeting table schema.

Schema invariants this test pins down:
- All columns present with the right types and nullability
- CHECK constraint on `status IN (scheduled, in_progress, completed)`
- Index on `(user_id, created_at DESC)`
- FK on `user_id → user(id) ON DELETE CASCADE`

The downgrade -1 case is exercised in `migrated_engine` fixture itself
(downgrade base + upgrade head on every session).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Expected schema in spec (design.md). Keep these in sync with the migration.
_EXPECTED_COLUMNS = {
    "id",
    "user_id",
    "title",
    "counterparty_display_name",
    "me_display_name",
    "status",
    "asr_provider",
    "calendar_event_id",
    "created_at",
    "updated_at",  # added in slice-06 migration 0003 to support transition_status
    "started_at",
    "ended_at",
    # added in slice-07 migration 0004 (calendar view + scheduled-import paths)
    "scheduled_start_at",
    "scheduled_end_at",
}

_NOT_NULL_COLUMNS = {
    "id",
    "user_id",
    "title",
    "counterparty_display_name",
    "me_display_name",
    "status",
    "asr_provider",
    "created_at",
    "updated_at",
}


@pytest.mark.asyncio
async def test_meeting_table_exists_with_expected_columns(migrated_engine: AsyncEngine):
    """Migration creates `meeting` with every spec'd column."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'meeting'
                """
            )
        )
        columns = {row.column_name: row.is_nullable for row in rows}

    assert set(columns) == _EXPECTED_COLUMNS, (
        f"Unexpected meeting columns. extra={set(columns) - _EXPECTED_COLUMNS}, "
        f"missing={_EXPECTED_COLUMNS - set(columns)}"
    )

    nulls = {col: nullable for col, nullable in columns.items() if nullable == "NO"}
    assert set(nulls) == _NOT_NULL_COLUMNS, (
        f"NOT NULL columns drifted from spec. got={set(nulls)}, expected={_NOT_NULL_COLUMNS}"
    )


@pytest.mark.asyncio
async def test_meeting_status_check_constraint_enforces_enum(migrated_engine: AsyncEngine):
    """`status` is constrained to scheduled / in_progress / completed."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid) AS def
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'meeting' AND c.contype = 'c'
                """
            )
        )
        defs = [row.def_ if hasattr(row, "def_") else row[0] for row in rows]

    joined = " ".join(defs).lower()
    assert "scheduled" in joined and "in_progress" in joined and "completed" in joined, (
        f"meeting.status CHECK constraint missing required enum values. defs={defs}"
    )


@pytest.mark.asyncio
async def test_meeting_user_id_fk_cascades_on_delete(migrated_engine: AsyncEngine):
    """meeting.user_id → user.id ON DELETE CASCADE."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT confdeltype, conname
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_class ref ON c.confrelid = ref.oid
                WHERE t.relname = 'meeting'
                  AND c.contype = 'f'
                  AND ref.relname = 'user'
                """
            )
        )
        fks = list(rows)

    assert fks, "Expected an FK from meeting.user_id to user.id"

    def _as_char(v: bytes | str) -> str:
        return v.decode() if isinstance(v, bytes) else v

    assert any(_as_char(row.confdeltype) == "c" for row in fks), (
        f"meeting.user_id FK is not ON DELETE CASCADE. fks={fks}"
    )


@pytest.mark.asyncio
async def test_meeting_user_created_at_index_is_descending(migrated_engine: AsyncEngine):
    """The (user_id, created_at DESC) covering index supports the list query."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT indexdef FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'meeting'
                """
            )
        )
        defs = [row.indexdef for row in rows]

    matching = [d for d in defs if "user_id" in d and "created_at" in d and "DESC" in d.upper()]
    assert matching, f"No (user_id, created_at DESC) index found on meeting. indexes={defs}"


@pytest.mark.asyncio
async def test_meeting_status_default_is_scheduled(migrated_engine: AsyncEngine):
    """Inserting without `status` defaults to 'scheduled'."""
    async with migrated_engine.begin() as conn:
        # Provide a user row to satisfy the FK.
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:id, :name, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": "u_default_test", "name": "U", "email": "u_default_test@example.com"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
                VALUES ('m_default_status', 'u_default_test', 'T', 'C', 'M')
                """
            )
        )
        row = (
            await conn.execute(
                text(
                    "SELECT status, asr_provider, calendar_event_id FROM meeting WHERE id = 'm_default_status'"
                )
            )
        ).first()

    assert row is not None
    assert row.status == "scheduled"
    # Slice-11 (migration 0008): default was flipped to 'qwen3'. Pre-existing
    # rows keep 'whisper'; new INSERTs without an explicit asr_provider land
    # on the new default.
    assert row.asr_provider == "qwen3"
    assert row.calendar_event_id is None
