"""Verify migration 0016 creates the `meeting_attachment` table (slice-20a task 1.1).

Per spec meeting-attachment ADDED requirement
"meeting_attachment table stores per-meeting attachment metadata":

  (a) Migration creates the table with all columns + CHECK constraints +
      FK CASCADE + composite index `(meeting_id, deleted_at)`.
  (b) The `kind` CHECK constraint rejects any value outside
      {image, pdf, docx, text, markdown}.
  (c) The `bytes > 0` CHECK constraint rejects zero / negative.
  (d) Up → down → up is reversible — downgrade drops the table cleanly;
      re-running upgrade re-creates it.
  (e) Deleting a meeting CASCADEs to its attachments.
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
async def test_meeting_attachment_table_exists_at_head(migrated_engine: AsyncEngine) -> None:
    """At HEAD, the `meeting_attachment` table exists with the expected columns."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'meeting_attachment'
                    ORDER BY column_name
                    """
                )
            )
        ).all()
    cols_by_name = {r.column_name: r for r in rows}

    for col in (
        "id",
        "meeting_id",
        "file_path",
        "kind",
        "original_name",
        "bytes",
        "uploaded_at",
        "deleted_at",
    ):
        assert col in cols_by_name, f"meeting_attachment.{col} missing"

    assert cols_by_name["deleted_at"].is_nullable == "YES"
    assert cols_by_name["uploaded_at"].is_nullable == "NO"
    assert cols_by_name["kind"].is_nullable == "NO"
    assert cols_by_name["bytes"].is_nullable == "NO"


@pytest.mark.asyncio
async def test_meeting_attachment_index_exists(migrated_engine: AsyncEngine) -> None:
    """The (meeting_id, deleted_at) composite index supports the list endpoint."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'meeting_attachment'
                    """
                )
            )
        ).all()
    index_names = {r.indexname for r in rows}
    assert any("meeting_id" in name and "deleted_at" in name for name in index_names), (
        f"expected composite index on (meeting_id, deleted_at); got {index_names}"
    )


@pytest.mark.asyncio
async def test_meeting_attachment_kind_check_constraint_rejects_invalid(
    migrated_engine: AsyncEngine,
) -> None:
    """The kind CHECK constraint refuses values outside the 5-enum set."""
    # Seed user + meeting
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('u_chk', 'u_chk', 'u_chk@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name
                )
                VALUES ('m_chk', 'u_chk', 'T', 'C', 'M')
                ON CONFLICT (id) DO NOTHING
                """
            )
        )

    with pytest.raises(IntegrityError):
        async with migrated_engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO meeting_attachment (
                        id, meeting_id, user_id, file_path, kind, original_name, bytes
                    )
                    VALUES (:aid, 'm_chk', 'u_chk', '/tmp/x', :bad_kind, 'x', 100)
                    """
                ),
                {"aid": "att_bad_kind", "bad_kind": "video"},
            )


@pytest.mark.asyncio
async def test_meeting_attachment_bytes_check_rejects_zero(
    migrated_engine: AsyncEngine,
) -> None:
    """The bytes > 0 CHECK refuses zero (and by extension negative) sizes."""
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('u_bz', 'u_bz', 'u_bz@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name
                )
                VALUES ('m_bz', 'u_bz', 'T', 'C', 'M')
                ON CONFLICT (id) DO NOTHING
                """
            )
        )

    with pytest.raises(IntegrityError):
        async with migrated_engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO meeting_attachment (
                        id, meeting_id, user_id, file_path, kind, original_name, bytes
                    )
                    VALUES ('att_bz_zero', 'm_bz', 'u_bz', '/tmp/x', 'pdf', 'x.pdf', 0)
                    """
                )
            )


@pytest.mark.asyncio
async def test_meeting_attachment_cascade_on_meeting_delete(
    migrated_engine: AsyncEngine,
) -> None:
    """Deleting a meeting cascades to delete its attachments."""
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('u_cas', 'u_cas', 'u_cas@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name
                )
                VALUES ('m_cas', 'u_cas', 'T', 'C', 'M')
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        for i in range(3):
            await conn.execute(
                text(
                    """
                    INSERT INTO meeting_attachment (
                        id, meeting_id, user_id, file_path, kind, original_name, bytes
                    )
                    VALUES (:aid, 'm_cas', 'u_cas', '/tmp/x', 'pdf', 'x.pdf', 100)
                    """
                ),
                {"aid": f"att_cas_{i}"},
            )

    async with migrated_engine.connect() as conn:
        before = (
            await conn.execute(
                text("SELECT COUNT(*) FROM meeting_attachment WHERE meeting_id = 'm_cas'")
            )
        ).scalar_one()
        assert before == 3

    # Delete the meeting → cascade should remove all attachments.
    async with migrated_engine.begin() as conn:
        await conn.execute(text("DELETE FROM meeting WHERE id = 'm_cas'"))

    async with migrated_engine.connect() as conn:
        after = (
            await conn.execute(
                text("SELECT COUNT(*) FROM meeting_attachment WHERE meeting_id = 'm_cas'")
            )
        ).scalar_one()
    assert after == 0, "CASCADE should remove all attachments when the meeting is deleted"


@pytest.mark.asyncio
async def test_migration_up_down_up_is_reversible(
    test_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run alembic upgrade → downgrade → upgrade three times and confirm the table
    is present at the end, absent in the middle, and idempotent on the bookends.

    Wraps `command.downgrade/upgrade` in `asyncio.to_thread` because Alembic
    env.py spawns its own `asyncio.run(...)` which cannot nest under
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

    async def _table_exists() -> bool:
        engine = create_async_engine(async_url, future=True)
        try:
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            """
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = 'public'
                              AND table_name = 'meeting_attachment'
                            """
                        )
                    )
                ).first()
                return row is not None
        finally:
            await engine.dispose()

    # Step back to 0015 (pre-0016).
    await asyncio.to_thread(command.downgrade, cfg, "0015_chunk_text_edited_at")
    assert not await _table_exists(), "table must be absent before 0016 upgrade"

    # Upgrade — should create the table.
    await asyncio.to_thread(command.upgrade, cfg, "head")
    assert await _table_exists(), "table must exist after upgrade to head"

    # Downgrade one step — should drop the table.
    await asyncio.to_thread(command.downgrade, cfg, "0015_chunk_text_edited_at")
    assert not await _table_exists(), "table must be dropped after downgrade -1"

    # Upgrade again — should re-create cleanly (round-trip).
    await asyncio.to_thread(command.upgrade, cfg, "head")
    assert await _table_exists(), "table must exist after re-upgrade to head"
