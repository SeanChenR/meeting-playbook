"""Verify migration 0019 makes `meeting_attachment.meeting_id` nullable and
adds a NOT NULL `user_id` column — slice-24 task 1.1.

Per spec meeting-attachment ADDED requirement
"meeting_attachment row supports staged (orphan) state":

  (a) At HEAD: `meeting_attachment.meeting_id` is_nullable = YES.
  (b) At HEAD: `meeting_attachment.user_id` exists, NOT NULL, FK to user.id.
  (c) At HEAD: composite index
      `meeting_attachment_user_meeting_uploaded_idx` exists on
      (user_id, meeting_id, uploaded_at DESC).
  (d) Existing attached rows (created by earlier migrations) get backfilled
      `user_id` from their meeting's `user_id` via JOIN before SET NOT NULL.
  (e) Task 1.2: SQLAlchemy `MeetingAttachment(meeting_id=None, user_id=...)`
      ORM insert round-trips without a DB error.
  (f) Downgrade -1 deletes any meeting_id IS NULL rows, drops the
      user_id column, restores meeting_id NOT NULL. Upgrade head restores.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _run_alembic(action: str, target: str, database_url: str) -> None:
    """Run alembic CLI in a subprocess to avoid event-loop conflicts."""
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "BETTER_AUTH_SECRET": "test-secret",
        "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
        "GOOGLE_OAUTH_CLIENT_SECRET": "test-client-secret",
    }
    proc = subprocess.run(  # noqa: S603 - alembic CLI, hard-coded args
        [sys.executable, "-m", "alembic", action, target],
        cwd=str(_BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"alembic {action} {target} failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )


@pytest.mark.asyncio
async def test_meeting_id_is_nullable_at_head(migrated_engine: AsyncEngine) -> None:
    """After 0019, `meeting_attachment.meeting_id` allows NULL."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'meeting_attachment'
                      AND column_name = 'meeting_id'
                    """
                )
            )
        ).first()
    assert row is not None, "meeting_attachment.meeting_id column missing"
    assert row.is_nullable == "YES", "meeting_id MUST be nullable after 0019"


@pytest.mark.asyncio
async def test_user_id_column_exists_not_null_at_head(
    migrated_engine: AsyncEngine,
) -> None:
    """After 0019, `meeting_attachment.user_id` exists, NOT NULL, text."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'meeting_attachment'
                      AND column_name = 'user_id'
                    """
                )
            )
        ).first()
    assert row is not None, "meeting_attachment.user_id column missing"
    assert row.is_nullable == "NO", "user_id MUST be NOT NULL"
    assert row.data_type == "text"


@pytest.mark.asyncio
async def test_user_id_fk_to_user_table(migrated_engine: AsyncEngine) -> None:
    """A FK constraint links meeting_attachment.user_id → user.id."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT
                        tc.constraint_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table,
                        ccu.column_name AS foreign_column
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                        ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.table_name = 'meeting_attachment'
                      AND tc.constraint_type = 'FOREIGN KEY'
                      AND kcu.column_name = 'user_id'
                    """
                )
            )
        ).all()
    assert any(r.foreign_table == "user" and r.foreign_column == "id" for r in rows), (
        f"Expected FK meeting_attachment.user_id → user.id; got {rows!r}"
    )


@pytest.mark.asyncio
async def test_user_meeting_uploaded_index_exists(migrated_engine: AsyncEngine) -> None:
    """The composite index for staging list queries exists at HEAD."""
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'meeting_attachment'
                      AND indexname = 'meeting_attachment_user_meeting_uploaded_idx'
                    """
                )
            )
        ).first()
    assert row is not None, "Index meeting_attachment_user_meeting_uploaded_idx missing at HEAD"
    # Sanity: it should include user_id and uploaded_at.
    assert "user_id" in row.indexdef
    assert "uploaded_at" in row.indexdef


