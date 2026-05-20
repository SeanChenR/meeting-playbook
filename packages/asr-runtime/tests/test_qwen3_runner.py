"""Qwen3Runner unit tests (asr-runtime task 2.1 / 2.2).

The runner's job is to wrap qwen-asr's `Qwen3ASRModel` behind a tiny async
surface so the HTTP / WebSocket routes don't need to care about model
internals. These tests exercise the *contract* (silent input → empty text,
concurrent calls serialise via the internal `asyncio.Lock`) rather than the
upstream model accuracy — the heavy `qwen-asr` dep is monkeypatched so the
tests stay fast and CPU-only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from meeting_playbook_asr_runtime.qwen3_runner import Qwen3Runner


@pytest.fixture
def _patched_model(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, int]]:
    """Replace the upstream model loader so tests don't need the 5GB weights."""

    counters: dict[str, int] = {"calls_active": 0, "max_calls_active": 0}

    class _StubModel:
        def transcribe(self, _pcm: bytes, sample_rate: int) -> dict[str, str]:
            counters["calls_active"] += 1
            counters["max_calls_active"] = max(
                counters["max_calls_active"], counters["calls_active"]
            )
            try:
                # Mimic the real model: silence → empty text. Non-silent
                # audio would carry decoded characters here.
                is_silent = all(b == 0 for b in _pcm[:64])
                text = "" if is_silent else "hello"
                return {"text": text}
            finally:
                counters["calls_active"] -= 1

    def _fake_loader(_config: object) -> _StubModel:
        return _StubModel()

    monkeypatch.setattr(
        "meeting_playbook_asr_runtime.qwen3_runner._load_qwen3_model",
        _fake_loader,
    )
    yield counters


@pytest.mark.asyncio
async def test_silent_returns_empty_text(_patched_model: dict[str, int]) -> None:
    """10 seconds of int16 silence → TranscriptChunk with text == ''."""

    runner = Qwen3Runner()
    silent_pcm = bytes(16000 * 2 * 10)  # 16kHz int16 × 10s, all zeros

    before = datetime.now(UTC)
    chunk = await runner.transcribe(silent_pcm, sample_rate_hz=16000)
    after = datetime.now(UTC)

    assert chunk.text == ""
    assert chunk.started_at is not None
    assert chunk.ended_at is not None
    assert before <= chunk.started_at <= chunk.ended_at <= after


@pytest.mark.asyncio
async def test_concurrent_calls_serialized(_patched_model: dict[str, int]) -> None:
    """asyncio.gather of two chunks → both succeed, but lock guarantees
    at most one call is inside the critical section at any time."""

    runner = Qwen3Runner()
    silent_pcm = bytes(16000 * 2 * 1)  # 1s silence

    chunk_a, chunk_b = await asyncio.gather(
        runner.transcribe(silent_pcm, sample_rate_hz=16000),
        runner.transcribe(silent_pcm, sample_rate_hz=16000),
    )

    assert chunk_a.text == ""
    assert chunk_b.text == ""
    # The stub model bumps `calls_active` on enter and decrements on exit.
    # If the lock truly serialises, the high-water mark MUST be 1.
    assert _patched_model["max_calls_active"] == 1
