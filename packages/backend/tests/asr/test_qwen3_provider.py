"""Qwen3ASRProvider tests — slice-11 task 1.2.

Per spec asr-provider-selection ADDED requirement scenarios:
  * "Qwen3ASRProvider satisfies the ASRProvider Protocol"
  * "First transcribe_chunk loads the model lazily; subsequent calls reuse it"
  * "Calling warmup() twice loads the model exactly once"
  * "Real fixture transcription" — opt-in (requires qwen-asr deps installed
    + ~5GB model downloaded; gated behind MEETING_PLAYBOOK_QWEN3_AVAILABLE=1)

The first three cases monkeypatch `_load_qwen3_model`, so they always run
without hitting torch / qwen-asr / MPS at all.
"""

from __future__ import annotations

import asyncio
import os
import wave
from dataclasses import dataclass
from pathlib import Path

import pytest

from meeting_playbook.asr import qwen3_provider as qwen3_module
from meeting_playbook.asr.base import ASRProvider, TranscriptChunk
from meeting_playbook.asr.qwen3_provider import (
    Qwen3ASRProvider,
    Qwen3UnavailableError,
)

FIXTURE = Path(__file__).parent / "fixtures" / "short_speech_zh.wav"


@dataclass
class _FakeResult:
    text: str
    language: str = "Chinese"


class _FakeQwenModel:
    """Minimal stand-in for qwen_asr.Qwen3ASRModel — returns a fixed transcript."""

    def __init__(self, transcript: str = "你好世界") -> None:
        self._transcript = transcript

    def transcribe(self, *, audio, language=None):
        # Params named to match the real qwen-asr API shape; intentionally unused.
        del audio, language
        return [_FakeResult(text=self._transcript)]


def _patch_loader(monkeypatch, *, transcript: str = "你好世界") -> dict:
    """Replace `_load_qwen3_model` with a counter-and-fake-model factory."""
    stats = {"load_count": 0}

    def _fake_loader(_config):
        stats["load_count"] += 1
        return _FakeQwenModel(transcript=transcript)

    monkeypatch.setattr(qwen3_module, "_load_qwen3_model", _fake_loader)
    return stats


# ─── (a) Protocol structural assertion ──────────────────────────────


def test_qwen3_provider_is_asr_provider_protocol() -> None:
    """A fresh Qwen3ASRProvider satisfies the ASRProvider Protocol."""
    provider = Qwen3ASRProvider()
    assert isinstance(provider, ASRProvider)
    assert provider.name == "qwen3"


# ─── (b) First transcribe_chunk loads model lazily ──────────────────


@pytest.mark.asyncio
async def test_first_transcribe_loads_model(monkeypatch) -> None:
    """The first transcribe_chunk call MUST trigger model load exactly once."""
    stats = _patch_loader(monkeypatch, transcript="第一次")

    provider = Qwen3ASRProvider()
    assert provider._model is None

    result = await provider.transcribe_chunk(b"\x00\x00" * 1600, 16000)

    assert isinstance(result, TranscriptChunk)
    assert result.text == "第一次"
    assert result.asr_provider_used == "qwen3"
    assert result.confidence is None
    assert result.ended_at >= result.started_at
    assert provider._model is not None
    assert stats["load_count"] == 1


# ─── (c) Subsequent calls reuse loaded model ────────────────────────


@pytest.mark.asyncio
async def test_subsequent_transcribe_reuses_model(monkeypatch) -> None:
    """Two consecutive transcribe_chunk calls SHALL share the same loaded model."""
    stats = _patch_loader(monkeypatch, transcript="重用")

    provider = Qwen3ASRProvider()
    await provider.transcribe_chunk(b"\x00\x00" * 1600, 16000)
    first_model_id = id(provider._model)

    await provider.transcribe_chunk(b"\x00\x00" * 1600, 16000)
    second_model_id = id(provider._model)

    assert first_model_id == second_model_id
    assert stats["load_count"] == 1, f"expected one load, got {stats['load_count']}"


# ─── warmup() idempotency + concurrency ─────────────────────────────


@pytest.mark.asyncio
async def test_warmup_loads_model_once(monkeypatch) -> None:
    """warmup() called twice loads the model exactly once."""
    stats = _patch_loader(monkeypatch)

    provider = Qwen3ASRProvider()
    await provider.warmup()
    await provider.warmup()

    assert stats["load_count"] == 1
    assert provider._model is not None


@pytest.mark.asyncio
async def test_warmup_concurrent_calls_load_once(monkeypatch) -> None:
    """Two warmup() calls awaited via asyncio.gather load the model exactly once."""
    stats = {"load_count": 0}

    def _slow_loader(_config):
        stats["load_count"] += 1
        # Simulate a slow loader so concurrent calls actually overlap.
        import time

        time.sleep(0.05)
        return _FakeQwenModel()

    monkeypatch.setattr(qwen3_module, "_load_qwen3_model", _slow_loader)

    provider = Qwen3ASRProvider()
    await asyncio.gather(provider.warmup(), provider.warmup())

    assert stats["load_count"] == 1


# ─── Loader unavailable raises Qwen3UnavailableError ────────────────


@pytest.mark.asyncio
async def test_loader_failure_raises(monkeypatch) -> None:
    """If the loader raises Qwen3UnavailableError, transcribe_chunk propagates it."""

    def _raising_loader(_config):
        raise Qwen3UnavailableError("test stub: MPS not available")

    monkeypatch.setattr(qwen3_module, "_load_qwen3_model", _raising_loader)

    provider = Qwen3ASRProvider()
    with pytest.raises(Qwen3UnavailableError):
        await provider.transcribe_chunk(b"\x00\x00" * 1600, 16000)


# ─── (d) Real fixture transcription — opt-in ────────────────────────

_QWEN3_AVAILABLE = os.getenv("MEETING_PLAYBOOK_QWEN3_AVAILABLE") == "1"


@pytest.mark.skipif(
    not _QWEN3_AVAILABLE,
    reason=(
        "Set MEETING_PLAYBOOK_QWEN3_AVAILABLE=1 after `uv sync` to run the real "
        "Qwen3-ASR-1.7B model on MPS (~5GB FP16 download on first run)."
    ),
)
@pytest.mark.asyncio
async def test_qwen3_transcribes_real_chinese_clip() -> None:
    """Real-fixture sanity test against the qwen-asr-loaded Qwen3 model.

    Slow on first run (~30s for model load + inference on M3 Pro MPS).
    """
    with wave.open(str(FIXTURE), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        audio_bytes = wf.readframes(wf.getnframes())
        sample_rate = wf.getframerate()

    provider = Qwen3ASRProvider()
    result = await provider.transcribe_chunk(
        audio_bytes=audio_bytes,
        sample_rate_hz=sample_rate,
        language_hint="Chinese",
    )

    assert isinstance(result, TranscriptChunk)
    assert result.text.strip() != "", "expected non-empty transcript text"
    assert result.asr_provider_used == "qwen3"
    assert result.ended_at >= result.started_at
