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

    # Slice 12 — single-channel speaker attribution (面對面模式)
    # HuggingFace access token for downloading pyannote/speaker-diarization-3.1.
    # Required for `SingleChannelStrategy`; absent → `select_strategy` raises
    # `DiarizationProviderUnavailable` and the session orchestrator rejects
    # single-channel finalize. See ADR-0029 + README §3.5.
    pyannote_auth_token: str = ""

    # Slice 12 — rollback / kill switch for the hybrid attribution pipeline.
    # When false, `select_strategy` accepts only dual-channel configurations
    # and treats single-channel as `InvalidSpeakerConfiguration`. Useful to
    # revert quickly if pyannote outputs degrade in production.
    speaker_hybrid_enabled: bool = True

    # Slice 13 — voice enrollment (聲紋樣本) for single-channel auto-me.
    # Directory where each user's 30s enrollment WAV is persisted; the
    # `voice_enrollment` row only carries the file path, the embedding lives
    # in the DB. The user_id is appended as the filename to avoid collisions.
    voice_enrollment_dir: str = "~/MeetingPlaybook/voice_enrollments"

    # Cosine similarity threshold for matching a single-channel cluster's
    # embedding against the enrolled embedding. Best-cluster similarity must
    # be >= this value before the rename to `me` runs (per slice-13 ADR-0029
    # + design.md "Matching：cosine similarity + tunable threshold"). 0.5 is
    # the pyannote x-vector default; tune up if you see false positives.
    voice_enrollment_match_threshold: float = 0.5

    # Rollback flag for the voice enrollment integration. When false,
    # `apply_speaker_attribution` skips the post-strategy rename pass even
    # if a `voice_enrollment` row exists for the current user.
    voice_enrollment_enabled: bool = True

    # Slice 14 — offline ingest (離線匯入).
    # Staging + final WAV directory for files uploaded via the tus protocol.
    # Each tus session writes a `{upload_id}.partial` file here while in
    # flight; on completion the canonical 16kHz mono WAV is written to
    # `{meeting_id}/source.wav` under this same root.
    offline_upload_dir: str = "~/MeetingPlaybook/offline_uploads"

    # Maximum upload size in bytes (default 500 MiB). Enforced at tus
    # creation (`Upload-Length` header) and advertised via `Tus-Max-Size`
    # on OPTIONS responses so clients can refuse over-budget files locally.
    offline_upload_max_bytes: int = 524_288_000

    # Maximum transcoded duration in seconds (default 3 hours). Enforced
    # post-transcode by reading the canonical WAV header — high-bitrate
    # inputs can stay under the byte budget while exceeding wall time.
    offline_upload_max_duration_seconds: int = 10_800

    # Slice 20a — meeting attachment storage.
    # Per-meeting attachments (image / pdf / docx / text / markdown) are stored
    # under `{attachment_dir}/{meeting_id}/{attachment_id}.<ext>`. Default sits
    # alongside the recordings dir so a single user folder holds all meeting
    # artifacts. Quota is per-meeting (5 files / 30 MiB) — see ADR-0020 and the
    # 30-day retention semantics shared with recordings (cleanup job sweeps
    # both tables in one transaction).
    attachment_dir: str = "~/MeetingPlaybook/attachments"

    # Slice 20c — per-attachment text extraction timeout (PDF / docx). Caps
    # the time `AttachmentProcessor` spends pulling text from a single file
    # before raising `attachment.extraction_timeout`. Override via env to
    # bump for slow disks or very large PDFs.
    attachment_text_extraction_timeout_seconds: int = 15

    # Slice 24 — staged (orphan) attachment retention TTL. Per design D7,
    # the existing recording-retention background loop also sweeps staged
    # rows older than this many hours. Default 24h covers the
    # "上傳今晚弄好，明早建會議" workflow without leaking disk space.
    staged_attachment_ttl_hours: int = 24

    # Slice 16 — audio playback Range cap.
    # Single Range request body is capped here (default 2 MiB ≈ 64 seconds of
    # 16 kHz mono 16-bit PCM). Browsers chase up with a follow-up Range when
    # they need more, so this caps server-side memory + bandwidth per response
    # without preventing full-file playback.
    audio_range_max_bytes: int = 2_097_152

    # P4 IA refactor — `/recordings` batch-download size cap.
    # Sum of selected `recording.bytes` across a batch-download request MUST
    # NOT exceed this value; over-limit requests get 413 with
    # `error_code: "recording.batch_oversize"`. Default 2 GiB covers a typical
    # 30-day Recording window for a single user (~30 × 1-hour meetings at
    # ~60 MB / hour). Tune via env if downstream observes oversize rejections.
    recording_batch_download_max_bytes: int = 2_147_483_648

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
