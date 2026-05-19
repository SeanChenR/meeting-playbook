"""AudioCaptureService protocol-only tests — no real audio device.

Per spec meeting-session ADDED requirements "Audio capture writes one WAV
file per session under RECORDINGS_DIR" + "Silence in the audio stream is
reported within 30 seconds".

We inject a stub `_input_stream_factory` that yields scripted PCM frames
so this file runs everywhere (CI included).
"""

from __future__ import annotations

import asyncio
import contextlib
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from meeting_playbook.audio.capture import (
    AudioCaptureService,
    AudioChunk,
    SilenceWarning,
)

SAMPLE_RATE = 16000


def _silence_frame(seconds: float) -> bytes:
    """Generate `seconds` of silence as int16 PCM."""
    samples = np.zeros(int(SAMPLE_RATE * seconds), dtype=np.int16)
    return samples.tobytes()


def _voice_frame(seconds: float, amplitude: int = 8000) -> bytes:
    """Generate `seconds` of a synthetic ~440Hz sine wave (well above silence threshold)."""
    n = int(SAMPLE_RATE * seconds)
    t = np.arange(n) / SAMPLE_RATE
    wave_arr = (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
    return wave_arr.tobytes()


def _scripted_factory(
    frames: list[bytes],
) -> Callable[[asyncio.Queue[bytes]], asyncio.Task[None]]:
    """Return a factory that pushes pre-recorded frames into the audio queue.

    Mimics the production sounddevice callback: the real impl would be a
    `RawInputStream` whose callback writes into the queue from the audio
    thread; here we just push synchronously then signal end-of-stream.
    """

    def factory(queue: asyncio.Queue[bytes]) -> asyncio.Task[None]:
        async def _push() -> None:
            for f in frames:
                await queue.put(f)
                # tiny await so the consumer task can interleave
                await asyncio.sleep(0)
            # No sentinel — context-manager exit closes the iterator.

        return asyncio.create_task(_push())

    return factory


@pytest.mark.asyncio
async def test_capture_writes_wav_on_exit_with_full_stream(tmp_path: Path):
    frames = [_voice_frame(1.0), _voice_frame(1.0)]  # 2 seconds total

    async with AudioCaptureService(
        meeting_id="m_test",
        recordings_dir=tmp_path,
        sample_rate_hz=SAMPLE_RATE,
        chunk_seconds=1.0,
        silence_warning_after=30.0,
        _input_stream_factory=_scripted_factory(frames),
    ) as session:
        # Drain a couple of events then exit.
        events_received: list[AudioChunk | SilenceWarning] = []

        async def _drain() -> None:
            async for ev in session.events():
                events_received.append(ev)
                if len(events_received) >= 2:
                    return

        await asyncio.wait_for(_drain(), timeout=5.0)

    wav_path = tmp_path / "m_test" / "me.wav"
    assert wav_path.exists(), f"WAV file should exist at {wav_path}"

    with wave.open(str(wav_path), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == SAMPLE_RATE
        n_frames = w.getnframes()
        # Expected ~2 seconds worth of samples
        assert n_frames >= int(SAMPLE_RATE * 1.5)


@pytest.mark.asyncio
async def test_capture_yields_one_audio_chunk_per_chunk_seconds(tmp_path: Path):
    frames = [_voice_frame(1.0)] * 3  # 3 seconds

    chunks: list[AudioChunk] = []
    async with AudioCaptureService(
        meeting_id="m_test",
        recordings_dir=tmp_path,
        sample_rate_hz=SAMPLE_RATE,
        chunk_seconds=1.0,
        silence_warning_after=30.0,
        _input_stream_factory=_scripted_factory(frames),
    ) as session:

        async def _drain() -> None:
            async for ev in session.events():
                if isinstance(ev, AudioChunk):
                    chunks.append(ev)
                if len(chunks) >= 3:
                    return

        await asyncio.wait_for(_drain(), timeout=5.0)

    assert len(chunks) >= 2, f"expected at least 2 audio chunks, got {len(chunks)}"
    # Each chunk should carry approximately chunk_seconds worth of int16 samples.
    expected_bytes = int(SAMPLE_RATE * 1.0) * 2  # 2 bytes per int16
    for ch in chunks[:2]:
        assert abs(len(ch.audio_bytes) - expected_bytes) <= expected_bytes // 5


@pytest.mark.asyncio
async def test_capture_emits_silence_warning_after_threshold(tmp_path: Path):
    """Silence frames spanning > silence_warning_after seconds → exactly one warning."""
    # 4 chunks of silence at chunk_seconds=0.5, threshold=1.5s → warning fires once
    frames = [_silence_frame(0.5)] * 8

    events: list[AudioChunk | SilenceWarning] = []
    async with AudioCaptureService(
        meeting_id="m_test",
        recordings_dir=tmp_path,
        sample_rate_hz=SAMPLE_RATE,
        chunk_seconds=0.5,
        silence_warning_after=1.5,
        _input_stream_factory=_scripted_factory(frames),
    ) as session:

        async def _drain() -> None:
            async for ev in session.events():
                events.append(ev)
                if any(isinstance(e, SilenceWarning) for e in events):
                    # Continue a bit longer to verify dedup.
                    if sum(1 for e in events if isinstance(e, SilenceWarning)) >= 2:
                        return
                    if len(events) >= 8:
                        return

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_drain(), timeout=5.0)

    warnings = [e for e in events if isinstance(e, SilenceWarning)]
    assert len(warnings) == 1, (
        f"expected exactly one silence warning, got {len(warnings)} out of {len(events)} events"
    )


@pytest.mark.asyncio
async def test_init_accepts_device_name_and_stream_label(tmp_path: Path):
    """Slice-07: AudioCaptureService takes device_name + stream_label kwargs.

    The stream_label is carried on every emitted event so SessionService can
    route per-stream. The wav_path uses the label so two instances write to
    distinct files (me.wav + counterparty.wav).
    """
    frames = [_voice_frame(0.5)]

    chunks: list[AudioChunk] = []
    warnings: list[SilenceWarning] = []
    async with AudioCaptureService(
        meeting_id="m_dual",
        recordings_dir=tmp_path,
        sample_rate_hz=SAMPLE_RATE,
        chunk_seconds=0.5,
        silence_warning_after=30.0,
        device_name="BlackHole 2ch",  # accepted; ignored by scripted factory
        stream_label="counterparty",
        _input_stream_factory=_scripted_factory(frames),
    ) as session:
        assert session.wav_path == tmp_path / "m_dual" / "counterparty.wav"

        async def _drain() -> None:
            async for ev in session.events():
                if isinstance(ev, AudioChunk):
                    chunks.append(ev)
                elif isinstance(ev, SilenceWarning):
                    warnings.append(ev)
                if chunks:
                    return

        await asyncio.wait_for(_drain(), timeout=5.0)

    assert chunks, "should have at least one AudioChunk"
    for ch in chunks:
        assert ch.stream == "counterparty", (
            f"AudioChunk emitted by counterparty service must carry stream='counterparty', got {ch.stream!r}"
        )

    # WAV written under the labeled filename (not me.wav).
    wav_path = tmp_path / "m_dual" / "counterparty.wav"
    assert wav_path.exists()


@pytest.mark.asyncio
async def test_default_stream_label_is_me_keeping_slice6_behaviour(tmp_path: Path):
    """Slice-07 must not break Slice-06: default stream_label='me' + me.wav path."""
    frames = [_voice_frame(0.5)]

    chunks: list[AudioChunk] = []
    async with AudioCaptureService(
        meeting_id="m_solo",
        recordings_dir=tmp_path,
        sample_rate_hz=SAMPLE_RATE,
        chunk_seconds=0.5,
        silence_warning_after=30.0,
        _input_stream_factory=_scripted_factory(frames),
    ) as session:
        assert session.wav_path == tmp_path / "m_solo" / "me.wav"

        async def _drain() -> None:
            async for ev in session.events():
                if isinstance(ev, AudioChunk):
                    chunks.append(ev)
                if chunks:
                    return

        await asyncio.wait_for(_drain(), timeout=5.0)

    for ch in chunks:
        assert ch.stream == "me"
