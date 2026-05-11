"""ASR provider factory — selects an ASRProvider implementation per meeting.

Slice-11 replaces the slice-7 `_whisper_singleton_*` lru_cache pattern in
`sessions/dependencies.py`. The router calls `get_asr_providers_for_meeting`
at WS connect time with `meeting.asr_provider` and receives a tuple
`(me_provider, counterparty_provider)` of independent instances so per-stream
state (warmup status, sample-rate cache) does not leak across streams.

Design (per `openspec/changes/slice-11-asr-and-retention/design.md` Decision 1):
  * Cache key is `(provider_name, stream)`. Two meetings using the same engine
    reuse the same provider singletons → no double model load.
  * Different streams under the same engine get distinct instances so
    asyncio.gather warmups overlap (they target different model objects).
  * Unknown provider names fall back to Whisper with a WARNING log; we
    never raise here — the keystone of ADR-0005 is that the session orchestrator
    does NOT need to special-case engines.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from functools import cache
from typing import Literal

from meeting_playbook.asr.base import ASRProvider, TranscriptChunk
from meeting_playbook.asr.qwen3_provider import Qwen3ASRProvider
from meeting_playbook.asr.transliteration import to_traditional_chinese
from meeting_playbook.asr.whisper_provider import WhisperProvider

logger = logging.getLogger(__name__)

Stream = Literal["me", "counterparty"]
_STREAMS: tuple[Stream, Stream] = ("me", "counterparty")


class _TraditionalChineseProvider:
    """ASRProvider decorator: post-process every transcript through OpenCC
    `s2twp` so the persisted text is Traditional Chinese (Taiwan variant).

    Both Qwen3 and Whisper trained predominantly on simplified-Chinese
    corpora, so wrapping at the factory layer (rather than inside each
    provider) keeps individual providers ignorant of locale concerns.

    Forwards `name` + `warmup` unchanged so the keystone Protocol is
    structurally preserved.
    """

    def __init__(self, inner: ASRProvider) -> None:
        self._inner = inner

    @property
    def name(self) -> str:
        return self._inner.name

    async def warmup(self) -> None:
        await self._inner.warmup()

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        sample_rate_hz: int,
        language_hint: str | None = None,
    ) -> TranscriptChunk:
        chunk = await self._inner.transcribe_chunk(
            audio_bytes=audio_bytes,
            sample_rate_hz=sample_rate_hz,
            language_hint=language_hint,
        )
        return replace(chunk, text=to_traditional_chinese(chunk.text))


@cache
def _provider_singleton(provider_name: str, stream: Stream) -> ASRProvider:
    """Build (or return the cached) provider for one (engine, stream) pair.

    `stream` is part of the cache key but is not passed to providers — the
    keystone is that ASRProvider implementations are stream-agnostic. The
    key exists purely so two streams of the same engine get distinct
    instances.

    Every provider is wrapped in `_TraditionalChineseProvider` so the
    transcript_chunk text persisted to the DB is always Traditional
    Chinese (Taiwan variant). Wrapping at the factory layer means
    individual provider implementations stay locale-agnostic.
    """
    del stream  # part of cache key only
    if provider_name == "qwen3":
        return _TraditionalChineseProvider(Qwen3ASRProvider())
    if provider_name == "whisper":
        return _TraditionalChineseProvider(WhisperProvider())
    logger.warning("unknown asr_provider %r, falling back to whisper", provider_name)
    return _TraditionalChineseProvider(WhisperProvider())


def get_asr_providers_for_meeting(provider_name: str) -> tuple[ASRProvider, ASRProvider]:
    """Resolve the (me, counterparty) provider pair for a meeting at WS connect time.

    Both providers are independent instances so warmup + inference run in
    parallel on distinct model objects (matching the slice-7 dual-stream
    contract). Repeated calls with the same `provider_name` reuse the same
    cached instances.
    """
    return (
        _provider_singleton(provider_name, _STREAMS[0]),
        _provider_singleton(provider_name, _STREAMS[1]),
    )


def clear_provider_cache() -> None:
    """Test helper: drop all cached providers so per-test instance assertions
    are deterministic. Production code SHALL NOT call this — releasing the
    Whisper / Qwen3 model objects mid-run defeats the whole point of caching."""
    _provider_singleton.cache_clear()


__all__ = [
    "Stream",
    "clear_provider_cache",
    "get_asr_providers_for_meeting",
]
