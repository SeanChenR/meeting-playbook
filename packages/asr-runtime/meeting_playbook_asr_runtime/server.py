"""FastAPI app factory for the ASR runtime.

Module-level layout:
  * `_get_runner()` — lazy singleton accessor (tests monkeypatch it).
  * `_runtime_state` — module-level state machine exposed via `/healthz`:
    `loading` → `ready` (after warmup) or `error` (if warmup raises).
  * Lifespan startup runs `_runner.load()` + an optional silent-audio
    warmup pass when `ASR_RUNTIME_WARMUP_ON_BOOT=1` (default).
  * `RuntimeUnavailableError` is translated into the structured 503
    envelope at the app level, so both HTTP and WebSocket routes get a
    consistent error shape.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from meeting_playbook_asr_runtime.errors import RuntimeUnavailableError
from meeting_playbook_asr_runtime.qwen3_runner import Qwen3Runner
from meeting_playbook_asr_runtime.routes import transcribe as transcribe_routes

logger = logging.getLogger(__name__)


_runner: Qwen3Runner | None = None


@dataclass
class _RuntimeState:
    """In-process status reported by /healthz."""

    status: str = "loading"  # "loading" | "ready" | "error"
    last_error: str | None = None
    started_at: float = field(default_factory=time.monotonic)

    def reset(self) -> None:
        self.status = "loading"
        self.last_error = None
        self.started_at = time.monotonic()


_runtime_state = _RuntimeState()


def _get_runner() -> Qwen3Runner:
    """Lazy singleton accessor.

    Tests monkeypatch this name so route handlers see a stub. Production
    code SHALL always call this — never `Qwen3Runner()` directly — so the
    same instance is reused across the process lifetime.
    """
    global _runner
    if _runner is None:
        _runner = Qwen3Runner()
    return _runner


def _warmup_enabled() -> bool:
    """Read `ASR_RUNTIME_WARMUP_ON_BOOT` at lifespan time (not import time).

    Tests set this env var via monkeypatch.setenv() *after* importing the
    module, so we MUST resolve it lazily inside the lifespan hook.
    """
    raw = os.environ.get("ASR_RUNTIME_WARMUP_ON_BOOT", "1").strip().lower()
    return raw not in ("0", "false", "no", "")


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """uvicorn lifespan — runs model warmup so the first real chunk skips
    the cold-start cost.

    Per design Decision 5:
      * default: load weights + run a 0.5s silent inference, then mark ready
      * `ASR_RUNTIME_WARMUP_ON_BOOT=0`: skip warmup; status stays `loading`
        until the first transcribe call triggers a lazy load
      * load/warmup raises: status flips to `error` + `last_error` captured
    """
    _runtime_state.reset()
    logger.info("asr-runtime lifespan startup (warmup_enabled=%s)", _warmup_enabled())
    if _warmup_enabled():
        try:
            runner = _get_runner()
            await runner.load()
            silent_pcm = bytes(16000 * 2)  # 1s of int16 silence — cheap to inference
            await runner.transcribe(silent_pcm, sample_rate_hz=16000)
            _runtime_state.status = "ready"
            logger.info("asr-runtime warmup complete")
        except Exception as exc:
            _runtime_state.status = "error"
            _runtime_state.last_error = str(exc)
            logger.exception("asr-runtime warmup failed")
    yield
    logger.info("asr-runtime lifespan shutdown")


app = FastAPI(
    title="meeting-playbook ASR runtime",
    version="0.0.1",
    lifespan=_lifespan,
)
app.include_router(transcribe_routes.router)


@app.exception_handler(RuntimeUnavailableError)
async def _runtime_unavailable_handler(
    _request: Request, exc: RuntimeUnavailableError
) -> JSONResponse:
    """Map RuntimeUnavailableError → structured 503 envelope (both
    transports rely on this shape)."""
    return JSONResponse(
        status_code=503,
        content={
            "error_code": "asr.runtime_unavailable",
            "message": exc.message,
            "retriable": exc.retriable,
        },
    )


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    """Public health check — reports model load state + identity bits."""
    runner = _get_runner()
    body: dict[str, object] = {
        "status": _runtime_state.status,
        "model_repo": runner.model_repo,
        "device": runner.device,
        "uptime_seconds": int(time.monotonic() - _runtime_state.started_at),
    }
    if _runtime_state.last_error is not None:
        body["last_error"] = _runtime_state.last_error
    return body


__all__ = ["app"]
