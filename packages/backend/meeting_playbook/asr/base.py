"""ASRProvider Protocol + TranscriptChunk dataclass — the keystone of ADR-0005.

Concrete providers (Whisper, VibeVoice, ...) implement this Protocol. The
session orchestrator depends ONLY on this contract — adding a new engine
is a drop-in via dependency injection without touching the router or the
audio capture service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class TranscriptChunk:
    text: str
    started_at: datetime
    ended_at: datetime
    asr_provider_used: str
    confidence: float | None


@runtime_checkable
class ASRProvider(Protocol):
    """Behavioral contract for ASR engines (per ADR-0005).

    Implementations MUST:
    - Expose a stable `name` property used as the `asr_provider_used` value
      written into transcript_chunk rows
    - Run `transcribe_chunk` asynchronously; sync libraries should wrap calls
      in `asyncio.to_thread` so the WebSocket event loop stays unblocked
    - Honor `sample_rate_hz` instead of assuming a fixed rate
    - Treat `language_hint` as advisory; default behavior when None is provider-specific
    """

    @property
    def name(self) -> str: ...

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        sample_rate_hz: int,
        language_hint: str | None = None,
    ) -> TranscriptChunk: ...

    async def warmup(self) -> None:
        """Optional: pre-load any heavy resources so the first transcribe_chunk
        does not pay the cold-start cost. Idempotent. Implementations that
        have no expensive setup MAY make this a no-op.

        Slice-7 SessionService awaits warmup() on every per-stream provider in
        parallel via asyncio.gather before the first audio chunk arrives.
        """
        ...


__all__ = ["ASRProvider", "TranscriptChunk"]
