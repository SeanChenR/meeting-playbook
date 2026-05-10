"""MeetingSummarizer Protocol + shared types — slice-10 keystone.

Concrete impls (`VertexProSummarizer` today) wrap the LLM call. The
runtime depends ONLY on this Protocol so the underlying SDK can be
swapped without touching the spawn / repository layers.

`SummaryFormatError` is raised when the model returns markdown that
doesn't contain the 4 required headings in document order — the
runtime treats it the same as a Vertex API failure (no upsert).
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

Locale = Literal["zh-TW", "en"]


class SummaryFormatError(Exception):
    """Raised when the LLM output is missing or reorders the 4 required headings.

    Slice-10 Decision 5: the prompt's hard contract is "4 fixed sections in
    fixed order". Validation runs after the LLM call; mismatch here means
    the LLM ignored the instruction and we don't trust the row enough to
    persist it.
    """


@runtime_checkable
class MeetingSummarizer(Protocol):
    """Async LLM wrapper that returns a 4-section markdown summary."""

    async def summarize(self, meeting_id: str) -> str:
        """Generate a markdown summary for the meeting.

        Returns the full markdown string. Raises:
        - asyncio.TimeoutError on stream timeout
        - SummaryFormatError when 4-heading validation fails
        - propagates provider exceptions (runtime maps to log + skip-upsert)
        """
        ...


__all__ = ["Locale", "MeetingSummarizer", "SummaryFormatError"]
