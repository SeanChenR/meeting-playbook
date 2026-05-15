"""Verify migration 0011 adds `recording.source` + `recording.started_at`
(slice-14 task 1.1).

Per spec `offline-ingest` ADDED requirement
"recording table tracks live vs offline source":

  (a) Upgrade: existing recording rows back-fill to `source = 'live'`;
      `started_at` is added nullable; CHECK constraint rejects any source
      outside `('live','offline')`.
  (b) Downgrade: drops the CHECK constraint, the `source` column, and the
      `started_at` column cleanly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
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
async def test_recording_has_source_and_started_at_at_head(
    migrated_engine: AsyncEngine,
) -> None:
    """At HEAD both columns exist with the expected shape."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'recording'
                      AND column_name IN ('source', 'started_at')
                    ORDER BY column_name
                    """
                )
            )
        ).all()
    by_name = {r.column_name: r for r in rows}
    assert "source" in by_name, "recording.source column missing after migration"
    assert by_name["source"].data_type == "text", (
        f"source type must be text; got {by_name['source'].data_type!r}"
    )
    assert by_name["source"].is_nullable == "NO", (
        f"source must be NOT NULL; got {by_name['source'].is_nullable!r}"
    )
    assert by_name["source"].column_default is not None, (
        "source must carry a DEFAULT so pre-migration rows back-fill to 'live'"
    )
    assert "'live'" in by_name["source"].column_default, (
        f"source DEFAULT must be 'live'; got {by_name['source'].column_default!r}"
    )

    assert "started_at" in by_name, "recording.started_at column missing"
    assert by_name["started_at"].data_type == "timestamp with time zone", (
        f"started_at type must be TIMESTAMPTZ; got {by_name['started_at'].data_type!r}"
    )
    # Slice-14 introduced `started_at` as nullable; slice-16 migration
    # 0014 backfills then tightens to NOT NULL. After HEAD, the column
    # is required — see test_alembic_recording_started_at.py for the
    # backfill round-trip coverage.
    assert by_name["started_at"].is_nullable == "NO", (
        f"started_at must be NOT NULL after slice-16; got {by_name['started_at'].is_nullable!r}"
    )


@pytest.mark.asyncio
async def test_pre_0011_recording_rows_backfill_as_live(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Migration 0011 back-fills existing rows to `source = 'live'`.

    Steps the schema back to 0010 (pre-0011), seeds 3 recording rows that
    pre-date the new column, then upgrades to head. After upgrade, all 3
    rows MUST exist with `source = 'live'` and `started_at IS NULL`.
    """
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = _async_url(test_database_url)

    # Step back to 0010 (pre-0011).
    await asyncio.to_thread(command.downgrade, cfg, "0010_relax_chunk_speaker_check")

    # Seed: 1 user, 3 meetings, 3 recordings.
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
                {"uid": "u_pre0011", "email": "u_pre0011@example.com"},
            )
            for i in range(3):
                mid = f"m_pre0011_{i}"
                await conn.execute(
                    text(
                        """
                        INSERT INTO meeting (
                            id, user_id, title, counterparty_display_name, me_display_name
                        )
                        VALUES (:mid, 'u_pre0011', 'T', 'C', 'M')
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
    finally:
        await engine.dispose()

    # Run 0011.
    await asyncio.to_thread(command.upgrade, cfg, "head")

    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, source, started_at FROM recording "
                        "WHERE meeting_id LIKE 'm_pre0011_%' ORDER BY id"
                    )
                )
            ).all()
            assert len(rows) == 3, (
                f"All 3 pre-0011 rows MUST survive the migration; got {len(rows)}"
            )
            for r in rows:
                assert r.source == "live", (
                    f"row {r.id} MUST back-fill to source='live'; got {r.source!r}"
                )
                # Slice-14 added `started_at` as nullable and inserted rows
                # left it NULL. Slice-16 migration 0014 now back-fills any
                # NULL value to that row's `created_at` and tightens to
                # NOT NULL — so after HEAD the value MUST be non-null and
                # equal to created_at for these pre-0011 rows.
                assert r.started_at is not None, (
                    f"row {r.id} MUST have started_at back-filled post-0014; got NULL"
                )

            # Cleanup so the seeded rows don't leak into other tests' counts.
            await conn.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": "u_pre0011"})
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_source_check_constraint_rejects_invalid_values(
    migrated_engine: AsyncEngine,
) -> None:
    """The CHECK constraint MUST reject sources outside ('live','offline')."""
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": "u_check_0011", "email": "u_check_0011@example.com"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name
                )
                VALUES ('m_check_0011', 'u_check_0011', 'T', 'C', 'M')
                """
            )
        )

    try:
        with pytest.raises(IntegrityError) as excinfo:
            async with migrated_engine.begin() as conn:
                await conn.execute(
                    text(
                        """
                        INSERT INTO recording (
                            id, meeting_id, stream, file_path, bytes, created_at, source
                        )
                        VALUES ('r_check_bad', 'm_check_0011', 'me', '/tmp/bad.wav',
                                100, now(), 'streamed')
                        """
                    )
                )
        # PostgreSQL surfaces the check constraint name in the error.
        assert (
            "recording_source_check" in str(excinfo.value) or "check" in str(excinfo.value).lower()
        ), f"expected check constraint violation; got {excinfo.value!r}"
    finally:
        async with migrated_engine.begin() as conn:
            await conn.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": "u_check_0011"})


@pytest.mark.asyncio
async def test_downgrade_removes_source_and_started_at(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Downgrade 0011 → 0010 cleanly drops both columns + the CHECK."""
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    cfg = _alembic_config(test_database_url)
    async_url = _async_url(test_database_url)

    # Run downgrade to 0010 then back up to head so other tests are not affected.
    await asyncio.to_thread(command.downgrade, cfg, "0010_relax_chunk_speaker_check")
    try:
        engine = create_async_engine(async_url, future=True)
        try:
            async with engine.connect() as conn:
                cols = (
                    await conn.execute(
                        text(
                            """
                            SELECT column_name FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = 'recording'
                            """
                        )
                    )
                ).all()
                col_names = {row.column_name for row in cols}
                assert "source" not in col_names, (
                    "downgrade must drop the `source` column; still present"
                )
                assert "started_at" not in col_names, (
                    "downgrade must drop the `started_at` column; still present"
                )

                checks = (
                    await conn.execute(
                        text(
                            """
                            SELECT conname FROM pg_constraint
                            WHERE conrelid = 'public.recording'::regclass
                              AND contype = 'c'
                            """
                        )
                    )
                ).all()
                assert "recording_source_check" not in {c.conname for c in checks}, (
                    "downgrade must drop the `recording_source_check` CHECK; still present"
                )
        finally:
            await engine.dispose()
    finally:
        # Restore HEAD so subsequent tests see the migrated schema.
        await asyncio.to_thread(command.upgrade, cfg, "head")
