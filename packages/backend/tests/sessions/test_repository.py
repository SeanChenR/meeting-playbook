"""SessionRepository — transcript_chunk + recording inserts.

Per spec meeting-session ADDED requirement "Transcript chunks are persisted
in chronological order" + "Audio capture writes one WAV file per session".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.sessions.repository import SessionRepository


async def _seed_meeting(session: AsyncSession, *, mid: str = "m_s") -> None:
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ('u_s', 'Sean', 'sean@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, 'u_s', 'T', 'C', 'M')
            """
        ),
        {"mid": mid},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_insert_chunk_persists_and_returns_orm_object(db_session):
    await _seed_meeting(db_session)
    repo = SessionRepository(db_session)
    started = datetime.now(timezone.utc)
    chunk = await repo.insert_chunk(
        meeting_id="m_s",
        speaker="me",
        text_content="hello",
        started_at=started,
        ended_at=started + timedelta(seconds=10),
        asr_provider_used="whisper",
        confidence=0.9,
    )
    await db_session.commit()
    assert chunk.id.startswith("tc_")
    assert chunk.meeting_id == "m_s"
    assert chunk.text == "hello"


@pytest.mark.asyncio
async def test_chunks_query_back_in_started_at_ascending(db_session):
    await _seed_meeting(db_session, mid="m_order")
    repo = SessionRepository(db_session)
    base = datetime.now(timezone.utc)
    # Insert OUT OF ORDER
    for offset in (5, 1, 3):
        await repo.insert_chunk(
            meeting_id="m_order",
            speaker="me",
            text_content=f"chunk_{offset}",
            started_at=base + timedelta(seconds=offset),
            ended_at=base + timedelta(seconds=offset + 1),
            asr_provider_used="whisper",
            confidence=None,
        )
    await db_session.commit()

    rows = await db_session.execute(
        text(
            "SELECT text FROM transcript_chunk WHERE meeting_id = 'm_order' ORDER BY started_at ASC"
        )
    )
    texts = [r.text for r in rows]
    assert texts == ["chunk_1", "chunk_3", "chunk_5"]


@pytest.mark.asyncio
async def test_insert_chunk_rejects_invalid_speaker(db_session):
    await _seed_meeting(db_session, mid="m_bad")
    repo = SessionRepository(db_session)
    with pytest.raises((IntegrityError, DBAPIError)):
        await repo.insert_chunk(
            meeting_id="m_bad",
            speaker="stranger",
            text_content="x",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            asr_provider_used="whisper",
            confidence=None,
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_insert_recording_round_trips(db_session):
    await _seed_meeting(db_session, mid="m_rec")
    repo = SessionRepository(db_session)
    rec = await repo.insert_recording(
        meeting_id="m_rec",
        stream="me",
        file_path="/tmp/m_rec/me.wav",
        bytes_size=12345,
    )
    await db_session.commit()
    assert rec.id.startswith("rec_")
    assert rec.stream == "me"
    assert rec.bytes == 12345


@pytest.mark.asyncio
async def test_insert_recording_unique_per_meeting_stream(db_session):
    await _seed_meeting(db_session, mid="m_dup")
    repo = SessionRepository(db_session)
    await repo.insert_recording(
        meeting_id="m_dup",
        stream="me",
        file_path="/tmp/m_dup/me.wav",
        bytes_size=100,
    )
    await db_session.commit()
    with pytest.raises((IntegrityError, DBAPIError)):
        await repo.insert_recording(
            meeting_id="m_dup",
            stream="me",
            file_path="/tmp/m_dup/me_again.wav",
            bytes_size=200,
        )
        await db_session.commit()
