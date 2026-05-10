"""SummaryRepository — slice-10 write path + stale-flag tests.

Per spec meeting-summary ADDED requirement scenarios (cascade delete /
upsert atomic / get_for_meeting None / 4 is_stale variants).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.summarization.repository import SummaryRepository


async def _seed_meeting(session: AsyncSession, *, mid: str = "m_sum") -> None:
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ('u_sum', 'Sean', 'sean@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, 'u_sum', 'T', 'C', 'M')
            """
        ),
        {"mid": mid},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_upsert_creates_then_replaces_row_atomically(db_session):
    """Slice-10 Decision 1: upsert creates row first time, replaces on conflict."""
    await _seed_meeting(db_session, mid="m_up")
    repo = SummaryRepository(db_session)

    first = await repo.upsert(meeting_id="m_up", markdown="v1")
    assert first.id.startswith("sm_")
    assert first.markdown == "v1"
    # SQLAlchemy identity-map: `first` and `second` end up as the SAME
    # Python instance (UNIQUE on meeting_id → upsert mutates the existing
    # row's attributes in-place after `populate_existing`). Snapshot the
    # generated_at BEFORE the second upsert or the comparison reads the
    # post-mutation value on both sides.
    first_generated_at = first.generated_at

    # Sleep 1ms so server-side now() advances measurably.
    await asyncio.sleep(0.01)

    second = await repo.upsert(meeting_id="m_up", markdown="v2")
    assert second.markdown == "v2"
    assert second.generated_at > first_generated_at, "regenerate must advance generated_at"

    # Exactly one row remains (UNIQUE on meeting_id enforced).
    rows = await db_session.execute(text("SELECT COUNT(*) FROM summary WHERE meeting_id = 'm_up'"))
    assert rows.scalar_one() == 1


@pytest.mark.asyncio
async def test_get_for_meeting_returns_none_when_absent(db_session):
    """Slice-10: get_for_meeting on never-summarized meeting returns None."""
    await _seed_meeting(db_session, mid="m_none")
    repo = SummaryRepository(db_session)
    assert await repo.get_for_meeting("m_none") is None


@pytest.mark.asyncio
async def test_cascade_delete_on_meeting_removal(db_session):
    """Slice-10: deleting the meeting cascades to its summary row."""
    await _seed_meeting(db_session, mid="m_cas")
    repo = SummaryRepository(db_session)
    await repo.upsert(meeting_id="m_cas", markdown="x")
    pre = await db_session.execute(text("SELECT COUNT(*) FROM summary WHERE meeting_id = 'm_cas'"))
    assert pre.scalar_one() == 1

    await db_session.execute(text("DELETE FROM meeting WHERE id = 'm_cas'"))
    await db_session.commit()

    post = await db_session.execute(text("SELECT COUNT(*) FROM summary WHERE meeting_id = 'm_cas'"))
    assert post.scalar_one() == 0


@pytest.mark.asyncio
async def test_get_with_stale_flag_true_when_transcript_chunk_newer_than_generated_at(
    db_session,
):
    """Slice-10 Decision 9: transcript_chunk newer than summary → is_stale=True."""
    await _seed_meeting(db_session, mid="m_stale_t")
    repo = SummaryRepository(db_session)
    await repo.upsert(meeting_id="m_stale_t", markdown="early")

    # Insert a transcript_chunk with started_at + created_at strictly later.
    future = datetime.now(UTC) + timedelta(seconds=30)
    await db_session.execute(
        text(
            """
            INSERT INTO transcript_chunk (id, meeting_id, speaker, text, started_at, ended_at, asr_provider_used, created_at)
            VALUES ('tc_stale', 'm_stale_t', 'me', 'x', :ts, :ts2, 'whisper', :ts)
            """
        ),
        {"ts": future, "ts2": future + timedelta(seconds=10)},
    )
    await db_session.commit()

    out = await repo.get_with_stale_flag("m_stale_t")
    assert out is not None
    assert out.is_stale is True


@pytest.mark.asyncio
async def test_get_with_stale_flag_true_when_playbook_updated_after_summary(db_session):
    """Slice-10 Decision 9: playbook.updated_at later than summary → is_stale=True."""
    await _seed_meeting(db_session, mid="m_stale_p")
    repo = SummaryRepository(db_session)
    await repo.upsert(meeting_id="m_stale_p", markdown="early")

    future = datetime.now(UTC) + timedelta(seconds=30)
    # Insert a playbook row with updated_at in the future.
    await db_session.execute(
        text(
            """
            INSERT INTO playbook (id, meeting_id, free_form_markdown, objective, counterparty_profile,
                                  anticipated_topics, anticipated_objections, talking_points, red_lines,
                                  created_at, updated_at)
            VALUES ('pb_stale', 'm_stale_p', '', '', '', '', '', '', '', :ts, :ts)
            """
        ),
        {"ts": future},
    )
    await db_session.commit()

    out = await repo.get_with_stale_flag("m_stale_p")
    assert out is not None
    assert out.is_stale is True


@pytest.mark.asyncio
async def test_get_with_stale_flag_true_when_chat_message_newer_than_generated_at(
    db_session,
):
    """Slice-10 Decision 9: newer chat_message → is_stale=True."""
    await _seed_meeting(db_session, mid="m_stale_c")
    repo = SummaryRepository(db_session)
    await repo.upsert(meeting_id="m_stale_c", markdown="early")

    future = datetime.now(UTC) + timedelta(seconds=30)
    await db_session.execute(
        text(
            """
            INSERT INTO chat_message (id, meeting_id, role, content, created_at)
            VALUES ('cm_stale', 'm_stale_c', 'user', 'q', :ts)
            """
        ),
        {"ts": future},
    )
    await db_session.commit()

    out = await repo.get_with_stale_flag("m_stale_c")
    assert out is not None
    assert out.is_stale is True


@pytest.mark.asyncio
async def test_get_with_stale_flag_false_when_nothing_changed_after_generation(
    db_session,
):
    """Slice-10 Decision 9: zero newer rows → is_stale=False."""
    await _seed_meeting(db_session, mid="m_fresh")
    repo = SummaryRepository(db_session)
    # Generate summary AT now; no transcript / playbook / chat exists.
    await repo.upsert(meeting_id="m_fresh", markdown="fresh")

    out = await repo.get_with_stale_flag("m_fresh")
    assert out is not None
    assert out.is_stale is False


@pytest.mark.asyncio
async def test_get_with_stale_flag_returns_none_when_no_summary(db_session):
    """Slice-10: get_with_stale_flag on missing summary returns None (not exception)."""
    await _seed_meeting(db_session, mid="m_no_sum")
    repo = SummaryRepository(db_session)
    assert await repo.get_with_stale_flag("m_no_sum") is None
