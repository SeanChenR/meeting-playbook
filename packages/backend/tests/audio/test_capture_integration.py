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
        except TimeoutError:
            pass

    wav_path = tmp_path / "m_real" / "me.wav"
    assert wav_path.exists(), f"WAV not written at {wav_path}"
    assert len(chunks) >= 1, "expected at least one AudioChunk from real device"


def _has_blackhole() -> bool:
    """Skip the dual-stream test unless BlackHole is installed."""
    try:
        from meeting_playbook.audio.devices import find_blackhole_device

        return find_blackhole_device(env_override=None) is not None
    except Exception:
        return False


@pytest.mark.skipif(
    not _has_blackhole(),
    reason="BlackHole 2ch not installed — skipped",
)
@pytest.mark.asyncio
async def test_dual_stream_writes_two_files(tmp_path: Path):
    """Slice-07: two AudioCaptureService instances each write their own WAV."""
    import wave

    from meeting_playbook.audio.devices import find_blackhole_device, find_mic_device

    bh_idx = find_blackhole_device(env_override=None)
    mic_idx = find_mic_device(env_override=None)
    assert bh_idx is not None

    me_chunks: list[AudioChunk] = []
    cp_chunks: list[AudioChunk] = []

    async with (
        AudioCaptureService(
            meeting_id="m_dual",
            recordings_dir=tmp_path,
            sample_rate_hz=16000,
            chunk_seconds=0.5,
            silence_warning_after=30.0,
            device_name=mic_idx,
            stream_label="me",
        ) as me_sess,
        AudioCaptureService(
            meeting_id="m_dual",
            recordings_dir=tmp_path,
            sample_rate_hz=16000,
            chunk_seconds=0.5,
            silence_warning_after=30.0,
            device_name=bh_idx,
            stream_label="counterparty",
        ) as cp_sess,
    ):

        async def _drain_me() -> None:
            async for ev in me_sess.events():
                if isinstance(ev, AudioChunk):
                    me_chunks.append(ev)
                    if len(me_chunks) >= 1:
                        return

        async def _drain_cp() -> None:
            async for ev in cp_sess.events():
                if isinstance(ev, AudioChunk):
                    cp_chunks.append(ev)
                    if len(cp_chunks) >= 1:
                        return

        try:
            await asyncio.wait_for(asyncio.gather(_drain_me(), _drain_cp()), timeout=4.0)
        except TimeoutError:
            pass

    me_wav = tmp_path / "m_dual" / "me.wav"
    cp_wav = tmp_path / "m_dual" / "counterparty.wav"
    assert me_wav.exists(), f"me WAV not written at {me_wav}"
    assert cp_wav.exists(), f"counterparty WAV not written at {cp_wav}"

    for path in (me_wav, cp_wav):
        with wave.open(str(path), "rb") as w:
            assert w.getnchannels() == 1, f"{path} should be mono"

    for ch in me_chunks:
        assert ch.stream == "me"
    for ch in cp_chunks:
        assert ch.stream == "counterparty"
