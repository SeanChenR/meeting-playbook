"""Verify migration 0015 adds `transcript_chunk.text_edited_at` (slice-16 task 1.1).

Per spec transcript-edit "transcript_chunk gains text_edited_at column
tracking user edits":

  (a) HEAD has the column nullable.
  (b) Newly inserted ASR chunks leave `text_edited_at = NULL`.
  (c) Down → up round-trip drops then re-creates the column.
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
async def test_text_edited_at_column_exists_and_is_nullable(
    migrated_engine: AsyncEngine,
) -> None:
    """At HEAD, `transcript_chunk.text_edited_at` exists and is nullable."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'transcript_chunk'
                      AND column_name = 'text_edited_at'
                    """
                )
            )
        ).first()
    assert row is not None, "transcript_chunk.text_edited_at column missing"
    assert row.is_nullable == "YES", f"text_edited_at MUST be nullable; got {row.is_nullable!r}"


@pytest.mark.asyncio
async def test_new_chunk_starts_with_null_text_edited_at(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Newly inserted ASR chunks leave text_edited_at NULL until a PATCH
    stamps it.
    """
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    async_url = _async_url(test_database_url)
    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO "user" (id, name, email, "emailVerified")
                    VALUES (:uid, :uid, :email, true)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"uid": "u_chunk_new", "email": "u_chunk_new@example.com"},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO meeting (
                        id, user_id, title, counterparty_display_name,
                        me_display_name, scheduled_start_at, created_at
                    )
                    VALUES (:mid, 'u_chunk_new', 'T', 'C', 'M', now(), now())
                    """
                ),
                {"mid": "m_chunk_new"},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO transcript_chunk (
                        id, meeting_id, speaker, text,
                        started_at, ended_at, asr_provider_used,
                        confidence, created_at
                    )
                    VALUES (
                        :cid, 'm_chunk_new', 'me', 'hello',
                        now(), now() + interval '1 second',
                        'qwen3', 0.95, now()
                    )
                    """
                ),
                {"cid": "c_new"},
            )

        async with engine.connect() as conn:
            edited = (
                await conn.execute(
                    text("SELECT text_edited_at FROM transcript_chunk WHERE id = :cid"),
                    {"cid": "c_new"},
                )
            ).scalar_one()
            assert edited is None, (
                f"newly-inserted chunk MUST have text_edited_at NULL; got {edited!r}"
            )

        async with engine.begin() as conn:
            await conn.execute(
                text('DELETE FROM "user" WHERE id = :uid'),
                {"uid": "u_chunk_new"},
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_downgrade_drops_column_then_reupgrade_succeeds(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Down → up cycle: downgrade drops text_edited_at, re-upgrade re-adds it."""
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = _async_url(test_database_url)

    await asyncio.to_thread(command.downgrade, cfg, "0014_recording_started_at")
    try:
        engine = create_async_engine(async_url, future=True)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'transcript_chunk'
                              AND column_name = 'text_edited_at'
                            """
                        )
                    )
                ).first()
            assert row is None, "After downgrade text_edited_at column MUST be dropped"
        finally:
            await engine.dispose()
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
