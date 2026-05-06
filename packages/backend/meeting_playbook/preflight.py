"""Startup preflight checks — PostgreSQL reachability + env var validation + warnings.

Critical failures raise `RuntimeError` with actionable messages. Optional dependencies
(Vertex AI / GCP credentials) only warn, since Slice 1 does not need them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import asyncpg
import structlog
from pydantic import ValidationError

if TYPE_CHECKING:
    from .config import Settings


def _redact(url: str) -> str:
    """Mask credentials in a connection URL for safe logging."""
    if "@" in url:
        scheme_user, host_db = url.split("@", 1)
        scheme = scheme_user.split("://")[0] if "://" in scheme_user else "postgresql"
        return f"{scheme}://***@{host_db}"
    return url


async def check_database(database_url: str, logger: Any) -> None:
    """Connect to PostgreSQL and immediately close. Raise RuntimeError on failure."""
    try:
        conn = await asyncpg.connect(database_url)
        await conn.close()
        logger.info("preflight.db_reachable", url=_redact(database_url))
    except Exception as e:
        raise RuntimeError(
            f"PostgreSQL unreachable at {_redact(database_url)}: {e}. "
            "Run `brew services start postgresql@16 && createdb meeting_playbook`."
        ) from e


def check_vertex_ai(settings: Settings, logger: Any) -> None:
    """Warn (do not raise) when optional Vertex AI env vars are unset."""
    if not settings.vertex_ai_project:
        logger.warning(
            "preflight.vertex_ai_unset",
            hint="VERTEX_AI_PROJECT not set — LLM features will fail from Slice 5 onward",
        )
    if not settings.google_application_credentials:
        logger.warning(
            "preflight.gcp_credentials_unset",
            hint="GOOGLE_APPLICATION_CREDENTIALS not set — needed for Vertex AI auth",
        )


async def run_preflight_checks(
    settings: Settings | None = None,
    logger: Any | None = None,
) -> Settings:
    """Run all preflight checks. Returns the validated Settings.

    Raises `RuntimeError` on:
        - Missing required env vars (caught from Settings ValidationError)
        - PostgreSQL unreachable
    """
    log = logger or structlog.get_logger("preflight")

    if settings is None:
        from .config import Settings as SettingsCls

        try:
            settings = SettingsCls(_env_file=None)
        except ValidationError as e:
            missing = [str(err["loc"][0]) for err in e.errors() if err.get("type") == "missing"]
            raise RuntimeError(
                f"Missing required environment variables: {missing}. "
                "Copy .env.example to .env and fill in the values, then restart."
            ) from e

    await check_database(settings.database_url, log)
    check_vertex_ai(settings, log)
    log.info("preflight.complete")
    return settings
