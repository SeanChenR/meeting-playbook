"""MeetingLinkRepository tests — slice-21 tasks 2.1, 2.2, 2.3.

Per slice-21 design "`MeetingLinkRepository` interface (deep module)":
- `create(A, B)` writes one row; second create in either direction raises
  `MeetingLinkDuplicate`; self-reference raises `MeetingLinkSelfReference`.
- `list_for_meeting(M)` returns every link touching M, projected as the
  "other-meeting perspective" view (caller never sees from/to direction).
- `get(link_id)` returns the row or None.
- `delete(link_id)` returns True for one-row-deleted, False otherwise.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meeting_links.repository import (
    MeetingLinkDuplicate,
    MeetingLinkRepository,
    MeetingLinkSelfReference,
)
from meeting_playbook.meetings.repository import MeetingRepository


async def _seed_user(session: AsyncSession, *, user_id: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES (:id, :name, :email, true)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": user_id, "name": user_id, "email": f"{user_id}@example.com"},
    )
    await session.commit()


async def _seed_two_meetings(session: AsyncSession, *, user_id: str) -> tuple[str, str]:
    """Return `(meeting_a_id, meeting_b_id)` both owned by `user_id`."""
    await _seed_user(session, user_id=user_id)
    repo = MeetingRepository(session)
    a = await repo.create(
        user_id=user_id,
        title="Meeting A",
        counterparty_display_name="C1",
        me_display_name="Me",
    )
    b = await repo.create(
        user_id=user_id,
        title="Meeting B",
        counterparty_display_name="C2",
        me_display_name="Me",
    )
    return a.id, b.id


# ─── Task 2.1: create ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_self_reference_raises(db_session: AsyncSession) -> None:
    """`create(A, A)` MUST raise `MeetingLinkSelfReference`."""
    a, _ = await _seed_two_meetings(db_session, user_id="u_self")
    repo = MeetingLinkRepository(db_session)

    with pytest.raises(MeetingLinkSelfReference):
        await repo.create(from_meeting_id=a, to_meeting_id=a)


@pytest.mark.asyncio
async def test_create_same_direction_duplicate_raises(db_session: AsyncSession) -> None:
    """A second `create(A, B)` in the same direction MUST raise `MeetingLinkDuplicate`."""
    a, b = await _seed_two_meetings(db_session, user_id="u_dup_same")
    repo = MeetingLinkRepository(db_session)

    await repo.create(from_meeting_id=a, to_meeting_id=b)
    with pytest.raises(MeetingLinkDuplicate):
        await repo.create(from_meeting_id=a, to_meeting_id=b)


@pytest.mark.asyncio
async def test_create_reverse_direction_duplicate_raises(db_session: AsyncSession) -> None:
    """A second `create(B, A)` MUST raise `MeetingLinkDuplicate` (order-independent)."""
    a, b = await _seed_two_meetings(db_session, user_id="u_dup_rev")
    repo = MeetingLinkRepository(db_session)

    await repo.create(from_meeting_id=a, to_meeting_id=b)
    with pytest.raises(MeetingLinkDuplicate):
        await repo.create(from_meeting_id=b, to_meeting_id=a)


# ─── Task 2.2: list_for_meeting ────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_for_meeting_both_sides_see_the_row(db_session: AsyncSession) -> None:
    """Writing `(A, B)` MUST be visible from both `list_for_meeting(A)` and `(B)`,
    with each view's `other_meeting_id` correctly swapped."""
    a, b = await _seed_two_meetings(db_session, user_id="u_list_both")
    repo = MeetingLinkRepository(db_session)

    await repo.create(from_meeting_id=a, to_meeting_id=b)

    from_a = await repo.list_for_meeting(a)
    from_b = await repo.list_for_meeting(b)

    assert len(from_a) == 1
    assert len(from_b) == 1
    assert from_a[0].other_meeting_id == b
    assert from_b[0].other_meeting_id == a
    # Both sides share the same link_id + created_at (it is the SAME row).
    assert from_a[0].link_id == from_b[0].link_id
    assert from_a[0].created_at == from_b[0].created_at


@pytest.mark.asyncio
async def test_list_for_meeting_sorts_created_at_desc(db_session: AsyncSession) -> None:
    """Multiple links MUST come back sorted by `created_at` DESC."""
    await _seed_user(db_session, user_id="u_list_order")
    mrepo = MeetingRepository(db_session)
    a = await mrepo.create(
        user_id="u_list_order",
        title="A",
        counterparty_display_name="C",
        me_display_name="Me",
    )
    b = await mrepo.create(
        user_id="u_list_order",
        title="B",
        counterparty_display_name="C",
        me_display_name="Me",
    )
    c = await mrepo.create(
        user_id="u_list_order",
        title="C",
        counterparty_display_name="C",
        me_display_name="Me",
    )

    repo = MeetingLinkRepository(db_session)
    first = await repo.create(from_meeting_id=a.id, to_meeting_id=b.id)
    # Force a measurable created_at delta — `now()` resolution is microseconds
    # but two inserts inside the same transaction can collide on the same
    # `now()` snapshot in PostgreSQL. A small sleep makes the ordering
    # deterministic in test runs without affecting production behaviour.
    await asyncio.sleep(0.01)
    second = await repo.create(from_meeting_id=a.id, to_meeting_id=c.id)

    rows = await repo.list_for_meeting(a.id)
    assert len(rows) == 2
    assert rows[0].link_id == second.id
    assert rows[1].link_id == first.id


# ─── Task 2.3: get + delete ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_returns_true_first_time_false_second(db_session: AsyncSession) -> None:
    """`delete` MUST return True on first call, False on second (idempotent)."""
    a, b = await _seed_two_meetings(db_session, user_id="u_del")
    repo = MeetingLinkRepository(db_session)

    link = await repo.create(from_meeting_id=a, to_meeting_id=b)

    assert await repo.delete(link.id) is True
    assert await repo.delete(link.id) is False


@pytest.mark.asyncio
async def test_get_returns_none_for_missing_link(db_session: AsyncSession) -> None:
    """`get` MUST return None for a non-existent link_id."""
    repo = MeetingLinkRepository(db_session)
    assert await repo.get(uuid4()) is None
