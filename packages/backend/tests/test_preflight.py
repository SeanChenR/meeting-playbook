"""Tests for startup preflight checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meeting_playbook.config import Settings
from meeting_playbook.preflight import (
    _redact,
    check_database,
    check_vertex_ai,
    run_preflight_checks,
)


def _settings_required(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/test")
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-secret")


def test_redact_strips_credentials():
    assert _redact("postgresql://user:pass@host:5432/db") == "postgresql://***@host:5432/db"
    assert _redact("postgresql://localhost:5432/db") == "postgresql://localhost:5432/db"


@pytest.mark.asyncio
async def test_check_database_passes_when_connect_succeeds():
    fake_conn = AsyncMock()
    fake_conn.close = AsyncMock()
    fake_logger = MagicMock()

    with patch(
        "meeting_playbook.preflight.asyncpg.connect",
        new=AsyncMock(return_value=fake_conn),
    ):
        await check_database("postgresql://localhost:5432/test", fake_logger)

    fake_conn.close.assert_awaited_once()
    fake_logger.info.assert_called_once()


@pytest.mark.asyncio
async def test_check_database_raises_runtime_error_on_failure():
    fake_logger = MagicMock()

    with patch(
        "meeting_playbook.preflight.asyncpg.connect",
        new=AsyncMock(side_effect=ConnectionRefusedError("connection refused")),
    ):
        with pytest.raises(RuntimeError, match="PostgreSQL unreachable"):
            await check_database("postgresql://localhost:5432/test", fake_logger)


def test_check_vertex_ai_warns_when_unset(monkeypatch):
    _settings_required(monkeypatch)
    settings = Settings(_env_file=None)
    fake_logger = MagicMock()

    check_vertex_ai(settings, fake_logger)

    warning_events = [c.args[0] for c in fake_logger.warning.call_args_list]
    assert "preflight.vertex_ai_unset" in warning_events
    assert "preflight.gcp_credentials_unset" in warning_events


def test_check_vertex_ai_silent_when_set(monkeypatch):
    _settings_required(monkeypatch)
    monkeypatch.setenv("VERTEX_AI_PROJECT", "my-project")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/to/sa.json")
    settings = Settings(_env_file=None)
    fake_logger = MagicMock()

    check_vertex_ai(settings, fake_logger)

    fake_logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_run_preflight_orchestrates_both(monkeypatch):
    _settings_required(monkeypatch)
    settings = Settings(_env_file=None)
    fake_conn = AsyncMock()
    fake_conn.close = AsyncMock()
    fake_logger = MagicMock()

    with patch(
        "meeting_playbook.preflight.asyncpg.connect",
        new=AsyncMock(return_value=fake_conn),
    ):
        result = await run_preflight_checks(settings, logger=fake_logger)

    assert result is settings
    fake_conn.close.assert_awaited_once()
    info_events = [c.args[0] for c in fake_logger.info.call_args_list]
    assert "preflight.db_reachable" in info_events
    assert "preflight.complete" in info_events


@pytest.mark.asyncio
async def test_run_preflight_raises_on_missing_env(monkeypatch):
    for var in (
        "DATABASE_URL",
        "BETTER_AUTH_SECRET",
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
    ):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        await run_preflight_checks()
