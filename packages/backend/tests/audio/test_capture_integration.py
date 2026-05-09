"""AudioCaptureService against the REAL system input device.

Per spec meeting-session ADDED requirement "Audio capture writes one WAV
file per session under RECORDINGS_DIR" — the protocol-only tests cover
the contract; this test exercises the production sounddevice path.

Skipped automatically when no input device is available (CI, headless).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from meeting_playbook.audio.capture import AudioCaptureService, AudioChunk


def _has_audio_input() -> bool:
    try:
        import sounddevice as sd
    except (ImportError, OSError):
        return False
    try:
        devices = sd.query_devices()
    except Exception:
        return False
    return any(d.get("max_input_channels", 0) > 0 for d in devices)


pytestmark = pytest.mark.skipif(
    not _has_audio_input(),
    reason="no audio input device available — skipped on CI / headless",
)


@pytest.mark.asyncio
async def test_real_device_emits_at_least_one_chunk_and_writes_wav(
    tmp_path: Path,
):
    chunks: list[AudioChunk] = []
    async with AudioCaptureService(
        meeting_id="m_real",
        recordings_dir=tmp_path,
        sample_rate_hz=16000,
        chunk_seconds=1.0,
        silence_warning_after=30.0,
    ) as session:

        async def _drain() -> None:
            async for ev in session.events():
                if isinstance(ev, AudioChunk):
                    chunks.append(ev)
                    if len(chunks) >= 1:
                        return

        try:
            await asyncio.wait_for(_drain(), timeout=4.0)
        except asyncio.TimeoutError:
            pass

    wav_path = tmp_path / "m_real" / "me.wav"
    assert wav_path.exists(), f"WAV not written at {wav_path}"
    assert len(chunks) >= 1, "expected at least one AudioChunk from real device"
