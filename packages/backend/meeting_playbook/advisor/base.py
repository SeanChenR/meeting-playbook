"""TacticalAdvisor Protocol — the keystone of slice-08 (in-meeting LLM).

Concrete impls (`VertexFlashAdvisor` today, conceivably others later) wrap an
LLM streaming client. The session router depends ONLY on this Protocol so
the underlying SDK can be swapped without touching the WS handler.

The Protocol is intentionally a pure function: caller fetches `recent_chunks`
and `playbook` (via its own AsyncSession) and hands them in. The advisor
holds zero database state — exactly the shape needed for the slice-09
chatbox follow-up which adds `user_question` to the same call.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal, Protocol, runtime_checkable

from meeting_playbook.chat.models import ChatMessage
from meeting_playbook.playbooks.models import Playbook
from meeting_playbook.sessions.models import TranscriptChunk

Locale = Literal["zh-TW", "en"]


@runtime_checkable
class TacticalAdvisor(Protocol):
    """Async streaming wrapper over the in-meeting LLM (Vertex Flash today).

    Per ADR-0017 (button + chatbox trigger) and ADR-0018 (last-60s + full
    playbook context window). Caller assembles the context; advisor calls
    the model and yields text segments as they arrive.
    """

    async def advise(
        self,
        meeting_id: str,
        recent_chunks: list[TranscriptChunk],
        playbook: Playbook | None,
        me_display_name: str,
        counterparty_display_name: str,
        user_question: str | None,
        locale: Locale,
        chat_history: list[ChatMessage],
    ) -> AsyncIterator[str]:
        """Yield text segments per upstream SDK chunk.

        - `recent_chunks` — last 60s of transcript_chunk rows, ordered
          ascending by `started_at`. May be empty when the meeting just
          started or has been silent.
        - `playbook` — meeting's playbook row, may be None if no row exists.
        - `user_question` — None for slice-08 (button-only); slice-09 chatbox
          passes the user's question.
        - `locale` — affects the output language; comes from the WS frame.
        - `chat_history` — slice-09: prior chat_message rows for this meeting,
          ordered ascending by `created_at`. Empty list = first turn.

        Implementations SHALL:
        - apply a 15-second outer `asyncio.timeout` (raises `asyncio.TimeoutError`
          on stalled streams)
        - skip empty `chunk.text` segments
        - propagate provider exceptions (router maps to `advisor_failed` frames)
        """
        ...


__all__ = ["Locale", "TacticalAdvisor"]
