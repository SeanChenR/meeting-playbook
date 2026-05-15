"""Offline-ingest runtime registry tests — slice-14 task 4.2.

Verifies the spec scenarios under
"Pipeline writes a single offline recording row and spawns ASR task" and
"GET /api/meetings/{id}/offline_ingest_progress reports pipeline state":

- spawn → state transitions to `asr_running`
- second spawn while in-flight → returns False
- task completes → state transitions to `completed`
- task raises → state transitions to `failed` with `error_code`

Runtime is tested in isolation from the real ASR pipeline via a
caller-supplied async `runner` coroutine, mirroring the rerun runtime's
shape (slice-11 task 5.1).
"""

from __future__ import annotations

import asyncio

import pytest

from meeting_playbook.offline_ingest import runtime


@pytest.fixture(autouse=True)
def _reset():
    runtime.reset()
    yield
    runtime.reset()


@pytest.mark.asyncio
async def test_spawn_marks_state_asr_running() -> None:
    held = asyncio.Event()

    async def _runner(meeting_id: str) -> None:
        await held.wait()

    started = await runtime.spawn_ingest_task("m_x", runner=_runner)
    assert started is True

    # Yield once so the spawned task actually starts running.
    await asyncio.sleep(0)

    state = runtime.get_state("m_x")
    assert state["state"] == "asr_running", state

    # Clean up so the test does not leave a dangling task.
    held.set()
    await runtime._inflight["m_x"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_second_spawn_while_inflight_returns_false() -> None:
    held = asyncio.Event()

    async def _runner(meeting_id: str) -> None:
        await held.wait()

    first = await runtime.spawn_ingest_task("m_busy", runner=_runner)
    assert first is True
    await asyncio.sleep(0)

    second = await runtime.spawn_ingest_task("m_busy", runner=_runner)
    assert second is False, "second spawn must return False per busy contract"

    held.set()
    await runtime._inflight["m_busy"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_task_completion_transitions_to_completed() -> None:
    async def _runner(meeting_id: str) -> None:
        # Pretend ASR ran instantly.
        return None

    started = await runtime.spawn_ingest_task("m_ok", runner=_runner)
    assert started is True

    # Wait for the spawned task to finish.
    task = runtime._inflight["m_ok"]  # type: ignore[index]
    await task

    state = runtime.get_state("m_ok")
    assert state["state"] == "completed", state


@pytest.mark.asyncio
async def test_task_exception_transitions_to_failed_with_error_code() -> None:
    async def _runner(meeting_id: str) -> None:
        raise RuntimeError("boom")

    started = await runtime.spawn_ingest_task(
        "m_bad", runner=_runner, error_code_on_failure="offline_ingest.transcode_failed"
    )
    assert started is True

    task = runtime._inflight.get("m_bad")  # type: ignore[attr-defined]
    if task is not None:
        # Exception swallowed by the wrapper; awaiting must not re-raise.
        await task

    state = runtime.get_state("m_bad")
    assert state["state"] == "failed", state
    assert state.get("error_code") == "offline_ingest.transcode_failed", state
