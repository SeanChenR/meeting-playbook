"""Tests for Settings — env loading, required-field validation, async URL rewrite."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from meeting_playbook.config import Settings


def _set_required(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/test_db")
    monkeypatch.setenv("BETTER_AUTH_SECRET", "test-secret-32-bytes-base64-encoded")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")


def test_settings_loads_required_fields(monkeypatch):
    _set_required(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql://localhost:5432/test_db"
    assert settings.better_auth_secret == "test-secret-32-bytes-base64-encoded"
    assert settings.google_oauth_client_id == "test-client-id"
    assert settings.google_oauth_client_secret == "test-client-secret"


def test_settings_default_optional_fields(monkeypatch):
    _set_required(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.vertex_ai_location == "us-central1"
    assert settings.backend_url == "http://localhost:8000"
    assert settings.log_level == "INFO"
    assert settings.google_application_credentials == ""
    assert settings.vertex_ai_project == ""


def test_settings_raises_on_missing_required(monkeypatch):
    for var in (
        "DATABASE_URL",
        "BETTER_AUTH_SECRET",
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
    ):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_async_database_url_adds_asyncpg_prefix(monkeypatch):
    _set_required(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/test_db")

    settings = Settings(_env_file=None)

    assert settings.async_database_url == "postgresql+asyncpg://localhost:5432/test_db"


def test_async_database_url_passthrough_when_already_asyncpg(monkeypatch):
    _set_required(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://localhost:5432/test_db")

    settings = Settings(_env_file=None)

    assert settings.async_database_url == "postgresql+asyncpg://localhost:5432/test_db"


# ─── Slice 11: recording retention ──────────────────────────────────


def test_recording_retention_days_default(monkeypatch):
    """Without an env override, retention defaults to 30 days."""
    _set_required(monkeypatch)
    monkeypatch.delenv("RECORDING_RETENTION_DAYS", raising=False)

    settings = Settings(_env_file=None)
    assert settings.recording_retention_days == 30


def test_recording_retention_days_env_override(monkeypatch):
    """Env var overrides the default."""
    _set_required(monkeypatch)
    monkeypatch.setenv("RECORDING_RETENTION_DAYS", "7")

    settings = Settings(_env_file=None)
    assert settings.recording_retention_days == 7


def test_recording_retention_days_zero_is_valid(monkeypatch):
    """`0` is valid: cleanup will delete everything older than `now()`."""
    _set_required(monkeypatch)
    monkeypatch.setenv("RECORDING_RETENTION_DAYS", "0")

    settings = Settings(_env_file=None)
    assert settings.recording_retention_days == 0


def test_audio_range_max_bytes_default(monkeypatch):
    """Default cap on a single Range request body is 2 MiB (slice-16 task 1.2)."""
    _set_required(monkeypatch)
    monkeypatch.delenv("AUDIO_RANGE_MAX_BYTES", raising=False)

    settings = Settings(_env_file=None)
    assert settings.audio_range_max_bytes == 2_097_152


def test_audio_range_max_bytes_env_override(monkeypatch):
    """Env override (1 MiB) takes effect (slice-16 task 1.2)."""
    _set_required(monkeypatch)
    monkeypatch.setenv("AUDIO_RANGE_MAX_BYTES", "1048576")

    settings = Settings(_env_file=None)
    assert settings.audio_range_max_bytes == 1_048_576


# ─── Slice 20a: meeting attachment storage ──────────────────────────


def test_attachment_dir_default(monkeypatch):
    """Default attachment directory is `~/MeetingPlaybook/attachments`."""
    _set_required(monkeypatch)
    monkeypatch.delenv("ATTACHMENT_DIR", raising=False)

    settings = Settings(_env_file=None)
    assert settings.attachment_dir == "~/MeetingPlaybook/attachments"


def test_attachment_dir_env_override(monkeypatch):
    """Env var ATTACHMENT_DIR overrides the default."""
    _set_required(monkeypatch)
    monkeypatch.setenv("ATTACHMENT_DIR", "/tmp/test-attachments")

    settings = Settings(_env_file=None)
    assert settings.attachment_dir == "/tmp/test-attachments"


# ─── Slice 24: staged attachment retention TTL ───────────────────────


def test_staged_attachment_ttl_default_24(monkeypatch):
    """Without an env override, staged attachment TTL defaults to 24 hours."""
    _set_required(monkeypatch)
    monkeypatch.delenv("STAGED_ATTACHMENT_TTL_HOURS", raising=False)

    settings = Settings(_env_file=None)
    assert settings.staged_attachment_ttl_hours == 24


def test_staged_attachment_ttl_env_override(monkeypatch):
    """Env var STAGED_ATTACHMENT_TTL_HOURS overrides the default."""
    _set_required(monkeypatch)
    monkeypatch.setenv("STAGED_ATTACHMENT_TTL_HOURS", "72")

    settings = Settings(_env_file=None)
    assert settings.staged_attachment_ttl_hours == 72


# ─── P4 IA refactor: recording batch download size cap ──────────────


def test_recording_batch_size_cap_default(monkeypatch):
    """Without an env override, the batch-download cap defaults to 2 GiB."""
    _set_required(monkeypatch)
    monkeypatch.delenv("RECORDING_BATCH_DOWNLOAD_MAX_BYTES", raising=False)

    settings = Settings(_env_file=None)
    assert settings.recording_batch_download_max_bytes == 2_147_483_648


def test_recording_batch_size_cap_override(monkeypatch):
    """Env var RECORDING_BATCH_DOWNLOAD_MAX_BYTES overrides the default."""
    _set_required(monkeypatch)
    monkeypatch.setenv("RECORDING_BATCH_DOWNLOAD_MAX_BYTES", "5368709120")

    settings = Settings(_env_file=None)
    assert settings.recording_batch_download_max_bytes == 5_368_709_120
