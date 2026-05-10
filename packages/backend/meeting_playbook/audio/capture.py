"""AudioCaptureService — async-context-managed microphone capture + WAV writer.

Per slice-06 design:
- Async context manager: `async with AudioCaptureService(...) as session: ...`
- `session.events()` is an async iterator yielding `AudioChunk` (every
  `chunk_seconds` of accumulated PCM) and `SilenceWarning` (when sustained
  silence exceeds the threshold).
- The default `_input_stream_factory` opens a `sounddevice.RawInputStream`
  on the system default input device; the constructor's `_input_stream_factory`
  parameter is the test seam — protocol tests pass scripted PCM frames
  without touching the audio subsystem.
- On context-manager exit the entire captured stream is written atomically
  to `{recordings_dir}/{meeting_id}/me.wav` (16-bit mono PCM at the
  configured sample rate). The base directory is created on demand.
"""

from __future__ import annotations

import asyncio
import contextlib
import math
import wave
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import numpy as np

Stream = Literal["me", "counterparty"]

# Silence threshold expressed as int16 RMS — anything quieter than this for
# `silence_warning_after` seconds triggers a SilenceWarning. ~50 corresponds
# to roughly -56 dBFS, well below normal speech.
_SILENCE_RMS_THRESHOLD = 50.0

# Maximum number of chunks the queue may hold before back-pressure kicks in
# (60 seconds of audio at chunk_seconds=10 → 6). Bounding the queue prevents
# unbounded memory growth if transcription falls behind.
_MAX_QUEUE_CHUNKS = 6


@dataclass(frozen=True)
class AudioChunk:
    audio_bytes: bytes
    sample_rate_hz: int
    started_at: datetime
    ended_at: datetime
    stream: Stream = "me"


@dataclass(frozen=True)
class SilenceWarning:
    since: datetime
    stream: Stream = "me"


class CaptureDeviceUnavailable(Exception):
    """Raised when `sounddevice` cannot open an input stream."""


def _default_input_stream_factory(
    sample_rate_hz: int,
    device: int | str | None = None,
) -> Callable[[asyncio.Queue[bytes]], asyncio.Task[None]]:
    """Production factory wrapping `sounddevice.RawInputStream`.

    `device` is forwarded to `RawInputStream(device=...)`. None → system default
    input device. A string is treated as a device name (sounddevice resolves it).
    """

    def factory(queue: asyncio.Queue[bytes]) -> asyncio.Task[None]:
        async def _open_and_pump() -> None:
            import sounddevice as sd  # local import keeps test paths light

            loop = asyncio.get_running_loop()

            def _callback(indata, _frames, _time_info, _status) -> None:
                # Called from the audio thread; hop back to the loop.
                loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

            try:
                stream = sd.RawInputStream(
                    samplerate=sample_rate_hz,
                    channels=1,
                    dtype="int16",
                    callback=_callback,
                    device=device,
                )
            except Exception as exc:  # PortAudioError, etc.
                raise CaptureDeviceUnavailable(f"Could not open input stream: {exc}") from exc

            with stream:
                # Run until cancelled by the consumer task on context exit.
                while True:
                    await asyncio.sleep(3600)

        return asyncio.create_task(_open_and_pump())

    return factory


