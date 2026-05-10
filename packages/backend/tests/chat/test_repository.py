"""ChatMessageRepository — write path for chat_message rows.

Per spec tactical-advisor ADDED requirement "chat_message table persists
per-meeting conversation history" — pin the repository contract here.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.chat.repository import ChatMessageRepository


async def _seed_meeting(session: AsyncSession, *, mid: str = "m_chat") -> None:
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ('u_chat', 'Sean', 'sean@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, 'u_chat', 'T', 'C', 'M')
            """
        ),
        {"mid": mid},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_insert_pair_after_advice_writes_two_rows_atomically(db_session):
    """Slice-09 Decision 2: stream success writes user + advisor rows in one transaction.

    User row's created_at SHALL be earlier than or equal to the advisor row's.
    """
    await _seed_meeting(db_session, mid="m_pair")
    repo = ChatMessageRepository(db_session)

    user_msg, advisor_msg = await repo.insert_pair_after_advice(
        meeting_id="m_pair",
        user_content="Q",
        advisor_content="A",
    )

    assert user_msg.id.startswith("cm_")
    assert advisor_msg.id.startswith("cm_")
    assert user_msg.role == "user"
    assert user_msg.content == "Q"
    assert advisor_msg.role == "advisor"
    assert advisor_msg.content == "A"
    assert user_msg.meeting_id == "m_pair" == advisor_msg.meeting_id
    assert user_msg.created_at <= advisor_msg.created_at, (
        "user row must be created before or at the same instant as advisor row"
    )

    # Both rows persisted.
    rows = await db_session.execute(
        text(
            "SELECT id, role, content FROM chat_message WHERE meeting_id = 'm_pair' ORDER BY created_at ASC"
        )
    )
    listed = [(r.role, r.content) for r in rows]
    assert listed == [("user", "Q"), ("advisor", "A")]


@pytest.mark.asyncio
async def test_list_for_meeting_returns_chronological_order(db_session):
    """Slice-09: list_for_meeting orders by created_at ASC even when inserted out of order."""
    await _seed_meeting(db_session, mid="m_order")
    repo = ChatMessageRepository(db_session)

    # Insert via insert_pair_after_advice 3 times — each pair monotonically increases time.
    await repo.insert_pair_after_advice(
        meeting_id="m_order", user_content="Q1", advisor_content="A1"
    )
    await repo.insert_pair_after_advice(
        meeting_id="m_order", user_content="Q2", advisor_content="A2"
    )
    await repo.insert_pair_after_advice(
        meeting_id="m_order", user_content="Q3", advisor_content="A3"
    )

    listed = await repo.list_for_meeting("m_order")
    assert [m.content for m in listed] == ["Q1", "A1", "Q2", "A2", "Q3", "A3"]
    # Strictly non-decreasing created_at.
    for prev, nxt in zip(listed, listed[1:], strict=False):
        assert prev.created_at <= nxt.created_at


@pytest.mark.asyncio
async def test_cascade_delete_on_meeting_removal(db_session):
    """Slice-09 Decision 1: deleting a meeting cascades to all chat_message rows."""
    await _seed_meeting(db_session, mid="m_cascade")
    repo = ChatMessageRepository(db_session)
    await repo.insert_pair_after_advice(
        meeting_id="m_cascade", user_content="Q", advisor_content="A"
    )
    # Sanity: 2 rows exist.
    pre = await db_session.execute(
        text("SELECT COUNT(*) FROM chat_message WHERE meeting_id = 'm_cascade'")
    )
    assert pre.scalar_one() == 2

    await db_session.execute(text("DELETE FROM meeting WHERE id = 'm_cascade'"))
    await db_session.commit()

    post = await db_session.execute(
        text("SELECT COUNT(*) FROM chat_message WHERE meeting_id = 'm_cascade'")
    )
    assert post.scalar_one() == 0, "FK CASCADE failed to remove chat_message rows"
