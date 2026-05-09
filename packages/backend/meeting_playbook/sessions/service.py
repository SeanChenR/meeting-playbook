"""SessionService — pure orchestration loop for an active meeting session.

Per slice-06 design ("WebSocket endpoint design" steps 6–10): this is the
serial pipeline that pulls events from `AudioCaptureService.events()`, runs
each `AudioChunk` through `ASRProvider`, persists via `SessionRepository`
BEFORE forwarding the result to the WebSocket client, and forwards
`SilenceWarning` events 1:1.

Decoupled from the WebSocket layer (router calls `service.run(capture)`
with an injected `send(frame)` async callable) so the orchestration is
testable without spinning up FastAPI / Starlette WebSocket plumbing.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.audio.capture import AudioChunk, SilenceWarning

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


class SessionService:
    """Drives the capture → ASR → persist → emit pipeline for one session."""

    def __init__(
        self,
        *,
        meeting_id: str,
        asr_provider: ASRProvider,
        session_repo: _RepoLike,
        send: SendFn,
        speaker: str = "me",
    ) -> None:
        self._meeting_id = meeting_id
        self._asr = asr_provider
        self._repo = session_repo
        self._send = send
        self._speaker = speaker

    async def run(self, capture_events: AsyncIterator[AudioChunk | SilenceWarning] | Any) -> None:
        """Drain `capture_events` until exhausted or persist failure.

        `capture_events` is duck-typed: anything with an `events()` async
        iterator OR an `__aiter__` works. Tests pass a scripted iterable;
        production passes an `AudioCaptureService` instance.
        """
        events = capture_events.events() if hasattr(capture_events, "events") else capture_events
        async for ev in events:
            if isinstance(ev, AudioChunk):
                if not await self._handle_audio(ev):
                    return
            elif isinstance(ev, SilenceWarning):
                await self._send(
                    {
                        "type": "silence_warning",
                        "meeting_id": self._meeting_id,
                        "since": ev.since.isoformat(),
                    }
                )

    async def _handle_audio(self, chunk: AudioChunk) -> bool:
        """Returns True to keep going, False if a fatal error was emitted."""
        try:
            result = await self._asr.transcribe_chunk(
                audio_bytes=chunk.audio_bytes,
                sample_rate_hz=chunk.sample_rate_hz,
                language_hint=None,
            )
        except Exception as exc:
            logger.exception("ASR transcription failed: %s", exc)
            await self._send(
                {
                    "type": "error",
                    "error_code": "session.transcribe_failed",
                    "message": f"Transcription failed: {exc}",
                }
            )
            return False
        # Whisper VAD filter returns empty text for chunks with no detected
        # speech. Skip those — neither persist nor emit — so the UI shows
        # only meaningful transcript rows.
        if not result.text.strip():
            return True
        try:
            await self._repo.insert_chunk(
                meeting_id=self._meeting_id,
                speaker=self._speaker,
                text_content=result.text,
                started_at=result.started_at,
                ended_at=result.ended_at,
                asr_provider_used=result.asr_provider_used,
                confidence=result.confidence,
            )
        except Exception:
            await self._send(
                {
                    "type": "error",
                    "error_code": "session.persist_failed",
                    "message": "Failed to persist transcript chunk; closing session.",
                }
            )
            return False

        await self._send(
            {
                "type": "transcript_chunk",
                "meeting_id": self._meeting_id,
                "speaker": self._speaker,
                "text": result.text,
                "started_at": result.started_at.isoformat(),
                "ended_at": result.ended_at.isoformat(),
                "asr_provider_used": result.asr_provider_used,
                "confidence": result.confidence,
            }
        )
        return True


__all__ = ["SessionService"]
