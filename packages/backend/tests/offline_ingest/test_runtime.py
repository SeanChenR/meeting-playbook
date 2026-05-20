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


# ─── asr-runtime-extraction tests (task 9.1) ────────────────────────────


@pytest.mark.asyncio
async def test_runtime_unavailable_triggers_retry_then_fail(monkeypatch):
    """When the asr-runtime returns `asr.runtime_unavailable` for every
    attempt, the chunk-transcribe helper SHALL retry 3 times with
    exponential backoff (2 / 4 / 8 seconds), then surface the failure
    through `runtime.set_state(meeting_id, "failed")` + the structured
    error_code. Per asr-runtime-extraction Decision 7."""
    from meeting_playbook.asr.remote_runtime_client import AsrRuntimeUnavailableError
    from meeting_playbook.offline_ingest import pipeline, runtime

    # Capture sleeps without actually waiting.
    sleeps: list[float] = []

    async def _record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(pipeline.asyncio, "sleep", _record_sleep)

    class _AlwaysFailingProvider:
        name = "qwen3"
        call_count = 0

        async def warmup(self):
            return None

        async def transcribe_chunk(self, *, audio_bytes, sample_rate_hz, language_hint=None):
            self.call_count += 1
            raise AsrRuntimeUnavailableError("stub: runtime down")

    runtime.reset()
    progress = runtime.get_progress("m_retry_fail")

    provider = _AlwaysFailingProvider()
    result = await pipeline._transcribe_with_runtime_retry(
        provider=provider,
        audio_bytes=bytes(16000 * 2),
        sample_rate_hz=16000,
        meeting_id="m_retry_fail",
        progress=progress,
    )

    assert result is None
    # 4 attempts total (initial + 3 retries) — the helper retries after
    # the first failure, so call_count counts attempts.
    assert provider.call_count == 4
    # Backoff sequence is 2 / 4 / 8 — three sleeps between four attempts.
    assert sleeps == [2.0, 4.0, 8.0]
    state = runtime.get_state("m_retry_fail")
    assert state["state"] == "failed", state
    assert state.get("error_code") == "asr.runtime_unavailable", state
