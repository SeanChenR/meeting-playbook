"""Integration tests for `VoiceEnrollmentRepository`.

Verifies the spec scenarios under "voice_enrollment table stores one
embedding per user":
- Re-upload replaces the existing row in place (row count stays 1).
- Deleting the user cascades to remove the voice_enrollment row.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.voice_enrollment.models import VoiceEnrollment
from meeting_playbook.voice_enrollment.repository import VoiceEnrollmentRepository


async def _seed_user(session: AsyncSession, user_id: str = "u_ve") -> None:
    await session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES (:uid, 'Voice User', :email, true)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"uid": user_id, "email": f"{user_id}@example.com"},
    )
    await session.commit()


async def _count_enrollment_rows(session: AsyncSession, user_id: str) -> int:
    result = await session.execute(
        select(VoiceEnrollment).where(VoiceEnrollment.user_id == user_id)
    )
    return len(list(result.scalars().all()))


@pytest.mark.asyncio
async def test_upsert_creates_row_when_no_existing_enrollment(db_session):
    await _seed_user(db_session)
    repo = VoiceEnrollmentRepository(db_session)

    row = await repo.upsert(
        user_id="u_ve",
        sample_wav_path="/tmp/u_ve.wav",
        embedding=b"\x00\x01\x02\x03",
    )

    assert row.user_id == "u_ve"
    assert row.sample_wav_path == "/tmp/u_ve.wav"
    assert row.embedding == b"\x00\x01\x02\x03"
    assert await _count_enrollment_rows(db_session, "u_ve") == 1


@pytest.mark.asyncio
async def test_reupload_replaces_existing_row_keeping_count_at_one(db_session):
    """Spec scenario: re-upload replaces the existing voice_enrollment row."""
    await _seed_user(db_session)
    repo = VoiceEnrollmentRepository(db_session)

    first = await repo.upsert(
        user_id="u_ve",
        sample_wav_path="/tmp/first.wav",
        embedding=b"\x11" * 16,
    )
    first_ts = first.created_at

    second = await repo.upsert(
        user_id="u_ve",
        sample_wav_path="/tmp/second.wav",
        embedding=b"\x22" * 16,
    )

    assert await _count_enrollment_rows(db_session, "u_ve") == 1
    assert second.sample_wav_path == "/tmp/second.wav"
    assert second.embedding == b"\x22" * 16
    assert second.created_at >= first_ts


@pytest.mark.asyncio
async def test_get_for_user_returns_none_when_no_row(db_session):
    await _seed_user(db_session, user_id="u_no_enrollment")
    repo = VoiceEnrollmentRepository(db_session)

    result = await repo.get_for_user("u_no_enrollment")

    assert result is None


@pytest.mark.asyncio
async def test_get_for_user_returns_row_after_upsert(db_session):
    await _seed_user(db_session)
    repo = VoiceEnrollmentRepository(db_session)
    await repo.upsert(
        user_id="u_ve",
        sample_wav_path="/tmp/u_ve.wav",
        embedding=b"\xaa" * 8,
    )

    result = await repo.get_for_user("u_ve")

    assert result is not None
    assert result.user_id == "u_ve"
    assert result.embedding == b"\xaa" * 8


@pytest.mark.asyncio
async def test_deleting_user_cascades_to_voice_enrollment(db_session):
    """Spec scenario: deleting the user removes the voice_enrollment row."""
    await _seed_user(db_session)
    repo = VoiceEnrollmentRepository(db_session)
    await repo.upsert(
        user_id="u_ve",
        sample_wav_path="/tmp/u_ve.wav",
        embedding=b"\x33" * 16,
    )
    assert await _count_enrollment_rows(db_session, "u_ve") == 1

    await db_session.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": "u_ve"})
    await db_session.commit()

    assert await _count_enrollment_rows(db_session, "u_ve") == 0
