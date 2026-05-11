"""Verify migration 0008 changes meeting.asr_provider DEFAULT to 'qwen3'.

Per spec asr-provider-selection ADDED requirement
"Meeting.asr_provider defaults to qwen3 for new meetings" + Decision 2 of
slice-11 design ("不 back-fill 既有 row").

Two scenarios:
  (a) After migration, the column DEFAULT is 'qwen3' AND inserts without
      asr_provider land 'qwen3'. (Async — uses migrated_engine fixture.)
  (b) Rows that existed before 0008 (with the old 'whisper' default) keep
      their 'whisper' value — the migration MUST NOT issue a UPDATE.
      (Sync — drives Alembic CLI directly, which spawns its own event loop
      via env.py and can't nest under pytest-asyncio.)
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


@pytest.mark.asyncio
async def test_meeting_asr_provider_default_is_qwen3(migrated_engine: AsyncEngine) -> None:
    """At HEAD (post-0008), the column DEFAULT is 'qwen3' and new inserts use it."""
    async with migrated_engine.begin() as conn:
        # Inspect the column default in PG metadata.
        row = (
            await conn.execute(
                text(
                    """
                    SELECT column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'meeting'
                      AND column_name = 'asr_provider'
                    """
                )
            )
        ).first()
        assert row is not None
        assert "qwen3" in (row.column_default or ""), (
            f"meeting.asr_provider DEFAULT must contain 'qwen3'; got {row.column_default!r}"
        )

        # Insert without asr_provider — should land 'qwen3'.
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": "u_qwen3_default", "email": "u_qwen3_default@example.com"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name
                )
                VALUES ('m_qwen3_default', 'u_qwen3_default', 'T', 'C', 'M')
                """
            )
        )
        provider = (
            await conn.execute(
                text("SELECT asr_provider FROM meeting WHERE id = 'm_qwen3_default'")
            )
        ).scalar_one()
        assert provider == "qwen3"


@pytest.mark.asyncio
async def test_pre_0008_whisper_rows_are_not_back_filled(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration 0008 MUST only change the column DEFAULT — existing rows stay 'whisper'.

    Steps the schema back to 0007 (pre-0008), seeds a row that picks up the
    old 'whisper' default, then upgrades to head and confirms the row was
    NOT back-filled.

    Async, but each `command.downgrade/upgrade` is wrapped in
    `asyncio.to_thread` because Alembic env.py spawns its own
    `asyncio.run(...)` and that can't nest under pytest-asyncio's loop.
    """
    # Alembic env.py loads Settings via pydantic-settings; set the same env
    # the session-scoped conftest fixture uses.
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = (
        test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if test_database_url.startswith("postgresql://")
        else test_database_url
    )

    # Step back to the revision immediately before 0008. Run alembic via
    # asyncio.to_thread so its own asyncio.run inside env.py doesn't
    # collide with pytest-asyncio's running loop.
    await asyncio.to_thread(command.downgrade, cfg, "0007_add_recording_deleted_at")

    # Seed a row using the OLD ('whisper') default.
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
                {"uid": "u_pre0008", "email": "u_pre0008@example.com"},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO meeting (
                        id, user_id, title, counterparty_display_name, me_display_name
                    )
                    VALUES ('m_pre0008', 'u_pre0008', 'T', 'C', 'M')
                    """
                )
            )
            seeded = (
                await conn.execute(text("SELECT asr_provider FROM meeting WHERE id = 'm_pre0008'"))
            ).scalar_one()
            assert seeded == "whisper", "pre-0008 default should still be 'whisper'"
    finally:
        await engine.dispose()

    # Run 0008.
    await asyncio.to_thread(command.upgrade, cfg, "head")

    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.begin() as conn:
            preserved = (
                await conn.execute(text("SELECT asr_provider FROM meeting WHERE id = 'm_pre0008'"))
            ).scalar_one()
            assert preserved == "whisper", (
                f"Existing row MUST NOT be back-filled by 0008; got asr_provider={preserved!r}"
            )

            # Cleanup so the seeded row doesn't leak into other tests' counts.
            await conn.execute(
                text('DELETE FROM "user" WHERE id = :uid'),
                {"uid": "u_pre0008"},
            )
    finally:
        await engine.dispose()
