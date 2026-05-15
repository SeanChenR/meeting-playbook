"""Verify migration 0014 backfills `recording.started_at` then makes
it NOT NULL (slice-16 task 1.1).

Per spec audio-playback "Migration backfills existing recording rows":

  (a) Upgrade: any pre-existing NULL `started_at` is rewritten to that
      row's `created_at`, column ends up NOT NULL.
  (b) Downgrade: column drops NOT NULL — backfilled values stay.
  (c) Up → down → up cycle is idempotent.
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
async def test_started_at_is_not_null_at_head(
    migrated_engine: AsyncEngine,
) -> None:
    """At HEAD, the `recording.started_at` column has `NOT NULL` enforced."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'recording'
                      AND column_name = 'started_at'
                    """
                )
            )
        ).first()
    assert row is not None, "recording.started_at column missing"
    assert row.is_nullable == "NO", (
        f"recording.started_at MUST be NOT NULL at head; got {row.is_nullable!r}"
    )


@pytest.mark.asyncio
async def test_pre_0014_null_rows_are_backfilled_from_created_at(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration 0014 backfills `started_at = created_at` for any existing
    NULL row, then enforces NOT NULL at the schema level.
    """
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = _async_url(test_database_url)

    # Step back to the migration immediately before 0014 so we can
    # insert NULL `recording.started_at` rows.
    await asyncio.to_thread(command.downgrade, cfg, "0012_meeting_start_not_null")

    # Seed: 1 user, 1 meeting, 4 recordings with started_at = NULL but
    # distinct created_at offsets.
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
                {"uid": "u_pre0014", "email": "u_pre0014@example.com"},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO meeting (
                        id, user_id, title, counterparty_display_name,
                        me_display_name, scheduled_start_at, created_at
                    )
                    VALUES (
                        :mid, 'u_pre0014', 'T', 'C', 'M',
                        now() - interval '1 day', now() - interval '1 day'
                    )
                    """
                ),
                {"mid": "m_pre0014"},
            )
            # Two meetings × two streams = 4 NULL-started_at recordings.
            # `recording_meeting_stream_unique` constrains (meeting_id, stream),
            # so we vary the meeting_id per pair instead of stacking on one.
            for i in range(4):
                if i == 1:
                    await conn.execute(
                        text(
                            """
                            INSERT INTO meeting (
                                id, user_id, title, counterparty_display_name,
                                me_display_name, scheduled_start_at, created_at
                            )
                            VALUES (
                                'm_pre0014b', 'u_pre0014', 'T', 'C', 'M',
                                now() - interval '2 day', now() - interval '2 day'
                            )
                            """
                        )
                    )
                meeting_id = "m_pre0014" if i < 2 else "m_pre0014b"
                stream = "me" if i % 2 == 0 else "counterparty"
                await conn.execute(
                    text(
                        """
                        INSERT INTO recording (
                            id, meeting_id, stream, file_path, bytes,
                            created_at, started_at, source
                        )
                        VALUES (
                            :rid, :mid, :stream, '/tmp/x.wav', 1024,
                            now() - (:offset || ' days')::interval,
                            NULL, 'live'
                        )
                        """
                    ),
                    {
                        "rid": f"r_pre_{i}",
                        "mid": meeting_id,
                        "stream": stream,
                        "offset": str(i * 3),
                    },
                )
    finally:
        await engine.dispose()

    # Run 0014.
    await asyncio.to_thread(command.upgrade, cfg, "head")

    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.connect() as conn:
            count_null = (
                await conn.execute(text("SELECT COUNT(*) FROM recording WHERE started_at IS NULL"))
            ).scalar_one()
            assert count_null == 0, (
                f"After upgrade no recording may have NULL started_at; got {count_null}"
            )

            mismatches = (
                await conn.execute(
                    text(
                        "SELECT id FROM recording "
                        "WHERE id LIKE 'r_pre_%' AND started_at <> created_at"
                    )
                )
            ).all()
            assert not mismatches, (
                f"backfill MUST set started_at = created_at; mismatching: {mismatches}"
            )

            async with engine.begin() as conn2:
                await conn2.execute(
                    text('DELETE FROM "user" WHERE id = :uid'),
                    {"uid": "u_pre0014"},
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

    await asyncio.to_thread(command.downgrade, cfg, "0012_meeting_start_not_null")
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
                              AND table_name = 'recording'
                              AND column_name = 'started_at'
                            """
                        )
                    )
                ).first()
            assert row is not None
            assert row.is_nullable == "YES", (
                f"After downgrade started_at MUST be nullable; got {row.is_nullable!r}"
            )
        finally:
            await engine.dispose()
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
