"""Verify migration 0007 adds `recording.deleted_at` (slice-11 task 4.1).

Per spec recording-retention ADDED requirement
"recording.deleted_at column tracks soft-deletion timestamp":

  (a) Migration adds the column with type TIMESTAMPTZ + nullable + no default.
  (b) Existing rows survive the migration with `deleted_at IS NULL`
      (no back-fill).
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
async def test_recording_has_deleted_at_column_at_head(migrated_engine: AsyncEngine) -> None:
    """At HEAD, the `deleted_at` column exists with type TIMESTAMPTZ + nullable."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'recording'
                      AND column_name = 'deleted_at'
                    """
                )
            )
        ).first()
    assert row is not None, "recording.deleted_at column missing after migration"
    assert row.data_type == "timestamp with time zone", (
        f"deleted_at type must be TIMESTAMPTZ; got {row.data_type!r}"
    )
    assert row.is_nullable == "YES", f"deleted_at must be nullable; got {row.is_nullable!r}"
    # The column has no DEFAULT — every existing row starts NULL ("recording
    # is still on disk"); the cleanup job stamps `now()` when it unlinks.
    assert row.column_default is None, (
        f"deleted_at must have no DEFAULT; got {row.column_default!r}"
    )


@pytest.mark.asyncio
async def test_pre_0007_recording_rows_are_not_back_filled(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration 0007 only adds a nullable column — existing rows stay NULL.

    Steps the schema back to 0006 (pre-0007), seeds 5 recording rows that
    pre-date the new column, then upgrades to head. After upgrade, all 5
    rows MUST still exist AND have `deleted_at IS NULL`.

    Wraps `command.downgrade/upgrade` in `asyncio.to_thread` because Alembic
    env.py spawns its own `asyncio.run(...)` and that can't nest under
    pytest-asyncio's loop.
    """
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = _async_url(test_database_url)

    # Step back to 0006 (pre-0007).
    await asyncio.to_thread(command.downgrade, cfg, "0006_create_summary")

    # Seed: 1 user, 1 meeting, 5 recordings (pre-existing).
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
                {"uid": "u_pre0007", "email": "u_pre0007@example.com"},
            )
            # 5 meetings, 1 recording each — recording has UNIQUE
            # (meeting_id, stream), so multi-rows-per-meeting needs distinct
            # streams. Spreading across meetings is simpler + matches the
            # "5 historical recordings" spec scenario shape.
            for i in range(5):
                mid = f"m_pre0007_{i}"
                await conn.execute(
                    text(
                        """
                        INSERT INTO meeting (
                            id, user_id, title, counterparty_display_name, me_display_name
                        )
                        VALUES (:mid, 'u_pre0007', 'T', 'C', 'M')
                        """
                    ),
                    {"mid": mid},
                )
                await conn.execute(
                    text(
                        """
                        INSERT INTO recording (
                            id, meeting_id, stream, file_path, bytes, created_at
                        )
                        VALUES (:rid, :mid, 'me', :fp, 100, now())
                        """
                    ),
                    {
                        "rid": f"r_pre_{i}",
                        "mid": mid,
                        "fp": f"/tmp/r_pre_{i}.wav",
                    },
                )
            count = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM recording WHERE meeting_id LIKE 'm_pre0007_%'")
                )
            ).scalar_one()
            assert count == 5, f"expected 5 seeded rows; got {count}"
    finally:
        await engine.dispose()

    # Run 0007.
    await asyncio.to_thread(command.upgrade, cfg, "head")

    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, deleted_at FROM recording "
                        "WHERE meeting_id LIKE 'm_pre0007_%' ORDER BY id"
                    )
                )
            ).all()
            assert len(rows) == 5, (
                f"All 5 pre-0007 rows MUST survive the migration; got {len(rows)}"
            )
            for r in rows:
                assert r.deleted_at is None, (
                    f"row {r.id} MUST have deleted_at IS NULL post-migration; got {r.deleted_at!r}"
                )

            # Cleanup so the seeded rows don't leak into other tests' counts.
            await conn.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": "u_pre0007"})
    finally:
        await engine.dispose()