def _rms(int16_bytes: bytes) -> float:
    if not int16_bytes:
        return 0.0
    samples = np.frombuffer(int16_bytes, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return 0.0
    return float(math.sqrt(float(np.mean(samples * samples))))


class AudioCaptureService:
    """Async-context-managed mic capture for one meeting.

    Args:
        meeting_id: Used to compute the WAV file path.
        recordings_dir: Base directory; `me.wav` is written under
            `{recordings_dir}/{meeting_id}/`.
        sample_rate_hz: Capture sample rate. 16kHz is right for Whisper.
        chunk_seconds: How often to emit an `AudioChunk` event.
        silence_warning_after: Sustained silence (RMS below threshold) for
            this many seconds emits a single `SilenceWarning`.
        _input_stream_factory: Test seam. Production callers omit this and
            the default factory opens a real `sounddevice.RawInputStream`.
    """

    def __init__(
        self,
        *,
        meeting_id: str,
        recordings_dir: Path,
        sample_rate_hz: int = 16000,
        chunk_seconds: float = 10.0,
        silence_warning_after: float = 30.0,
        device_name: str | int | None = None,
        stream_label: Stream = "me",
        _input_stream_factory: Callable[[asyncio.Queue[bytes]], asyncio.Task[None]] | None = None,
    ) -> None:
        self._meeting_id = meeting_id
        self._recordings_dir = Path(recordings_dir).expanduser()
        self._sample_rate = sample_rate_hz
        self._chunk_seconds = chunk_seconds
        self._silence_after = silence_warning_after
        self._stream_label: Stream = stream_label
        self._factory = _input_stream_factory or _default_input_stream_factory(
            sample_rate_hz, device=device_name
        )

        self._raw_queue: asyncio.Queue[bytes] = asyncio.Queue()
        # event_queue carries `None` as a graceful-shutdown sentinel.
        self._event_queue: asyncio.Queue[AudioChunk | SilenceWarning | None] = asyncio.Queue(
            maxsize=_MAX_QUEUE_CHUNKS * 4
        )
        self._stream_task: asyncio.Task[None] | None = None
        self._consumer_task: asyncio.Task[None] | None = None
        self._buffer = bytearray()
        self._closed = False
        self._stop_requested: asyncio.Event = asyncio.Event()

    @property
    def wav_path(self) -> Path:
        return self._recordings_dir / self._meeting_id / f"{self._stream_label}.wav"

    async def __aenter__(self) -> AudioCaptureService:
        self.wav_path.parent.mkdir(parents=True, exist_ok=True)
        self._stream_task = self._factory(self._raw_queue)
        self._consumer_task = asyncio.create_task(self._consume())
        return self

    async def stop(self) -> None:
        """Request graceful shutdown.

        Idempotent. After this returns, the consumer task will:
          - stop reading new audio from the input stream
          - flush any remaining bytes in chunk_buf as a final AudioChunk
            (even if shorter than chunk_seconds — preserves the last partial
            buffer when the user clicks End mid-utterance)
          - put None into event_queue as the end-of-stream sentinel
          - exit

        `events()` consumers see the sentinel and return naturally;
        `service.run` exits without being cancelled, so any in-flight
        `transcribe_chunk` finishes properly before WAV finalization.
        """
        self._stop_requested.set()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # Trigger graceful drain (idempotent).
        self._stop_requested.set()
        # Wait for consumer to finish flushing + emit sentinel.
        if self._consumer_task and not self._consumer_task.done():
            try:
                await asyncio.wait_for(self._consumer_task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError, Exception):
                if not self._consumer_task.done():
                    self._consumer_task.cancel()
                    with contextlib.suppress(BaseException):
                        await self._consumer_task
        # Stream task is the sounddevice loop — cancel it; it never exits on its own.
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            with contextlib.suppress(BaseException):
                await self._stream_task
        self._closed = True
        # Atomic WAV write — write to .tmp then rename.
        tmp_path = self.wav_path.with_suffix(".tmp")
        with wave.open(str(tmp_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)  # int16
            w.setframerate(self._sample_rate)
            w.writeframes(bytes(self._buffer))
        tmp_path.replace(self.wav_path)

    async def events(self) -> AsyncIterator[AudioChunk | SilenceWarning]:
        while not self._closed:
            try:
                ev = await asyncio.wait_for(self._event_queue.get(), timeout=0.5)
            except TimeoutError:
                if self._closed:
                    break
                continue
            if ev is None:
                # Graceful end-of-stream sentinel from `_consume`.
                return
            yield ev

    async def _consume(self) -> None:
        """Drain raw PCM into chunks + run silence detection.

        Exits gracefully when `_stop_requested` is set: flushes the remaining
        chunk_buf as a final (possibly short) AudioChunk and emits a None
        sentinel so the consumer side knows there is no more.
        """
        bytes_per_chunk = int(self._sample_rate * self._chunk_seconds) * 2  # int16
        chunk_buf = bytearray()
        chunk_started_at = datetime.now(UTC)
        silent_since: datetime | None = None
        warning_emitted_for: datetime | None = None

        while True:
            if self._stop_requested.is_set() and self._raw_queue.empty():
                # Flush trailing bytes as one last (partial) chunk so the
                # last few seconds of speech don't get lost when the user
                # clicks End mid-utterance.
                if chunk_buf:
                    payload = bytes(chunk_buf)
                    chunk_buf.clear()
                    ended_at = datetime.now(UTC)
                    await self._event_queue.put(
                        AudioChunk(
                            audio_bytes=payload,
                            sample_rate_hz=self._sample_rate,
                            started_at=chunk_started_at,
                            ended_at=ended_at,
                            stream=self._stream_label,
                        )
                    )
                # Sentinel signalling end-of-stream.
                await self._event_queue.put(None)
                return

            try:
                frame = await asyncio.wait_for(self._raw_queue.get(), timeout=0.05)
            except TimeoutError:
                # Periodically re-check silence even when no new audio arrives.
                if silent_since is not None and warning_emitted_for != silent_since:
                    elapsed = (datetime.now(UTC) - silent_since).total_seconds()
                    if elapsed >= self._silence_after:
                        await self._emit_silence_warning(silent_since)
                        warning_emitted_for = silent_since
                continue

            chunk_buf.extend(frame)
            self._buffer.extend(frame)

            # Silence detection on this incoming frame.
            rms = _rms(frame)
            now = datetime.now(UTC)
            if rms < _SILENCE_RMS_THRESHOLD:
                if silent_since is None:
                    silent_since = now
                elapsed = (now - silent_since).total_seconds()
                if elapsed >= self._silence_after and warning_emitted_for != silent_since:
                    await self._emit_silence_warning(silent_since)
                    warning_emitted_for = silent_since
            else:
                silent_since = None
                warning_emitted_for = None

            # Emit a full AudioChunk when the buffer reaches the threshold.
            while len(chunk_buf) >= bytes_per_chunk:
                payload = bytes(chunk_buf[:bytes_per_chunk])
                chunk_buf = chunk_buf[bytes_per_chunk:]
                ended_at = datetime.now(UTC)
                chunk = AudioChunk(
                    audio_bytes=payload,
                    sample_rate_hz=self._sample_rate,
                    started_at=chunk_started_at,
                    ended_at=ended_at,
                    stream=self._stream_label,
                )
                await self._event_queue.put(chunk)
                chunk_started_at = ended_at

    async def _emit_silence_warning(self, since: datetime) -> None:
        await self._event_queue.put(SilenceWarning(since=since, stream=self._stream_label))


__all__ = [
    "AudioCaptureService",
    "AudioChunk",
    "CaptureDeviceUnavailable",
    "SilenceWarning",
]
