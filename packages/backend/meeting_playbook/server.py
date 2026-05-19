"""FastAPI application — gateway-trusting backend.

Per ADR-0021 + spec `auth-gateway-contract`: this service is only ever called by the
Bun.serve gateway, which validates the Better Auth session and injects an
`X-User-Id` request header. The backend trusts that header without re-validation.

Direct requests that bypass the gateway (no `X-User-Id`) MUST receive a 401 with
`error_code: auth.gateway_bypass`.

Slice 2 adds an error-envelope contract: every error response is shaped
`{"error_code": <snake.dot.code>, "message": <str>}`. The frontend looks up
`error_code` in its `errors.*` locale group to render a localized message.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, Header, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.exceptions import HTTPException as StarletteHTTPException

from meeting_playbook.attachments.router import router as attachments_router
from meeting_playbook.attachments.staging_router import (
    router as attachments_staging_router,
)
from meeting_playbook.audio_playback.router import router as audio_playback_router
from meeting_playbook.calendar.router import router as calendar_router
from meeting_playbook.chat.router import router as chat_router
from meeting_playbook.config import get_settings
from meeting_playbook.dashboard_stats.router import router as dashboard_stats_router
from meeting_playbook.export.router import router as export_router
from meeting_playbook.meeting_links.router import router as meeting_links_router
from meeting_playbook.meetings.router import router as meetings_router
from meeting_playbook.offline_ingest import (
    pipeline as _offline_ingest_pipeline,  # noqa: F401 — auto-registers tus completion handler
)
from meeting_playbook.offline_ingest.router import router as offline_ingest_router
from meeting_playbook.playbooks.router import router as playbooks_router
from meeting_playbook.recordings.router import router as recordings_router
from meeting_playbook.retention import runtime as retention_runtime
from meeting_playbook.sessions.router import router as sessions_router
from meeting_playbook.summarization.router import router as summary_router
from meeting_playbook.tags.router import router as tags_router
from meeting_playbook.transcript_edit.router import router as transcript_edit_router
from meeting_playbook.voice_enrollment.router import router as voice_enrollment_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Spawn the retention background loop on startup; cancel on shutdown.

    The loop calls `retention.job.cleanup` once immediately and then every
    24h. Any per-iteration failure is logged + swallowed by the runtime so
    the loop survives across days.
    """
    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    task = asyncio.create_task(
        retention_runtime.run_forever(
            settings=settings,
            session_factory=session_factory,
        ),
        name="retention-loop",
    )
    logger.info(
        "retention background loop started (RECORDING_RETENTION_DAYS=%d)",
        settings.recording_retention_days,
    )

    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
        await engine.dispose()
        logger.info("retention background loop stopped")


def _envelope(status_code: int, error_code: str, message: str) -> JSONResponse:
    """Build a JSONResponse carrying the standard error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"error_code": error_code, "message": message},
    )


def create_app() -> FastAPI:
    """Construct and return the FastAPI app."""
    app = FastAPI(title="meeting-playbook backend", version="0.0.1", lifespan=_lifespan)

    # ─── Error envelope handlers ────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Endpoints can opt into a custom error_code by raising
        # HTTPException(detail={"error_code": "...", "message": "..."}).
        if isinstance(exc.detail, dict) and "error_code" in exc.detail:
            return _envelope(
                exc.status_code,
                str(exc.detail["error_code"]),
                str(exc.detail.get("message", "")),
            )
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = "auth.unauthenticated"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = "http.403"
        else:
            error_code = f"http.{exc.status_code}"
        return _envelope(exc.status_code, error_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        req: Request, exc: RequestValidationError
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {"msg": "Request validation failed"}
        msg = str(first.get("msg") or "Request validation failed")
        loc = first.get("loc") or ()

        # Domain-aware mapping: meeting POST body field errors get a
        # structured `meeting.<field>.required` so the frontend can resolve
        # to a localized message (slice-03 spec — required-field matrix;
        # slice-15 adds `scheduled_start_at` to the required matrix).
        if (
            req.url.path.startswith("/api/meetings")
            and len(loc) >= 2
            and loc[0] == "body"
            and loc[1]
            in {
                "title",
                "counterparty_display_name",
                "me_display_name",
                "scheduled_start_at",
            }
        ):
            error_code = f"meeting.{loc[1]}.required"
        else:
            error_code = "common.validation_error"

        return _envelope(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code,
            msg,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_req: Request, _exc: Exception) -> JSONResponse:
        # Hide internal details — clients get a stable error_code only.
        return _envelope(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "common.internal_error",
            "An unexpected error occurred",
        )

    # ─── Routes ─────────────────────────────────────────────────────────
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/me")
    async def me(
        x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    ) -> Any:
        if not x_user_id:
            return _envelope(
                status.HTTP_401_UNAUTHORIZED,
                "auth.gateway_bypass",
                "Missing X-User-Id header. This endpoint must be reached "
                "through the auth gateway (default localhost:3001).",
            )
        return {"user_id": x_user_id}

    # Mount /api/meetings/stats BEFORE the meetings router; FastAPI matches
    # routes in registration order and the catch-all `/{meeting_id}` route
    # on the meetings router would otherwise swallow `/stats`.
    app.include_router(dashboard_stats_router)
    app.include_router(meetings_router)
    app.include_router(tags_router)
    app.include_router(meeting_links_router)
    app.include_router(export_router)
    app.include_router(playbooks_router)
    app.include_router(calendar_router)
    app.include_router(sessions_router)
    app.include_router(chat_router)
    app.include_router(summary_router)
    app.include_router(voice_enrollment_router)
    app.include_router(offline_ingest_router)
    app.include_router(audio_playback_router)
    app.include_router(transcript_edit_router)
    app.include_router(attachments_router)
    # P4 IA refactor: flat `/api/recordings` index + batch-download. Mounted
    # after the meeting-scoped audio playback router so neither prefix shadows
    # the other (the per-meeting recording endpoints live at
    # `/api/meetings/{id}/recordings/...`).
    app.include_router(recordings_router)
    # Slice-24: staged (orphan) attachment endpoints live at /api/attachments
    # (not /api/meetings/{id}/attachments). Mount after the meeting-scoped
    # router so neither prefix shadows the other.
    app.include_router(attachments_staging_router)
    return app


# Configure root logger so app-side `logger.info(...)` actually reaches the
# uvicorn console. Without this, only WARNING+ from app loggers would surface
# (Python's root default), making slow Whisper calls look hung.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

app = create_app()
