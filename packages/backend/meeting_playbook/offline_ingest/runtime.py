"""In-flight registry for offline-ingest ASR background tasks (slice-14 task 4.2).

Mirrors the slice-11 `rerun/runtime.py` shape — process-scoped registries
keyed by `meeting_id` — but parameterises the actual work via a
caller-supplied `runner` coroutine so the runtime stays decoupled from
the pipeline orchestration in `pipeline.py`.

State machine surfaced via `get_state(meeting_id)`:

  asr_running  → (runner returned)            → completed
  asr_running  → (runner raised)              → failed
  asr_running  → (set_state(mid, "failed"))   → failed   # pipeline-side failure
  transcoding  → spawn_ingest_task            → asr_running
  uploading    → set_state(mid, "transcoding")→ transcoding

`pipeline.py` is responsible for the pre-ASR transitions (`uploading` /
`transcoding`); this module only tracks the ASR background task itself.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChunksProgress:
    """Mutable counters surfaced via the progress polling endpoint."""

    processed: int = 0
    total: int = 0


# Process-scoped registries.
_inflight: dict[str, asyncio.Task[None]] = {}
_progress: dict[str, ChunksProgress] = {}
_state: dict[str, str] = {}
_error_code: dict[str, str] = {}
_lock = asyncio.Lock()


# State enum values used in `get_state(...)["state"]`.
STATE_UPLOADING = "uploading"
STATE_TRANSCODING = "transcoding"
STATE_ASR_RUNNING = "asr_running"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"


_RunnerFn = Callable[[str], Awaitable[None]]


def reset() -> None:
    """Drop all in-memory state; used by tests."""
    _inflight.clear()
    _progress.clear()
    _state.clear()
    _error_code.clear()


def is_pending(meeting_id: str) -> bool:
    """True iff the meeting has an in-flight ASR task."""
    task = _inflight.get(meeting_id)
    return task is not None and not task.done()


def get_progress(meeting_id: str) -> ChunksProgress:
    """Return the (mutable) progress record for the meeting.

    Returns an empty `ChunksProgress` when none is registered. Callers
    that need to mutate `processed` / `total` must obtain the entry via
    `set_progress(meeting_id)` so the new record is persisted.
    """
    return _progress.get(meeting_id, ChunksProgress())


def set_state(meeting_id: str, state: str) -> None:
    """Move the meeting into a new pipeline state.

    Used by `pipeline.py` for the pre-ASR transitions (`uploading` →
    `transcoding`). The ASR side is handled internally by
    `spawn_ingest_task` + the `_wrap` wrapper.
    """
    _state[meeting_id] = state


def set_error(meeting_id: str, error_code: str) -> None:
    """Mark the meeting as failed with an `error_code` for the progress
    endpoint. Idempotent — the latest call wins."""
    _state[meeting_id] = STATE_FAILED
    _error_code[meeting_id] = error_code


def get_state(meeting_id: str) -> dict:
    """Polling-friendly snapshot used by GET /offline_ingest_progress.

    Shape: `{state, chunks_processed?, chunks_total?, error_code?}` — the
    optional fields only appear when the state warrants them per spec.
    """
    state = _state.get(meeting_id, "idle")
    payload: dict = {"state": state}

    if state in (STATE_ASR_RUNNING, STATE_COMPLETED):
        progress = _progress.get(meeting_id, ChunksProgress())
        payload["chunks_processed"] = progress.processed
        payload["chunks_total"] = progress.total

    if state == STATE_FAILED:
        error = _error_code.get(meeting_id)
        if error is not None:
            payload["error_code"] = error

    return payload


async def spawn_ingest_task(
    meeting_id: str,
    *,
    runner: _RunnerFn,
    error_code_on_failure: str = "offline_ingest.runner_failed",
) -> bool:
    """Spawn a background ASR coroutine for the meeting.

    `runner` is the actual ASR work — receives `meeting_id` and runs to
    completion. On return the wrapper marks the meeting `completed`; on
    exception it marks `failed` with `error_code_on_failure` and the
    exception is swallowed (callers cannot await a wrapped task in a way
    that re-raises).

    Returns True iff a new task was created, False when one is already
    in-flight for the same meeting (the calling pipeline maps False onto
    HTTP-level `offline_ingest.busy`).
    """
    async with _lock:
        existing = _inflight.get(meeting_id)
        if existing is not None and not existing.done():
            return False

        _state[meeting_id] = STATE_ASR_RUNNING
        _progress[meeting_id] = ChunksProgress()
        _error_code.pop(meeting_id, None)

        task = asyncio.create_task(
            _wrap(meeting_id, runner=runner, error_code_on_failure=error_code_on_failure)
        )
        _inflight[meeting_id] = task
        return True


async def _wrap(
    meeting_id: str,
    *,
    runner: _RunnerFn,
    error_code_on_failure: str,
) -> None:
    """Wrapper around the caller-supplied runner that owns state transitions."""
    try:
        await runner(meeting_id)
    except asyncio.CancelledError:
        logger.info("offline_ingest_runner_cancelled meeting=%s", meeting_id)
        _state[meeting_id] = STATE_FAILED
        _error_code[meeting_id] = "offline_ingest.cancelled"
        raise
    except Exception as exc:
        logger.exception(
            "offline_ingest_runner_failed meeting=%s: %s: %s",
            meeting_id,
            type(exc).__name__,
            exc,
        )
        _state[meeting_id] = STATE_FAILED
        _error_code[meeting_id] = error_code_on_failure
        return
    else:
        _state[meeting_id] = STATE_COMPLETED
    finally:
        _inflight.pop(meeting_id, None)
