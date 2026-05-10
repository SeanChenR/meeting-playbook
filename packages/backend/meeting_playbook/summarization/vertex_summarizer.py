"""VertexProSummarizer — Vertex Gemini 2.5 Pro impl of MeetingSummarizer.

Per slice-10 design Decision 5 + 8: fetches transcript / playbook / chat
history inside its own AsyncSession (separate from request-scoped
sessions); the LLM call runs OUTSIDE the session so no DB connection is
held during the 30-60s round-trip. Validates the 4 required headings
before returning; mismatch raises SummaryFormatError so the runtime
treats it as a generation failure (no upsert).

The implementation reads `Settings.vertex_pro_model_id` and applies a
90-second outer `asyncio.timeout` so a hung Vertex call raises
`asyncio.TimeoutError` rather than blocking the background task forever.

Test seam: `client_factory` is a callable that builds the underlying SDK
client. Production wires `lambda: google.genai.Client(vertexai=True, ...)`;
tests pass a `lambda: MagicMock(...)` so no GCP auth is needed at test time.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from meeting_playbook.chat.repository import ChatMessageRepository
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.playbooks.repository import PlaybookRepository
from meeting_playbook.sessions.repository import SessionRepository
from meeting_playbook.summarization.base import Locale, SummaryFormatError
from meeting_playbook.summarization.prompts import (
    REQUIRED_HEADINGS,
    build_system_instruction,
    build_user_message,
)

logger = logging.getLogger(__name__)

# 90-second outer cap on the whole Vertex call — see ADR-0006 + design.md
# Decision 2 (auto-trigger background task tolerance for 30-60s LLM round-trip
# with 30s safety margin).
_STREAM_TIMEOUT_S: float = 90.0
_TEMPERATURE: float = 0.3
_MAX_OUTPUT_TOKENS: int = 4096


def _validate_4_headings(markdown: str, locale: Locale) -> None:
    """Verify the 4 required headings appear in document order.

    Match is trim-insensitive (`{heading}` may have trailing whitespace
    on its line) and case-insensitive on the heading body. Raises
    `SummaryFormatError` on first violation with a message identifying
    the missing / out-of-order heading so the log is actionable.
    """
    headings = REQUIRED_HEADINGS[locale]
    lower = markdown.lower()
    last_idx = -1
    for h in headings:
        idx = lower.find(h.lower())
        if idx == -1:
            raise SummaryFormatError(
                f"Missing required heading {h!r} in summary markdown (locale={locale})"
            )
        if idx <= last_idx:
            raise SummaryFormatError(
                f"Heading {h!r} appears out of order in summary markdown (locale={locale})"
            )
        last_idx = idx


class VertexProSummarizer:
    """Concrete MeetingSummarizer wired to Vertex Gemini 2.5 Pro via google-genai."""

    def __init__(
        self,
        client_factory: Callable[[], Any],
        model_id: str,
        session_factory: async_sessionmaker[AsyncSession],
        locale: Locale = "zh-TW",
    ) -> None:
        self._client_factory = client_factory
        self._model_id = model_id
        self._session_factory = session_factory
        self._locale: Locale = locale
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    async def summarize(self, meeting_id: str) -> str:
        """Fetch context, call Vertex 2.5 Pro, validate headings, return markdown."""
        # Phase 1: fetch context inside a short-lived session.
        async with self._session_factory() as session:
            # MeetingRepository's read accessors require user_id — but here
            # the summarizer is invoked from a trusted background path
            # (auto-trigger after meeting_ended OR owner-validated POST),
            # so we read by id directly via a SELECT.
            meeting_repo = MeetingRepository(session)
            meeting = await meeting_repo.get_by_id(meeting_id)
            if meeting is None:
                raise SummaryFormatError(f"Meeting {meeting_id!r} not found at summarize() time")
            chunks = await SessionRepository(session).list_chunks_for_meeting(meeting_id)
            playbook = await PlaybookRepository(session).get_or_create_for_meeting(meeting_id)
            chat_history = await ChatMessageRepository(session).list_for_meeting(meeting_id)

        logger.info(
            "summary meeting=%s chunks=%d chat_history=%d locale=%s",
            meeting_id,
            len(chunks),
            len(chat_history),
            self._locale,
        )

        # Phase 2: build prompt + call Vertex (no DB connection held).
        system_instruction = build_system_instruction(self._locale)
        user_message = build_user_message(
            meeting=meeting,
            playbook=playbook,
            recent_chunks=chunks,
            chat_history=chat_history,
            locale=self._locale,
        )

        client = self._get_client()
        config = self._build_config(system_instruction)

        async with asyncio.timeout(_STREAM_TIMEOUT_S):
            response = await client.aio.models.generate_content(
                model=self._model_id,
                contents=user_message,
                config=config,
            )

        # google-genai returns an object with `.text`; some SDK versions
        # return `.candidates[0].content.parts[0].text`. Try both.
        markdown = getattr(response, "text", None)
        if markdown is None:
            try:
                markdown = response.candidates[0].content.parts[0].text  # type: ignore[union-attr]
            except (AttributeError, IndexError, TypeError) as exc:
                raise SummaryFormatError(
                    f"Vertex response missing .text and .candidates[0].content.parts[0].text: {exc}"
                ) from exc
        if not isinstance(markdown, str) or not markdown.strip():
            raise SummaryFormatError("Vertex returned empty markdown")

        # Phase 3: validate 4 headings in order. Mismatch → SummaryFormatError.
        _validate_4_headings(markdown, self._locale)

        return markdown

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


__all__ = ["VertexProSummarizer"]
