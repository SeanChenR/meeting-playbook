"""Tests for `MeetingRepository.transition_status` — slice-06.

Per spec meeting-management ADDED requirement "Meeting status transitions
are atomic and only allowed in the forward direction".
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.repository import (
    MeetingRepository,
    MeetingStatusConflict,
)


async def _seed_meeting(session: AsyncSession, *, user_id: str = "u_t", meeting_id: str = "m_t"):
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES (:uid, :uid, :email, true)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"uid": user_id, "email": f"{user_id}@example.com"},
    )
    await session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name, status)
            VALUES (:mid, :uid, 'T', 'C', 'M', 'scheduled')
            """
        ),
        {"mid": meeting_id, "uid": user_id},
    )
    await session.commit()


async def _read_status(session: AsyncSession, meeting_id: str) -> str:
    rows = await session.execute(
        text("SELECT status FROM meeting WHERE id = :mid"),
        {"mid": meeting_id},
    )
    row = rows.first()
    assert row is not None
    return row.status


@pytest.mark.asyncio
async def test_scheduled_to_in_progress_succeeds_and_advances_updated_at(db_session):
    await _seed_meeting(db_session, meeting_id="m_a")
    rows = await db_session.execute(
        text("SELECT updated_at FROM meeting WHERE id = :mid"), {"mid": "m_a"}
    )
    before = rows.first().updated_at

    await asyncio.sleep(0.01)

    await MeetingRepository(db_session).transition_status(
        meeting_id="m_a", expected_from="scheduled", target="in_progress"
    )
    await db_session.commit()

    assert await _read_status(db_session, "m_a") == "in_progress"
    rows2 = await db_session.execute(
        text("SELECT updated_at FROM meeting WHERE id = :mid"), {"mid": "m_a"}
    )
    after = rows2.first().updated_at
    assert after > before


@pytest.mark.asyncio
async def test_in_progress_to_completed_succeeds(db_session):
    await _seed_meeting(db_session, meeting_id="m_b")
    repo = MeetingRepository(db_session)
    await repo.transition_status(meeting_id="m_b", expected_from="scheduled", target="in_progress")
    await db_session.commit()

    await repo.transition_status(meeting_id="m_b", expected_from="in_progress", target="completed")
    await db_session.commit()

    assert await _read_status(db_session, "m_b") == "completed"


@pytest.mark.asyncio
async def test_completed_to_completed_raises_conflict(db_session):
    await _seed_meeting(db_session, meeting_id="m_c")
    repo = MeetingRepository(db_session)
    await repo.transition_status(meeting_id="m_c", expected_from="scheduled", target="in_progress")
    await repo.transition_status(meeting_id="m_c", expected_from="in_progress", target="completed")
    await db_session.commit()

    with pytest.raises(MeetingStatusConflict):
        await repo.transition_status(
            meeting_id="m_c", expected_from="in_progress", target="completed"
        )

    assert await _read_status(db_session, "m_c") == "completed"


@pytest.mark.asyncio
async def test_scheduled_to_completed_skipping_raises_conflict(db_session):
    await _seed_meeting(db_session, meeting_id="m_d")

    with pytest.raises(MeetingStatusConflict):
        await MeetingRepository(db_session).transition_status(
            meeting_id="m_d", expected_from="scheduled", target="completed"
        )

    assert await _read_status(db_session, "m_d") == "scheduled"
