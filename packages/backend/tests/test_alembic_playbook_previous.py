"""Verify migration 0018 adds the `previous_*` snapshot columns to `playbook`.

Per slice-23 task 1.1 (covers spec requirement
"`playbook` row SHALL carry the immediately preceding generated version"
in `playbook-versioning` and design D1: snapshot stored as row columns,
not a separate table).

Invariants this test pins down:
- At HEAD the `playbook` table has three nullable columns:
  `previous_free_form_markdown TEXT`, `previous_updated_at TIMESTAMPTZ`,
  `previous_attachment_hash_snapshot TEXT`.
- `Playbook` SQLAlchemy model accepts the three attributes (read + write)
  without type errors (task 1.2 — same test file per task scope).
- `alembic downgrade -1` removes the three columns; `alembic upgrade head`
  restores them.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from meeting_playbook.playbooks.models import Playbook

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _run_alembic(action: str, target: str, database_url: str) -> None:
    """Run `alembic <action> <target>` in a subprocess.

    Running alembic in-process clashes with pytest-asyncio's event loop
    (env.py spawns its own `asyncio.run`). A subprocess avoids the
    conflict and matches the shell invocation we use in CI.
    """
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


_PREVIOUS_COLS = (
    "previous_free_form_markdown",
    "previous_updated_at",
    "previous_attachment_hash_snapshot",
)


@pytest.mark.asyncio
async def test_playbook_has_previous_snapshot_columns_at_head(
    migrated_engine: AsyncEngine,
) -> None:
    """All three `previous_*` columns exist and are nullable at HEAD."""
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'playbook'
                      AND column_name = ANY(:cols)
                    """
                ),
                {"cols": list(_PREVIOUS_COLS)},
            )
        ).all()
    cols = {r.column_name: r for r in rows}

    for col in _PREVIOUS_COLS:
        assert col in cols, f"playbook.{col} missing at HEAD"
        assert cols[col].is_nullable == "YES", f"playbook.{col} should be NULL-able"

    assert cols["previous_free_form_markdown"].data_type == "text"
    assert cols["previous_updated_at"].data_type == "timestamp with time zone"
    assert cols["previous_attachment_hash_snapshot"].data_type == "text"


@pytest.mark.asyncio
async def test_playbook_model_accepts_previous_fields(migrated_engine: AsyncEngine) -> None:
    """Task 1.2: SQLAlchemy Playbook model attributes round-trip."""
    # Construct an in-memory Playbook with the new attrs assigned and read back.
    # We do not need to persist — model attribute presence is what the task validates.
    pb = Playbook()
    pb.previous_free_form_markdown = "draft v1"
    pb.previous_updated_at = None
    pb.previous_attachment_hash_snapshot = "hash-A"

    assert pb.previous_free_form_markdown == "draft v1"
    assert pb.previous_updated_at is None
    assert pb.previous_attachment_hash_snapshot == "hash-A"

    # Also verify defaults are None on a fresh instance.
    fresh = Playbook()
    assert fresh.previous_free_form_markdown is None
    assert fresh.previous_updated_at is None
    assert fresh.previous_attachment_hash_snapshot is None


@pytest.mark.asyncio
async def test_downgrade_drops_previous_columns_and_upgrade_restores_them(
    _migrated_db_url: str,
) -> None:
    """`alembic downgrade -1` drops the columns; `upgrade head` restores them."""
    sync_url = _migrated_db_url
    async_url = _async_url(sync_url)

    try:
        # Downgrade by one revision to undo 0018.
        _run_alembic("downgrade", "-1", sync_url)

        engine = create_async_engine(async_url, future=True)
        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                              AND table_name = 'playbook'
                              AND column_name = ANY(:cols)
                            """
                        ),
                        {"cols": list(_PREVIOUS_COLS)},
                    )
                ).all()
            assert rows == [], (
                f"After downgrade -1, previous_* columns should be gone; "
                f"still present: {[r.column_name for r in rows]}"
            )
        finally:
            await engine.dispose()
    finally:
        # Restore HEAD so the rest of the suite sees the migrated schema,
        # even if assertions above failed.
        _run_alembic("upgrade", "head", sync_url)

    engine = create_async_engine(async_url, future=True)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'playbook'
                          AND column_name = ANY(:cols)
                        """
                    ),
                    {"cols": list(_PREVIOUS_COLS)},
                )
            ).all()
        assert sorted(r.column_name for r in rows) == sorted(_PREVIOUS_COLS), (
            f"After upgrade head, previous_* columns should be restored; got {rows}"
        )
    finally:
        await engine.dispose()
