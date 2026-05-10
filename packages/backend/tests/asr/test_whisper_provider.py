"""WhisperProvider integration test — runs faster-whisper against a real WAV.

Per spec meeting-session ADDED requirement scenario "WhisperProvider satisfies
the contract".

Slow on first run (~10–30s for model load + transcription). Subsequent runs
in the same pytest session are fast because the model is cached on the
provider instance, which lives at module scope.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.asr.whisper_provider import WhisperProvider

FIXTURE = Path(__file__).parent / "fixtures" / "short_speech_zh.wav"


def _load_wav_bytes(path: Path) -> tuple[bytes, int]:
    """Return (PCM int16 bytes, sample_rate). 16kHz mono int16 expected."""
    import wave

    with wave.open(str(path), "rb") as w:
        assert w.getnchannels() == 1, "fixture must be mono"
        assert w.getsampwidth() == 2, "fixture must be int16 (sampwidth=2)"
        return w.readframes(w.getnframes()), w.getframerate()


@pytest_asyncio.fixture(scope="module")
async def provider() -> WhisperProvider:
    """Module-scope so the model loads once across all tests in this file."""
    return WhisperProvider()


@pytest.mark.asyncio
async def test_whisper_provider_transcribes_short_chinese_clip(
    provider: WhisperProvider,
):
    audio_bytes, sample_rate = _load_wav_bytes(FIXTURE)
    result = await provider.transcribe_chunk(
        audio_bytes=audio_bytes,
        sample_rate_hz=sample_rate,
        language_hint="zh",
    )

    assert isinstance(result, TranscriptChunk)
    assert result.text.strip() != "", "expected non-empty transcript text"
    assert result.asr_provider_used == "whisper"
    assert result.ended_at > result.started_at
    if result.confidence is not None:
        assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_whisper_provider_reuses_loaded_model(provider: WhisperProvider):
    """Two consecutive calls SHALL share the same underlying WhisperModel."""
    audio_bytes, sample_rate = _load_wav_bytes(FIXTURE)
    await provider.transcribe_chunk(audio_bytes, sample_rate, "zh")
    first_model_id = id(provider._model)  # private-by-convention attr access

    await provider.transcribe_chunk(audio_bytes, sample_rate, "zh")
    assert id(provider._model) == first_model_id


# ─── Slice 7: warmup() ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_warmup_loads_model_once(monkeypatch):
    """warmup() called twice loads the model exactly once (idempotent)."""

    from meeting_playbook.asr import whisper_provider as wp_module

    load_count = 0

    class _DummyModel:
        def __init__(self, *a, **kw):
            nonlocal load_count
            load_count += 1

    monkeypatch.setattr(wp_module, "WhisperModel", _DummyModel)

    p = WhisperProvider()
    await p.warmup()
    await p.warmup()

    assert load_count == 1, f"expected exactly one load, got {load_count}"
    assert p._model is not None


@pytest.mark.asyncio
async def test_warmup_concurrent_calls_load_once(monkeypatch):
    """Two warmup() calls awaited via asyncio.gather load the model exactly once."""
    import asyncio

    from meeting_playbook.asr import whisper_provider as wp_module

    load_count = 0

    class _SlowModel:
        def __init__(self, *a, **kw):
            nonlocal load_count
            load_count += 1
            # Simulate an ~80ms model construction so concurrent warmup() calls
            # actually overlap (would race without the internal lock).
            import time

            time.sleep(0.08)

    monkeypatch.setattr(wp_module, "WhisperModel", _SlowModel)

    p = WhisperProvider()
    await asyncio.gather(p.warmup(), p.warmup())

    assert load_count == 1, (
        f"expected exactly one load even with concurrent warmup, got {load_count}"
    )
