"""Verify migration 0012 backfills `meeting.scheduled_start_at` then makes
it NOT NULL (slice-15 task 1.1).

Per spec meeting-management MODIFIED requirement
"Meeting carries optional scheduled start and end timestamps" → after
slice-15 the start timestamp is required + backfilled from `created_at`:

  (a) Upgrade: any pre-existing NULL value is rewritten to that row's
      `created_at`, the column ends up NOT NULL, and no row survives with
      NULL.
  (b) Downgrade: column drops NOT NULL — backfilled values stay; nullable
      again so older deploys can re-deploy without losing rows.
  (c) Up → down → up cycle is idempotent (no constraint duplicates, no
      data loss).
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
async def test_scheduled_start_at_is_not_null_at_head(
    migrated_engine: AsyncEngine,
) -> None:
    """At HEAD, the `scheduled_start_at` column has `NOT NULL` enforced."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'meeting'
                      AND column_name = 'scheduled_start_at'
                    """
                )
            )
        ).first()
    assert row is not None, "meeting.scheduled_start_at column missing"
    assert row.is_nullable == "NO", (
        f"scheduled_start_at MUST be NOT NULL at head; got {row.is_nullable!r}"
    )


@pytest.mark.asyncio
async def test_pre_0012_null_rows_are_backfilled_from_created_at(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration 0012 backfills `scheduled_start_at = created_at` for any
    existing NULL row, then enforces NOT NULL at the schema level.
    """
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = _async_url(test_database_url)

    # Step back to 0011 (pre-0012) so we can insert NULL rows.
    await asyncio.to_thread(command.downgrade, cfg, "0011_recording_source_started")

    # Seed: 1 user, 3 meetings all with scheduled_start_at = NULL.
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
                {"uid": "u_pre0012", "email": "u_pre0012@example.com"},
            )
            for i in range(3):
                await conn.execute(
                    text(
                        """
                        INSERT INTO meeting (
                            id, user_id, title, counterparty_display_name,
                            me_display_name, scheduled_start_at, created_at
                        )
                        VALUES (
                            :mid, 'u_pre0012', 'T', 'C', 'M', NULL,
                            now() - (:offset || ' days')::interval
                        )
                        """
                    ),
                    {"mid": f"m_pre_{i}", "offset": str(i * 7)},
                )
    finally:
        await engine.dispose()

    # Run 0012.
    await asyncio.to_thread(command.upgrade, cfg, "head")

    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.connect() as conn:
            count_null = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM meeting WHERE scheduled_start_at IS NULL")
                )
            ).scalar_one()
            assert count_null == 0, (
                f"After upgrade no meeting may have NULL scheduled_start_at; got {count_null}"
            )

            # Each backfilled row's scheduled_start_at must equal its created_at.
            mismatches = (
                await conn.execute(
                    text(
                        "SELECT id FROM meeting "
                        "WHERE id LIKE 'm_pre_%' "
                        "  AND scheduled_start_at <> created_at"
                    )
                )
            ).all()
            assert not mismatches, (
                f"backfill MUST set scheduled_start_at = created_at; mismatching rows: {mismatches}"
            )

            # Cleanup so the seeded rows don't leak.
            async with engine.begin() as conn2:
                await conn2.execute(
                    text('DELETE FROM "user" WHERE id = :uid'),
                    {"uid": "u_pre0012"},
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_downgrade_drops_not_null_then_reupgrade_succeeds(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Down → up cycle: downgrade restores nullable column, re-upgrade
    finishes cleanly with no constraint duplicates.
    """
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = _async_url(test_database_url)

    await asyncio.to_thread(command.downgrade, cfg, "0011_recording_source_started")
    try:
        engine = create_async_engine(async_url, future=True)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT is_nullable
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'meeting'
                              AND column_name = 'scheduled_start_at'
                            """
                        )
                    )
                ).first()
            assert row is not None
            assert row.is_nullable == "YES", (
                f"After downgrade scheduled_start_at MUST be nullable; got {row.is_nullable!r}"
            )
        finally:
            await engine.dispose()
    finally:
        # Restore HEAD so subsequent tests see the migrated schema.
        await asyncio.to_thread(command.upgrade, cfg, "head")
