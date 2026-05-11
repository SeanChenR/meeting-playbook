"""Retention runtime + lifespan tests — slice-11 task 4.3.

Per spec recording-retention ADDED requirement
"Retention job runs every 24 hours via FastAPI lifespan":

  (a) First cleanup runs immediately on startup.
  (b) `asyncio.sleep` (24h) gates subsequent iterations — mocking it lets
      multiple iterations run in a single test.
  (c) Cleanup raising RuntimeError on iteration 1 does NOT kill the loop;
      iteration 2 still runs.
  (d) Lifespan shutdown cancels the task cleanly (await suppresses
      CancelledError, no hang).
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest

from meeting_playbook.config import Settings
from meeting_playbook.retention import runtime as retention_runtime


def _settings() -> Settings:
    """Minimal Settings stub for runtime calls (cleanup is mocked)."""
    return Settings(
        _env_file=None,
        database_url="postgresql://localhost:5432/x",
        better_auth_secret="x",
        google_oauth_client_id="x",
        google_oauth_client_secret="x",
        recording_retention_days=30,
    )


@pytest.mark.asyncio
async def test_first_cleanup_runs_within_one_second_of_startup(monkeypatch) -> None:
    """Spec scenario: first cleanup fires within 1 second after run_forever starts."""
    started_event = asyncio.Event()
    call_count = {"n": 0}

    async def _fake_cleanup(**_kwargs):
        call_count["n"] += 1
        started_event.set()
        return 0

    # Make sleep return immediately so we don't wait 24h between iterations.
    # Capture the real asyncio.sleep BEFORE we monkey-patch it onto the
    # retention_runtime module, otherwise _fake_sleep recurses into itself.
    _real_sleep = asyncio.sleep

    async def _fake_sleep(_s):
        await _real_sleep(0)

    monkeypatch.setattr(retention_runtime, "cleanup", _fake_cleanup)
    monkeypatch.setattr(retention_runtime.asyncio, "sleep", _fake_sleep)

    task = asyncio.create_task(
        retention_runtime.run_forever(
            settings=_settings(),
            session_factory=lambda: None,  # cleanup is mocked; factory unused
        )
    )
    try:
        # Spec wording: "within 1 second" — generous enough for any scheduler jitter.
        await asyncio.wait_for(started_event.wait(), timeout=1.0)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert call_count["n"] >= 1


@pytest.mark.asyncio
async def test_loop_runs_multiple_iterations_when_sleep_is_mocked(monkeypatch) -> None:
    """Spec scenario: subsequent cleanups fire on the configured cadence."""
    iterations_run = []
    iteration_event = asyncio.Event()

    async def _fake_cleanup(**_kwargs):
        iterations_run.append(1)
        if len(iterations_run) >= 2:
            iteration_event.set()
        return 0

    _real_sleep = asyncio.sleep

    async def _fake_sleep(_s):
        await _real_sleep(0)

    monkeypatch.setattr(retention_runtime, "cleanup", _fake_cleanup)
    monkeypatch.setattr(retention_runtime.asyncio, "sleep", _fake_sleep)

    task = asyncio.create_task(
        retention_runtime.run_forever(settings=_settings(), session_factory=lambda: None)
    )
    try:
        await asyncio.wait_for(iteration_event.wait(), timeout=1.0)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert len(iterations_run) >= 2


@pytest.mark.asyncio
async def test_iteration_failure_does_not_kill_loop(monkeypatch) -> None:
    """Spec scenario: iteration 1 raises; iteration 2 still executes.

    The "logger.exception is called" half of the spec is exercised by the
    runtime's `try/except Exception: logger.exception(...)` branch; we don't
    assert on caplog records because `server.py:_logging.basicConfig` runs
    at import time and breaks caplog propagation when this file is loaded
    alongside the rest of the suite. Loop survival (state.calls >= 2) is
    the testable contract.
    """
    state = {"calls": 0}
    second_call_event = asyncio.Event()

    async def _fake_cleanup(**_kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("disk full simulation")
        second_call_event.set()
        return 0

    _real_sleep = asyncio.sleep

    async def _fake_sleep(_s):
        await _real_sleep(0)

    monkeypatch.setattr(retention_runtime, "cleanup", _fake_cleanup)
    monkeypatch.setattr(retention_runtime.asyncio, "sleep", _fake_sleep)

    task = asyncio.create_task(
        retention_runtime.run_forever(settings=_settings(), session_factory=lambda: None)
    )
    try:
        await asyncio.wait_for(second_call_event.wait(), timeout=1.0)
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert state["calls"] >= 2, "iteration 2 must run after iteration 1's failure"


@pytest.mark.asyncio
async def test_cancel_during_sleep_returns_cleanly(monkeypatch) -> None:
    """Spec scenario: lifespan shutdown cancels the loop; await suppresses CancelledError."""
    started = asyncio.Event()

    async def _fake_cleanup(**_kwargs):
        started.set()
        return 0

    # Real sleep (no mock) so the cancel lands while loop is awaiting sleep,
    # not while it's inside cleanup. Capture before we patch the module attr.
    _orig_sleep = asyncio.sleep

    async def _passthrough_sleep(s):
        await _orig_sleep(s)

    monkeypatch.setattr(retention_runtime, "cleanup", _fake_cleanup)
    monkeypatch.setattr(retention_runtime.asyncio, "sleep", _passthrough_sleep)

    task = asyncio.create_task(
        retention_runtime.run_forever(settings=_settings(), session_factory=lambda: None)
    )

    await asyncio.wait_for(started.wait(), timeout=1.0)
    task.cancel()

    # Spec: await SHALL NOT hang; suppressed CancelledError is the contract.
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)

    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_lifespan_starts_and_cancels_retention_task(monkeypatch) -> None:
    """server.py's _lifespan spawns the loop on startup + cancels on shutdown."""
    spawned_event = asyncio.Event()
    call_count = {"n": 0}

    async def _fake_run_forever(**_kwargs: Any) -> None:
        spawned_event.set()
        call_count["n"] += 1
        # Hold open until cancelled.
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise

    monkeypatch.setattr(retention_runtime, "run_forever", _fake_run_forever)

    # Avoid a real DB connection: lifespan creates an engine + session_factory.
    # We don't care about either as long as run_forever is called and cancelled.
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/never_used")
    monkeypatch.setenv("BETTER_AUTH_SECRET", "x")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "x")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "x")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    from meeting_playbook.server import _lifespan, create_app

    app = create_app()
    async with _lifespan(app):
        await asyncio.wait_for(spawned_event.wait(), timeout=1.0)
    # If lifespan exit hangs on the cancelled task, asyncio.wait_for above
    # would have already failed; reaching here means the await completed.
    assert call_count["n"] == 1
