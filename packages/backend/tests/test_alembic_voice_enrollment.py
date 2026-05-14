"""Verify migration 0009 creates the `voice_enrollment` table — slice 13 task 1.1.

Per spec `voice_enrollment table stores one embedding per user`:
- user_id PRIMARY KEY referencing user.id with ON DELETE CASCADE
- sample_wav_path TEXT NOT NULL
- embedding BYTEA NOT NULL
- created_at TIMESTAMPTZ NOT NULL
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
async def test_voice_enrollment_table_exists_at_head(
    migrated_engine: AsyncEngine,
) -> None:
    """At HEAD, the `voice_enrollment` table exists with the spec'd columns."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'voice_enrollment'
                    ORDER BY column_name
                    """
                )
            )
        ).all()
    by_name = {r.column_name: r for r in rows}

    assert "user_id" in by_name, "voice_enrollment.user_id missing"
    assert by_name["user_id"].data_type == "text"
    assert by_name["user_id"].is_nullable == "NO"

    assert "sample_wav_path" in by_name
    assert by_name["sample_wav_path"].data_type == "text"
    assert by_name["sample_wav_path"].is_nullable == "NO"

    assert "embedding" in by_name
    # PostgreSQL reports BYTEA as 'bytea' in data_type.
    assert by_name["embedding"].data_type == "bytea"
    assert by_name["embedding"].is_nullable == "NO"

    assert "created_at" in by_name
    assert by_name["created_at"].data_type == "timestamp with time zone"
    assert by_name["created_at"].is_nullable == "NO"


@pytest.mark.asyncio
async def test_voice_enrollment_user_id_has_cascade_fk_to_user(
    migrated_engine: AsyncEngine,
) -> None:
    """The FK on user_id SHALL CASCADE on delete (per spec scenario
    'Deleting the user cascades to voice_enrollment')."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT confdeltype
                    FROM pg_constraint
                    WHERE conrelid = 'voice_enrollment'::regclass
                      AND contype = 'f'
                    LIMIT 1
                    """
                )
            )
        ).first()
    assert row is not None, "voice_enrollment has no foreign key"
    # 'c' = CASCADE in pg_constraint.confdeltype. asyncpg returns the
    # single-char field as bytes, so accept either b"c" or "c".
    actual = row.confdeltype
    expected = (b"c", "c")
    assert actual in expected, f"FK must cascade on delete; got {actual!r}"


@pytest.mark.asyncio
async def test_voice_enrollment_migration_is_reversible(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Downgrade removes the table; re-upgrade brings it back. Three rounds
    of upgrade → downgrade → upgrade succeed without leftover state.
    """
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
                          AND table_name = 'voice_enrollment'
                        """
                    )
                )
            ).first()
        return row is not None

    try:
        # We start at HEAD (the migrated_engine session-fixture pre-runs it).
        assert await _table_exists(), "voice_enrollment should exist at HEAD"

        # Round 1: downgrade past 0009 → table gone.
        await asyncio.to_thread(command.downgrade, cfg, "0008_asr_default_qwen3")
        assert not await _table_exists(), "voice_enrollment should not exist after downgrade"

        # Round 2: upgrade → table back.
        await asyncio.to_thread(command.upgrade, cfg, "head")
        assert await _table_exists(), "voice_enrollment should exist after re-upgrade"

        # Round 3: downgrade again to confirm idempotent behavior.
        await asyncio.to_thread(command.downgrade, cfg, "0008_asr_default_qwen3")
        assert not await _table_exists(), "voice_enrollment should not exist after second downgrade"

        # Restore HEAD for the rest of the test session.
        await asyncio.to_thread(command.upgrade, cfg, "head")
        assert await _table_exists(), "voice_enrollment restored at end of test"
    finally:
        await engine.dispose()
