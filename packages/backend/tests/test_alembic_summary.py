"""Verify the create_summary Alembic migration produces the expected schema.

Per design.md (slice-10-post-meeting-summary) Decision 1 — summary table:
- 4 columns (id, meeting_id, markdown, generated_at) — all NOT NULL
- FK from `meeting_id` → `meeting(id)` ON DELETE CASCADE
- UNIQUE constraint on `meeting_id` (1:1 with meeting)
- No status / error_code (failed generations don't write rows)
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

_EXPECTED_COLUMNS = {
    "id",
    "meeting_id",
    "markdown",
    "generated_at",
    # Slice-20c: nullable on legacy rows; treated as empty-set canonical hash.
    "attachment_hash_snapshot",
}
_NOT_NULL_COLUMNS = {"id", "meeting_id", "markdown", "generated_at"}


@pytest.mark.asyncio
async def test_summary_table_exists_with_expected_columns(migrated_engine: AsyncEngine):
    """Slice-10: migration creates `summary` with every spec'd column NOT NULL."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'summary'
                """
            )
        )
        columns = {row.column_name: row.is_nullable for row in rows}

    assert set(columns) == _EXPECTED_COLUMNS, (
        f"Unexpected summary columns. extra={set(columns) - _EXPECTED_COLUMNS}, "
        f"missing={_EXPECTED_COLUMNS - set(columns)}"
    )

    nulls = {col for col, nullable in columns.items() if nullable == "NO"}
    assert nulls == _NOT_NULL_COLUMNS, (
        f"NOT NULL columns drifted from spec. got={nulls}, expected={_NOT_NULL_COLUMNS}"
    )


@pytest.mark.asyncio
async def test_summary_meeting_id_unique_constraint(migrated_engine: AsyncEngine):
    """Slice-10: UNIQUE (meeting_id) enforces 1:1 with meeting."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT conname, contype
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                WHERE t.relname = 'summary' AND contype IN ('u', 'p')
                """
            )
        )
        constraints = [(r.conname, r.contype) for r in rows]

    # Either a unique constraint OR a unique index covering meeting_id is acceptable.
    has_unique = any(
        contype == "u" or "meeting_id" in name.lower() for name, contype in constraints
    )
    if not has_unique:
        # Fallback: check pg_indexes for unique index on meeting_id
        async with migrated_engine.connect() as conn:
            idx_rows = await conn.execute(
                text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = 'summary'
                      AND indexdef ILIKE '%UNIQUE%'
                      AND indexdef ILIKE '%meeting_id%'
                    """
                )
            )
            unique_indexes = list(idx_rows)
        assert unique_indexes, (
            f"Expected UNIQUE on summary.meeting_id; got constraints={constraints} and no unique index"
        )


@pytest.mark.asyncio
async def test_summary_meeting_id_fk_cascades_on_delete(migrated_engine: AsyncEngine):
    """Slice-10: summary.meeting_id → meeting.id ON DELETE CASCADE."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT confdeltype, conname
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_class ref ON c.confrelid = ref.oid
                WHERE t.relname = 'summary'
                  AND c.contype = 'f'
                  AND ref.relname = 'meeting'
                """
            )
        )
        fks = list(rows)

    assert fks, "Expected an FK from summary.meeting_id to meeting.id"

    def _as_char(v: bytes | str) -> str:
        return v.decode() if isinstance(v, bytes) else v

    assert any(_as_char(row.confdeltype) == "c" for row in fks), (
        f"summary.meeting_id FK is not ON DELETE CASCADE. fks={fks}"
    )
