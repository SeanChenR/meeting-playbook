"""Verify the create_chat_message Alembic migration produces the expected schema.

Per design.md (slice-09-advisor-chatbox) Decision 1 — chat_message table:
- 5 columns (id, meeting_id, role, content, created_at) — all NOT NULL
- FK from `meeting_id` → `meeting(id)` ON DELETE CASCADE
- CHECK constraint on `role IN ('user', 'advisor')`
- Composite index `chat_message_meeting_created_idx` on `(meeting_id, created_at)`
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

_EXPECTED_COLUMNS = {"id", "meeting_id", "role", "content", "created_at"}
_NOT_NULL_COLUMNS = {"id", "meeting_id", "role", "content", "created_at"}


@pytest.mark.asyncio
async def test_chat_message_table_exists_with_expected_columns(migrated_engine: AsyncEngine):
    """Migration creates `chat_message` with every spec'd column NOT NULL."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'chat_message'
                """
            )
        )
        columns = {row.column_name: row.is_nullable for row in rows}

    assert set(columns) == _EXPECTED_COLUMNS, (
        f"Unexpected chat_message columns. extra={set(columns) - _EXPECTED_COLUMNS}, "
        f"missing={_EXPECTED_COLUMNS - set(columns)}"
    )

    nulls = {col for col, nullable in columns.items() if nullable == "NO"}
    assert nulls == _NOT_NULL_COLUMNS, (
        f"NOT NULL columns drifted from spec. got={nulls}, expected={_NOT_NULL_COLUMNS}"
    )


@pytest.mark.asyncio
async def test_chat_message_role_check_constraint_enforces_enum(migrated_engine: AsyncEngine):
    """`role` CHECK constraint accepts only 'user' and 'advisor'."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid) AS def
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'chat_message' AND c.contype = 'c'
                """
            )
        )
        defs = [row.def_ if hasattr(row, "def_") else row[0] for row in rows]

    joined = " ".join(defs).lower()
    assert "user" in joined and "advisor" in joined, (
        f"chat_message.role CHECK constraint missing required enum values. defs={defs}"
    )


@pytest.mark.asyncio
async def test_chat_message_meeting_id_fk_cascades_on_delete(migrated_engine: AsyncEngine):
    """chat_message.meeting_id → meeting.id ON DELETE CASCADE."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT confdeltype, conname
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_class ref ON c.confrelid = ref.oid
                WHERE t.relname = 'chat_message'
                  AND c.contype = 'f'
                  AND ref.relname = 'meeting'
                """
            )
        )
        fks = list(rows)

    assert fks, "Expected an FK from chat_message.meeting_id to meeting.id"

    def _as_char(v: bytes | str) -> str:
        return v.decode() if isinstance(v, bytes) else v

    assert any(_as_char(row.confdeltype) == "c" for row in fks), (
        f"chat_message.meeting_id FK is not ON DELETE CASCADE. fks={fks}"
    )


@pytest.mark.asyncio
async def test_chat_message_composite_index_on_meeting_id_created_at(migrated_engine: AsyncEngine):
    """`(meeting_id, created_at)` composite index exists with the expected name."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'chat_message'
                """
            )
        )
        idx = {row.indexname: row.indexdef for row in rows}

    assert "chat_message_meeting_created_idx" in idx, (
        f"Expected `chat_message_meeting_created_idx` index, got {list(idx)}"
    )
    defn = idx["chat_message_meeting_created_idx"].lower()
    assert "meeting_id" in defn and "created_at" in defn, (
        f"Index does not cover (meeting_id, created_at). def={defn}"
    )
