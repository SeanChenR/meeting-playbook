"""SessionService — per-stream orchestration loop for an active meeting session.

Slice-07 evolution: holds `Mapping[Stream, AudioCaptureService]` +
`Mapping[Stream, ASRProvider]` and spawns one consumer task per stream.
Per-stream failures emit `stream_stopped` and remove that stream from the
active set; the other stream keeps producing chunks. The session ends
naturally when all streams have stopped (whether via user end_meeting,
capture exhaustion, or per-stream failures).

Per design.md (`Capture orchestration: two AudioCaptureService instances per
stream`, `Failure isolation: partial fault tolerance during in_progress`).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal, Protocol

from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.audio.capture import AudioCaptureService, AudioChunk, SilenceWarning

Stream = Literal["me", "counterparty"]

logger = logging.getLogger(__name__)


class _RepoLike(Protocol):
    async def insert_chunk(
        self,
        *,
        meeting_id: str,
        speaker: str,
        text_content: str,
        started_at: Any,
        ended_at: Any,
        asr_provider_used: str,
        confidence: float | None,
    ) -> Any: ...


SendFn = Callable[[dict], Awaitable[None]]


class _PersistFailed(Exception):
    """Internal sentinel to abort the whole session on a DB failure."""


class SessionService:
    """Drives per-stream capture → ASR → persist → emit pipelines for one meeting.

    Each stream has its own AudioCaptureService + ASRProvider. The class is
    stream-count-agnostic — pass `{"me": ...}` for slice-6 single-stream
    behaviour, or both `me` + `counterparty` for slice-7 dual-stream.
    """

    def __init__(
        self,
        *,
        meeting_id: str,
        captures: Mapping[Stream, AudioCaptureService] | None = None,
        providers: Mapping[Stream, ASRProvider] | None = None,
        session_repo: _RepoLike,
        send: SendFn,
        # Slice-6 backward-compat — single-stream constructor form.
        asr_provider: ASRProvider | None = None,
        speaker: Stream = "me",
    ) -> None:
        self._meeting_id = meeting_id
        self._repo = session_repo
        self._send = send
        # Resolve providers map. Backward-compat: caller may pass a single
        # `asr_provider=` kwarg + optional `speaker=` (slice-6 shape).
        if providers is not None:
            self._providers: dict[Stream, ASRProvider] = dict(providers)
        elif asr_provider is not None:
            self._providers = {speaker: asr_provider}
        else:
            raise TypeError(
                "SessionService requires either providers={...} (slice-7) "
                "or asr_provider=... (slice-6 single-stream backward compat)"
            )
        # Captures map is OPTIONAL because legacy callers pass the capture
        # directly into `service.run(capture)`. Slice-7 callers SHOULD pass
        # captures here; this lets `run()` be no-arg.
        self._captures: dict[Stream, AudioCaptureService] = (
            dict(captures) if captures is not None else {}
        )
        # Set of streams still producing events; consumed only via _stream_done().
        self._active_streams: set[Stream] = set(self._providers.keys())
        self._abort: asyncio.Event = asyncio.Event()
        # SQLAlchemy AsyncSession is NOT safe for concurrent use. With two
        # streams writing transcript_chunk rows in parallel, we MUST serialise
        # repo + send so one stream's commit doesn't collide with another's.
        # Granularity: per insert_chunk + matching transcript_chunk frame —
        # this preserves "DB write precedes client emission" per stream.
        self._write_lock: asyncio.Lock = asyncio.Lock()

    @property
    def active_streams(self) -> set[Stream]:
        return set(self._active_streams)

    async def run(
        self,
        capture_events: Any | None = None,
    ) -> None:
        """Drain per-stream events until exhausted, failed, or aborted.

        Two calling conventions:
          - Slice-7 (preferred): construct with `captures=` + `providers=` mappings,
            call `await service.run()` — spawns one consumer task per stream.
          - Slice-6 backward-compat: omit `captures=` at construction, pass
            a single capture into `service.run(capture)` — runs as before.
        """
        if capture_events is not None:
            # Single-stream legacy path. Drain the iterable directly.
            events = (
                capture_events.events() if hasattr(capture_events, "events") else capture_events
            )
            (only_stream,) = self._providers.keys()
            await self._consume_iter(only_stream, events)
            return

        if not self._captures:
            raise RuntimeError(
                "SessionService.run() called without an explicit capture and no "
                "captures were passed to __init__."
            )

        # Spawn one consumer task per stream. Tasks are independent — a
        # failure in one drops that stream from the active set but does NOT
        # cancel the other(s). Aborts (persist failure) signal all loops.
        tasks = [
            asyncio.create_task(self._consume_stream(stream), name=f"session-{stream}")
            for stream in self._captures
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _consume_stream(self, stream: Stream) -> None:
        capture = self._captures[stream]
        await self._consume_iter(stream, capture.events())

    async def _consume_iter(self, stream: Stream, events: Any) -> None:
        provider = self._providers[stream]
        try:
            async for ev in events:
                if self._abort.is_set():
                    return
                if isinstance(ev, AudioChunk):
                    try:
                        await self._handle_audio(ev, provider)
                    except _PersistFailed:
                        # Already emitted error frame in _handle_audio.
                        self._abort.set()
                        return
                elif isinstance(ev, SilenceWarning):
                    await self._send(
                        {
                            "type": "silence_warning",
                            "meeting_id": self._meeting_id,
                            "stream": ev.stream,
                            "since": ev.since.isoformat(),
                        }
                    )
        except Exception as exc:
            # Capture / ASR failure on this stream. Per design.md
            # `Failure isolation`: emit stream_stopped, leave other streams
            # alone. NOT an error frame.
            logger.exception("stream %s crashed: %s", stream, exc)
            with self._suppress_send_errors():
                await self._send(
                    {
                        "type": "stream_stopped",
                        "meeting_id": self._meeting_id,
                        "stream": stream,
                        "reason": str(exc) or type(exc).__name__,
                    }
                )
        finally:
            self._active_streams.discard(stream)

    def _suppress_send_errors(self):
        import contextlib

        return contextlib.suppress(Exception)

    async def _handle_audio(self, chunk: AudioChunk, provider: ASRProvider) -> None:
        try:
            result = await provider.transcribe_chunk(
                audio_bytes=chunk.audio_bytes,
                sample_rate_hz=chunk.sample_rate_hz,
                language_hint=None,
            )
        except Exception as exc:
            # ASR failure on a single chunk — log and skip (do NOT abort the
            # whole stream; transient errors shouldn't kill 30 minutes of audio).
            logger.warning("ASR transcription failed for stream %s: %s", chunk.stream, exc)
            return

        # VAD filter returns empty text for silent chunks. Skip emission.
        if not result.text.strip():
            return

        # Hold the write lock across BOTH the DB commit AND the WS frame so
        # the per-stream "DB write precedes client emission" invariant survives
        # under dual-stream concurrency. The lock is per-chunk; each stream's
        # ASR call still runs in parallel above.
        async with self._write_lock:
            try:
                await self._repo.insert_chunk(
                    meeting_id=self._meeting_id,
                    speaker=chunk.stream,
                    text_content=result.text,
                    started_at=result.started_at,
                    ended_at=result.ended_at,
                    asr_provider_used=result.asr_provider_used,
                    confidence=result.confidence,
                )
            except Exception as exc:
                logger.exception("Failed to persist transcript chunk: %s", exc)
                with self._suppress_send_errors():
                    await self._send(
                        {
                            "type": "error",
                            "error_code": "session.persist_failed",
                            "message": "Failed to persist transcript chunk; closing session.",
                        }
                    )
                raise _PersistFailed() from exc

            await self._send(
                {
                    "type": "transcript_chunk",
                    "meeting_id": self._meeting_id,
                    "speaker": chunk.stream,
                    "text": result.text,
                    "started_at": result.started_at.isoformat(),
                    "ended_at": result.ended_at.isoformat(),
                    "asr_provider_used": result.asr_provider_used,
                    "confidence": result.confidence,
                }
            )


__all__ = ["SessionService", "Stream"]
