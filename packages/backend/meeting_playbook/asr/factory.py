"""ASR provider factory — selects an ASRProvider implementation per meeting.

After `asr-runtime-extraction` (ADR-0027) there is only ONE concrete
provider: `RemoteAsrRuntimeClient`, which proxies to the standalone
asr-runtime micro-service. Whisper has been retired entirely. Historical
meetings persisted with `asr_provider = "whisper"` (or any other unknown
value) are coerced to `"qwen3"` with a structured log warning so the
session keeps working.

Design (per ADR-0027):
  * Cache key is `(provider_name, stream)`. Two meetings using the same
    engine reuse the same provider singletons → no extra connection pool
    per meeting.
  * Different streams under the same engine get distinct client instances
    so per-stream warmups can run in parallel via asyncio.gather.
  * `ASR_RUNTIME_URL` MUST be set; the factory raises
    `AsrRuntimeUnavailableError` if it isn't.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from functools import cache
from typing import Literal

from meeting_playbook.asr.base import ASRProvider, TranscriptChunk
from meeting_playbook.asr.remote_runtime_client import (
    AsrRuntimeUnavailableError,
    RemoteAsrRuntimeClient,
)
from meeting_playbook.asr.transliteration import to_traditional_chinese

logger = logging.getLogger(__name__)

Stream = Literal["me", "counterparty"]
_STREAMS: tuple[Stream, Stream] = ("me", "counterparty")

# Canonical provider name. Historical values (whisper, vibevoice, ...) are
# coerced here.
_CANONICAL_PROVIDER = "qwen3"


class _TraditionalChineseProvider:
    """ASRProvider decorator: post-process every transcript through OpenCC
    `s2twp` so persisted text is Traditional Chinese (Taiwan variant)."""

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


def _coerce_provider_name(provider_name: str) -> str:
    """Coerce legacy provider names (whisper, vibevoice, ...) to the
    canonical `qwen3` value. Emits a structured warning so operators can
    spot stale meeting rows."""
    if provider_name == _CANONICAL_PROVIDER:
        return provider_name
    logger.warning(
        "asr_provider_coerced",
        extra={"from_value": provider_name, "to_value": _CANONICAL_PROVIDER},
    )
    return _CANONICAL_PROVIDER


@cache
def _provider_singleton(provider_name: str, stream: Stream) -> ASRProvider:
    """Build (or return the cached) provider for one (engine, stream) pair.

    `provider_name` is part of the cache key so we can still distinguish
    rows when (rare) operator override env vars introduce a non-default
    label. In practice today every entry maps to `qwen3` via
    `_coerce_provider_name`.
    """
    del provider_name  # only part of cache key
    return _TraditionalChineseProvider(RemoteAsrRuntimeClient(stream=stream))


def get_asr_providers_for_meeting(
    provider_name: str,
) -> tuple[ASRProvider, ASRProvider]:
    """Resolve the (me, counterparty) provider pair for a meeting.

    Raises `AsrRuntimeUnavailableError` if `ASR_RUNTIME_URL` is not set —
    no graceful fallback exists since the in-process Whisper / MLX
    providers were removed by ADR-0027.
    """
    canonical = _coerce_provider_name(provider_name)
    # Construct RemoteAsrRuntimeClient eagerly so the env-var check
    # surfaces at WS connect time rather than at first chunk.
    # Use a per-stream singleton cache so two meetings sharing the same
    # engine reuse the same connection pool.
    return (
        _provider_singleton(canonical, _STREAMS[0]),
        _provider_singleton(canonical, _STREAMS[1]),
    )


def clear_provider_cache() -> None:
    """Test helper: drop all cached providers so per-test instance assertions
    are deterministic."""
    _provider_singleton.cache_clear()


__all__ = [
    "AsrRuntimeUnavailableError",
    "Stream",
    "_coerce_provider_name",
    "clear_provider_cache",
    "get_asr_providers_for_meeting",
]
