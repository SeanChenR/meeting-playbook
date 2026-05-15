"""Verify the create_tag_system Alembic migration produces the expected schema.

Per slice-17-tag-system design.md "Schema: `tag` + `meeting_tag` 雙表,
case-insensitive uniqueness 用 expression index":

- `tag(id, user_id, name, color, created_at)` with FK → user(id) CASCADE
- Expression unique index `(user_id, lower(name))` so the case-insensitive
  uniqueness is enforced at the DB layer (not application).
- `meeting_tag(meeting_id, tag_id, attached_at)` with composite PK and
  ON DELETE CASCADE on BOTH foreign keys.

The migration is exercised by the standard `migrated_engine` fixture which
runs `downgrade base → upgrade head` per session, so the up/down reversibility
is implicitly covered. This test additionally pins the schema invariants.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_tag_table_exists_with_expected_columns(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'tag'
                """
            )
        )
        columns = {row.column_name: row.is_nullable for row in rows}

    expected = {"id", "user_id", "name", "color", "created_at"}
    assert set(columns) == expected, (
        f"Unexpected tag columns. extra={set(columns) - expected}, "
        f"missing={expected - set(columns)}"
    )
    # All five are NOT NULL.
    assert all(v == "NO" for v in columns.values()), columns


@pytest.mark.asyncio
async def test_tag_unique_expression_index_on_user_id_lower_name(migrated_engine: AsyncEngine):
    """Expression unique index that case-folds the name guarantees the
    "客戶X / 客戶x" two-writers race can never persist twice."""
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT indexdef FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'tag'
                """
            )
        )
        defs = [row.indexdef for row in rows]

    matching = [
        d for d in defs if "user_id" in d and "lower" in d.lower() and "UNIQUE" in d.upper()
    ]
    assert matching, f"No UNIQUE (user_id, lower(name)) index on tag. indexes={defs}"


@pytest.mark.asyncio
async def test_tag_user_id_fk_cascades(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT confdeltype
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_class ref ON c.confrelid = ref.oid
                WHERE t.relname = 'tag'
                  AND c.contype = 'f'
                  AND ref.relname = 'user'
                """
            )
        )
        fks = list(rows)
    assert fks, "Expected an FK from tag.user_id to user.id"

    def _c(v: bytes | str) -> str:
        return v.decode() if isinstance(v, bytes) else v

    assert any(_c(row.confdeltype) == "c" for row in fks), (
        f"tag.user_id FK is not ON DELETE CASCADE. fks={fks}"
    )


@pytest.mark.asyncio
async def test_meeting_tag_table_columns_and_composite_pk(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        cols = await conn.execute(
            text(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'meeting_tag'
                """
            )
        )
        columns = {row.column_name: row.is_nullable for row in cols}
    expected = {"meeting_id", "tag_id", "attached_at"}
    assert set(columns) == expected, columns
    assert all(v == "NO" for v in columns.values()), columns

    # Composite primary key on (meeting_id, tag_id).
    async with migrated_engine.connect() as conn:
        pk_rows = await conn.execute(
            text(
                """
                SELECT a.attname
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                WHERE t.relname = 'meeting_tag' AND c.contype = 'p'
                ORDER BY a.attname
                """
            )
        )
        pk = sorted(r.attname for r in pk_rows)
    assert pk == ["meeting_id", "tag_id"], pk


@pytest.mark.asyncio
async def test_meeting_tag_fks_cascade_both_directions(migrated_engine: AsyncEngine):
    async with migrated_engine.connect() as conn:
        fk_rows = await conn.execute(
            text(
                """
                SELECT ref.relname AS target, c.confdeltype
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_class ref ON c.confrelid = ref.oid
                WHERE t.relname = 'meeting_tag' AND c.contype = 'f'
                """
            )
        )
        fks = {r.target: r.confdeltype for r in fk_rows}

    def _c(v: bytes | str) -> str:
        return v.decode() if isinstance(v, bytes) else v

    assert {"meeting", "tag"} <= set(fks), fks
    assert _c(fks["meeting"]) == "c", "meeting_tag.meeting_id FK is not ON DELETE CASCADE"
    assert _c(fks["tag"]) == "c", "meeting_tag.tag_id FK is not ON DELETE CASCADE"
