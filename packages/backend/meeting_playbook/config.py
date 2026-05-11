"""Application settings loaded from environment variables.

Uses pydantic-settings; see ADR-0007 (Python backend) and ADR-0012 (PostgreSQL).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is 4 directories up from this file:
#   packages/backend/meeting_playbook/config.py → repo/
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment-derived configuration.

    Required env vars (Slice 1):
        DATABASE_URL, BETTER_AUTH_SECRET,
        GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET

    Optional env vars (filled in by Slice 5+ when Vertex AI is wired):
        GOOGLE_APPLICATION_CREDENTIALS, VERTEX_AI_PROJECT, VERTEX_AI_LOCATION

    `.env` is searched at the repo root first, then the cwd. This lets the
    backend run from anywhere (root via `bun run dev`, or `packages/backend/`
    directly) without copying `.env` around.
    """

    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT / ".env"), ".env"),
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

    # Slice 5 — Python ↔ Bun gateway internal endpoint
    backend_internal_auth_secret: str = ""
    backend_internal_auth_url: str = "http://localhost:3001"

    # Slice 8 — Vertex Flash model id used by TacticalAdvisor (in-meeting advisor).
    # MUST be a Vertex AI publisher model id (e.g. `gemini-2.5-flash`,
    # `gemini-2.0-flash-001`), NOT a Gemini API (ai.google.dev) name like
    # `gemini-3.1-flash-lite` — those are not deployed to Vertex AI in
    # us-central1 and will 404 with `Publisher Model ... was not found`.
    # See https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
    vertex_flash_model_id: str = "gemini-2.5-flash"

    # Slice 10 — Vertex Pro model id used by MeetingSummarizer (post-meeting).
    # Same naming rules as `vertex_flash_model_id`: must be a Vertex AI
    # publisher model id, not a Gemini API name. Default `gemini-2.5-pro`
    # is the highest-quality SKU available on Vertex in us-central1.
    vertex_pro_model_id: str = "gemini-2.5-pro"

    # Slice 6 — audio capture + ASR
    recordings_dir: str = "~/MeetingPlaybook/recordings"
    whisper_model_size: str = "large-v3-turbo"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"

    # Slice 11 — recording retention. After this many days the cleanup
    # background job unlinks the wav file and stamps `recording.deleted_at`.
    # `0` is valid: cleanup deletes everything older than `now()`. The row
    # itself is never removed (preserves the historical fact that audio
    # was captured for this meeting + stream). See ADR-0028 + the slice-11
    # design Decision 5/6.
    recording_retention_days: int = 30

    # Slice 7 — dual-stream device discovery overrides (both optional)
    blackhole_device_name: str | None = None
    mic_device_name: str | None = None

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
