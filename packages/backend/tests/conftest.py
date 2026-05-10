"""Shared pytest fixtures for backend tests requiring a real PostgreSQL DB.

Per design.md slice-03-meeting-crud:
- Backend tests use pytest + httpx async client + a real PostgreSQL test DB.
- The `user` table is normally managed by Better Auth (TS), but this Python
  test suite needs it to exist for the meeting FK. We create a minimal
  fixture-shaped `user` table on test DB setup.

Test DB URL is taken from TEST_DATABASE_URL, falling back to
postgresql://localhost:5432/meeting_playbook_test.

Strategy:
- A session-scoped sync fixture (`_migrated_db_url`) ensures the user table
  exists and runs `alembic downgrade base + upgrade head` in a sync context
  (alembic itself spawns its own event loop in env.py, so it cannot be called
  from inside a running asyncio loop).
- An async per-test `db_session` fixture builds the engine and truncates
  application tables on teardown.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command

_BACKEND_DIR = Path(__file__).resolve().parent.parent

_TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://localhost:5432/meeting_playbook_test",
)


def _async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_USER_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS "user" (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    "emailVerified" BOOLEAN NOT NULL DEFAULT false,
    image TEXT,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT now(),
    "twoFactorEnabled" BOOLEAN
)
"""


def _alembic_config(url: str) -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    return cfg


async def _ensure_user_table(async_url: str) -> None:
    """Create the auth `user` table if missing — uses asyncpg via SQLAlchemy."""
    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(_USER_TABLE_DDL))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def _migrated_db_url() -> Iterator[str]:
    """Set up the test DB schema once per session and yield its URL."""
    asyncio.run(_ensure_user_table(_async_url(_TEST_DATABASE_URL)))

    cfg = _alembic_config(_TEST_DATABASE_URL)
    saved_env = {
        k: os.environ.get(k)
        for k in (
            "DATABASE_URL",
            "BETTER_AUTH_SECRET",
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
        )
    }
    os.environ.update(
        DATABASE_URL=_TEST_DATABASE_URL,
        BETTER_AUTH_SECRET="test-secret",
        GOOGLE_OAUTH_CLIENT_ID="test-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="test-client-secret",
    )
    try:
        from meeting_playbook.config import get_settings

        get_settings.cache_clear()
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        from meeting_playbook.config import get_settings

        get_settings.cache_clear()

    yield _TEST_DATABASE_URL


@pytest_asyncio.fixture
async def migrated_engine(_migrated_db_url: str) -> AsyncIterator[AsyncEngine]:
    """Per-test async engine bound to the freshly migrated test DB.

    Truncates application tables on teardown so each test starts clean.
    """
    engine = create_async_engine(_async_url(_migrated_db_url), future=True)
    yield engine
    async with engine.begin() as conn:
        # CASCADE from "user" / "meeting" already wipes children, but we
        # truncate explicitly so a future migration that drops a FK does
        # not silently leave stale rows behind.
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "playbook" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(migrated_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession bound to the migrated test engine."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest.fixture
def test_database_url() -> str:
    """Expose the resolved test DB URL (sync form) for tests that need it."""
    return _TEST_DATABASE_URL
