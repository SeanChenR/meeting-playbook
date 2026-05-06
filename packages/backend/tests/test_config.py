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