@pytest.mark.asyncio
async def test_orm_insert_with_null_meeting_id_succeeds(
    migrated_engine: AsyncEngine,
) -> None:
    """Task 1.2: MeetingAttachment ORM model accepts meeting_id=None + user_id."""
    from datetime import UTC, datetime

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from meeting_playbook.attachments.models import MeetingAttachment

    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('u_nullorm', 'u_nullorm', 'u_nullorm@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )

    async with Session() as session:
        att = MeetingAttachment(
            id="att_orm_null",
            meeting_id=None,
            user_id="u_nullorm",
            file_path="/tmp/x.pdf",
            kind="pdf",
            original_name="x.pdf",
            bytes=10,
            uploaded_at=datetime.now(UTC),
        )
        session.add(att)
        await session.commit()

    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT meeting_id, user_id
                    FROM meeting_attachment
                    WHERE id = 'att_orm_null'
                    """
                )
            )
        ).first()
    assert row is not None
    assert row.meeting_id is None
    assert row.user_id == "u_nullorm"

    # cleanup so other tests stay isolated
    async with migrated_engine.begin() as conn:
        await conn.execute(text("DELETE FROM meeting_attachment WHERE id = 'att_orm_null'"))
        await conn.execute(text("DELETE FROM \"user\" WHERE id = 'u_nullorm'"))


@pytest.mark.asyncio
async def test_downgrade_drops_user_id_and_restores_not_null(
    _migrated_db_url: str,
) -> None:
    """downgrade -1 deletes orphan rows, drops user_id, restores meeting_id NOT NULL.

    The migration's downgrade MUST cleanly remove any staged rows
    (meeting_id IS NULL) before re-enforcing NOT NULL — otherwise the
    constraint addition would fail.
    """
    sync_url = _migrated_db_url
    async_url = _async_url(sync_url)

    # Seed a staged row so downgrade has something to clean up.
    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO "user" (id, name, email, "emailVerified")
                    VALUES ('u_down', 'u_down', 'u_down@example.com', true)
                    ON CONFLICT (id) DO NOTHING
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO meeting_attachment
                        (id, meeting_id, user_id, file_path, kind, original_name,
                         bytes, uploaded_at)
                    VALUES
                        ('att_down_orphan', NULL, 'u_down', '/tmp/o.pdf', 'pdf',
                         'o.pdf', 10, now())
                    """
                )
            )
    finally:
        await engine.dispose()

    try:
        _run_alembic("downgrade", "-1", sync_url)

        engine = create_async_engine(async_url, future=True)
        try:
            async with engine.connect() as conn:
                col = (
                    await conn.execute(
                        text(
                            """
                            SELECT is_nullable
                            FROM information_schema.columns
                            WHERE table_name = 'meeting_attachment'
                              AND column_name = 'meeting_id'
                            """
                        )
                    )
                ).first()
                user_col = (
                    await conn.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_name = 'meeting_attachment'
                              AND column_name = 'user_id'
                            """
                        )
                    )
                ).first()
                idx = (
                    await conn.execute(
                        text(
                            """
                            SELECT indexname FROM pg_indexes
                            WHERE indexname = 'meeting_attachment_user_meeting_uploaded_idx'
                            """
                        )
                    )
                ).first()
            assert col is not None and col.is_nullable == "NO", (
                "After downgrade, meeting_id MUST be restored to NOT NULL"
            )
            assert user_col is None, "After downgrade, user_id column MUST be dropped"
            assert idx is None, "After downgrade, composite index MUST be dropped"
        finally:
            await engine.dispose()
    finally:
        _run_alembic("upgrade", "head", sync_url)
        # Cleanup the seed row (it may not exist after upgrade if downgrade
        # purged it; missing row is fine).
        engine = create_async_engine(async_url, future=True)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM meeting_attachment WHERE id = 'att_down_orphan'")
                )
                await conn.execute(text("DELETE FROM \"user\" WHERE id = 'u_down'"))
        finally:
            await engine.dispose()
