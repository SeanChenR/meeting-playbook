"""Application settings loaded from environment variables.

Uses pydantic-settings; see ADR-0007 (Python backend) and ADR-0012 (PostgreSQL).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-derived configuration.

    Required env vars (Slice 1):
        DATABASE_URL, BETTER_AUTH_SECRET,
        GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET

    Optional env vars (filled in by Slice 5+ when Vertex AI is wired):
        GOOGLE_APPLICATION_CREDENTIALS, VERTEX_AI_PROJECT, VERTEX_AI_LOCATION
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required
    database_url: str
    better_auth_secret: str
    google_oauth_client_id: str
    google_oauth_client_secret: str

    # Optional — Slice 5+ Vertex AI integration
    google_application_credentials: str = ""
    vertex_ai_project: str = ""
    vertex_ai_location: str = "us-central1"

    # Backend service URL (gateway forwards /api/* here)
    backend_url: str = "http://localhost:8000"

    # Logging
    log_level: str = "INFO"

    @property
    def async_database_url(self) -> str:
        """Return DATABASE_URL with the asyncpg driver prefix.

        TS-side `pg.Pool` wants `postgresql://`; SQLAlchemy async wants
        `postgresql+asyncpg://`. We keep one DATABASE_URL in .env and rewrite here.
        """
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """Cache a singleton Settings instance for the application lifetime."""
    return Settings()
