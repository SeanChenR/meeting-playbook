"""VertexFlashAdvisor — Vertex Gemini Flash streaming impl of TacticalAdvisor.

Per slice-08 design `Streaming protocol: per-SDK-chunk WS frame, transparent
forwarding`. Wraps `client.aio.models.generate_content_stream(...)` with a
15-second outer `asyncio.timeout`; yields each chunk's `.text` verbatim
(skipping empty / None segments).

Test seam: `client_factory` is a callable that builds the underlying SDK
client. Production wires `lambda: google.genai.Client(vertexai=True, ...)`;
tests pass a `lambda: MagicMock(...)` so no GCP auth is needed at test time.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

from meeting_playbook.advisor.base import Locale
from meeting_playbook.advisor.prompts import build_system_instruction, build_user_message
from meeting_playbook.playbooks.models import Playbook
from meeting_playbook.sessions.models import TranscriptChunk

logger = logging.getLogger(__name__)

# 15-second outer cap on the whole stream — see ADR-0017 latency target (3-5s)
# + design.md `Failure modes` (advisor.timeout maps from this).
_STREAM_TIMEOUT_S: float = 15.0
_TEMPERATURE: float = 0.4
_MAX_OUTPUT_TOKENS: int = 400


class VertexFlashAdvisor:
    """Concrete TacticalAdvisor wired to Vertex Gemini Flash via google-genai."""

    def __init__(
        self,
        client_factory: Callable[[], Any],
        model_id: str,
    ) -> None:
        self._client_factory = client_factory
        self._model_id = model_id
        self._client: Any | None = None  # lazy

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    async def advise(
        self,
        meeting_id: str,
        recent_chunks: Sequence[TranscriptChunk],
        playbook: Playbook | None,
        me_display_name: str,
        counterparty_display_name: str,
        user_question: str | None,
        locale: Locale,
    ) -> AsyncIterator[str]:
        system_instruction = build_system_instruction(locale)
        user_message = build_user_message(
            playbook=playbook,
            recent_chunks=recent_chunks,
            me_display_name=me_display_name,
            counterparty_display_name=counterparty_display_name,
            user_question=user_question,
            locale=locale,
        )

        client = self._get_client()
        config = self._build_config(system_instruction)

        logger.info(
            "TacticalAdvisor.advise meeting=%s locale=%s recent_chunks=%d user_question=%s",
            meeting_id,
            locale,
            len(recent_chunks),
            "yes" if user_question else "no",
        )

        async with asyncio.timeout(_STREAM_TIMEOUT_S):
            stream = client.aio.models.generate_content_stream(
                model=self._model_id,
                contents=user_message,
                config=config,
            )
            # The SDK returns either an async iterator directly OR an awaitable
            # that resolves to one. Handle both shapes.
            if hasattr(stream, "__aiter__"):
                async_stream = stream
            else:
                async_stream = await stream
            async for chunk in async_stream:
                text = getattr(chunk, "text", None)
                if not text:
                    continue
                yield text

    def _build_config(self, system_instruction: str) -> Any:
        """Build the SDK GenerateContentConfig; falls back to a plain dict when
        the SDK is not importable (test env using a mock client)."""
        try:
            from google.genai import types as genai_types  # type: ignore[import-not-found]

            return genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=_TEMPERATURE,
                max_output_tokens=_MAX_OUTPUT_TOKENS,
            )
        except (ImportError, AttributeError):
            return {
                "system_instruction": system_instruction,
                "temperature": _TEMPERATURE,
                "max_output_tokens": _MAX_OUTPUT_TOKENS,
            }


__all__ = ["VertexFlashAdvisor"]
