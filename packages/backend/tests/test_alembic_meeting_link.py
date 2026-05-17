"""Verify migration 0019 creates the `meeting_link` table — slice 21 task 1.1.

Per spec `meeting_link table stores one row per bidirectional related-meetings pair`:
- id UUID PRIMARY KEY default gen_random_uuid()
- from_meeting_id UUID NOT NULL REFERENCES meeting(id) ON DELETE CASCADE
- to_meeting_id UUID NOT NULL REFERENCES meeting(id) ON DELETE CASCADE
- link_type TEXT NOT NULL DEFAULT 'related', CHECK (link_type IN ('related'))
- created_at TIMESTAMPTZ NOT NULL DEFAULT now()
- CHECK (from_meeting_id <> to_meeting_id)
- UNIQUE INDEX on (LEAST(from_meeting_id, to_meeting_id), GREATEST(...))
- Secondary B-tree indexes on from_meeting_id and to_meeting_id
- Migration is reversible (downgrade drops the table)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import command

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_config(url: str) -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    return cfg


def _async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.mark.asyncio
async def test_meeting_link_table_exists_at_head(migrated_engine: AsyncEngine) -> None:
    """At HEAD, the `meeting_link` table exists with the spec'd columns."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'meeting_link'
                    ORDER BY column_name
                    """
                )
            )
        ).all()
    by_name = {r.column_name: r for r in rows}

    # id: UUID PK with gen_random_uuid() default — the meeting_link row's own id
    assert "id" in by_name, "meeting_link.id missing"
    assert by_name["id"].data_type == "uuid"
    assert by_name["id"].is_nullable == "NO"

    # from_meeting_id / to_meeting_id: must MATCH meeting.id which is TEXT
    # (meeting.id has shape `m_<urlsafe-token>` per MeetingRepository.create,
    # NOT a UUID despite the spec wording). FK columns must match target
    # column type, so we use TEXT here. Documented inline as a judgment
    # call vs spec wording — see slice-21 design.md "Implementation Contract".
    assert "from_meeting_id" in by_name
    assert by_name["from_meeting_id"].data_type == "text"
    assert by_name["from_meeting_id"].is_nullable == "NO"

    assert "to_meeting_id" in by_name
    assert by_name["to_meeting_id"].data_type == "text"
    assert by_name["to_meeting_id"].is_nullable == "NO"

    # link_type: TEXT NOT NULL with default
    assert "link_type" in by_name
    assert by_name["link_type"].data_type == "text"
    assert by_name["link_type"].is_nullable == "NO"

    # created_at: TIMESTAMPTZ NOT NULL with default now()
    assert "created_at" in by_name
    assert by_name["created_at"].data_type == "timestamp with time zone"
    assert by_name["created_at"].is_nullable == "NO"


@pytest.mark.asyncio
async def test_meeting_link_fks_cascade(migrated_engine: AsyncEngine) -> None:
    """Both `from_meeting_id` and `to_meeting_id` FKs SHALL CASCADE on delete."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT a.attname AS col, c.confdeltype
                    FROM pg_constraint c
                    JOIN pg_attribute a
                      ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
                    WHERE c.conrelid = 'meeting_link'::regclass
                      AND c.contype = 'f'
                    """
                )
            )
        ).all()
    assert len(rows) >= 2, "meeting_link should have FKs on from_meeting_id and to_meeting_id"
    for r in rows:
        actual = r.confdeltype
        expected = (b"c", "c")
        assert actual in expected, f"FK on {r.col} must cascade on delete; got {actual!r}"


@pytest.mark.asyncio
async def test_meeting_link_has_self_reference_check(migrated_engine: AsyncEngine) -> None:
    """A CHECK constraint MUST forbid `from_meeting_id == to_meeting_id`."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(oid) AS constraint_def
                    FROM pg_constraint
                    WHERE conrelid = 'meeting_link'::regclass
                      AND contype = 'c'
                      AND conname = 'meeting_link_no_self_reference'
                    """
                )
            )
        ).first()
    assert row is not None, "meeting_link_no_self_reference CHECK missing"
    assert "from_meeting_id" in row.constraint_def
    assert "to_meeting_id" in row.constraint_def


@pytest.mark.asyncio
async def test_meeting_link_has_link_type_check(migrated_engine: AsyncEngine) -> None:
    """A CHECK constraint MUST restrict `link_type` to {'related'} in v1.1."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(oid) AS constraint_def
                    FROM pg_constraint
                    WHERE conrelid = 'meeting_link'::regclass
                      AND contype = 'c'
                      AND conname = 'meeting_link_link_type_check'
                    """
                )
            )
        ).first()
    assert row is not None, "meeting_link_link_type_check missing"
    assert "related" in row.constraint_def


@pytest.mark.asyncio
async def test_meeting_link_has_unique_pair_index(migrated_engine: AsyncEngine) -> None:
    """A unique index on (LEAST, GREATEST) MUST enforce order-independent dedupe."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'meeting_link'
                      AND indexname = 'meeting_link_pair_uidx'
                    """
                )
            )
        ).first()
    assert row is not None, "meeting_link_pair_uidx index missing"
    indexdef = row.indexdef
    # The index expression must include both LEAST and GREATEST over the
    # meeting id pair so forward+reverse inserts collapse to the same key.
    assert "LEAST" in indexdef.upper()
    assert "GREATEST" in indexdef.upper()
    assert "UNIQUE" in indexdef.upper()


@pytest.mark.asyncio
async def test_meeting_link_has_secondary_indexes(migrated_engine: AsyncEngine) -> None:
    """B-tree indexes on `from_meeting_id` and `to_meeting_id` MUST exist."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'meeting_link'
                    """
                )
            )
        ).all()
    names = {r.indexname for r in rows}
    assert "meeting_link_from_meeting_id_idx" in names, (
        f"meeting_link_from_meeting_id_idx missing; have {names}"
    )
    assert "meeting_link_to_meeting_id_idx" in names, (
        f"meeting_link_to_meeting_id_idx missing; have {names}"
    )


@pytest.mark.asyncio
async def test_meeting_link_migration_is_reversible(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run upgrade → downgrade → upgrade three times — schema must come/go cleanly."""
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = _async_url(test_database_url)
    engine = create_async_engine(async_url, future=True)

    async def _table_exists() -> bool:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = 'meeting_link'
                        """
                    )
                )
            ).first()
        return row is not None

    try:
        # We start at HEAD (the migrated_engine session-fixture pre-runs it).
        assert await _table_exists(), "meeting_link should exist at HEAD"

        # Round 1: downgrade past 0019 → table gone.
        await asyncio.to_thread(command.downgrade, cfg, "0015_chunk_text_edited_at")
        assert not await _table_exists(), "meeting_link should not exist after downgrade"

        # Round 2: upgrade → table back.
        await asyncio.to_thread(command.upgrade, cfg, "head")
        assert await _table_exists(), "meeting_link should exist after re-upgrade"

        # Round 3: downgrade again to confirm idempotent behavior.
        await asyncio.to_thread(command.downgrade, cfg, "0015_chunk_text_edited_at")
        assert not await _table_exists(), "meeting_link should not exist after second downgrade"

        # Restore HEAD for the rest of the test session.
        await asyncio.to_thread(command.upgrade, cfg, "head")
        assert await _table_exists(), "meeting_link restored at end of test"
    finally:
        await engine.dispose()
