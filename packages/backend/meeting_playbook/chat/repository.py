"""ChatMessageRepository — write path for chat_message rows.

Per design.md (slice-09-advisor-chatbox) Decision 2:
- Stream success writes user + advisor rows in ONE transaction (single
  commit). The user row's `created_at` is set strictly earlier than the
  advisor row's so chronological ordering is deterministic even when
  `insert_pair_after_advice` is the only writer in the same wall-clock ms.
- Stream failure / cancel does NOT call this repository. There is no
  update / delete API — chat history is append-only.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.chat.models import ChatMessage


class ChatMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_meeting(self, meeting_id: str) -> list[ChatMessage]:
        """All chat_message rows for a meeting, ordered by `created_at` ASC."""
        result = await self._session.execute(
            select(ChatMessage)
            .where(ChatMessage.meeting_id == meeting_id)
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.scalars().all())

    async def insert_pair_after_advice(
        self,
        *,
        meeting_id: str,
        user_content: str,
        advisor_content: str,
    ) -> tuple[ChatMessage, ChatMessage]:
        """Atomically insert a (user, advisor) pair after a successful advice stream.

        The user row's `created_at` is offset 1 microsecond earlier than the
        advisor row's so `ORDER BY created_at ASC` guarantees the user
        message precedes its assistant reply, even when both INSERTs land
        in the same wall-clock millisecond.
        """
        user_now = datetime.now(UTC)
        advisor_now = user_now + timedelta(microseconds=1)
        user_msg = ChatMessage(
            id=f"cm_{secrets.token_urlsafe(16)}",
            meeting_id=meeting_id,
            role="user",
            content=user_content,
            created_at=user_now,
        )
        advisor_msg = ChatMessage(
            id=f"cm_{secrets.token_urlsafe(16)}",
            meeting_id=meeting_id,
            role="advisor",
            content=advisor_content,
            created_at=advisor_now,
        )
        self._session.add_all([user_msg, advisor_msg])
        await self._session.commit()
        return user_msg, advisor_msg


__all__ = ["ChatMessageRepository"]
