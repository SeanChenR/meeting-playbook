"""Voice enrollment HTTP endpoint tests — POST /api/voice_enrollment.

Verifies the 4 spec scenarios under "POST /api/voice_enrollment uploads +
replaces the per-user enrollment":
- valid 30-second WAV from a single speaker enrolls successfully
- re-enrollment overwrites the existing row and WAV
- sample longer than 30 seconds is rejected and WAV not retained
- multi-speaker sample is rejected and WAV not retained

The pyannote pipeline is replaced with a deterministic stub via monkeypatch
on `compute_enrollment_embedding` — the tests are about validation +
storage + repo behaviour, not about pyannote correctness.
"""

from __future__ import annotations

import asyncio
import io
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app
from meeting_playbook.voice_enrollment.embedding import InvalidEnrollmentSample
from meeting_playbook.voice_enrollment.models import VoiceEnrollment


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


def _build_wav(duration_seconds: float, sample_rate: int = 16_000) -> bytes:
    """Build a valid in-memory 16kHz mono 16-bit PCM WAV of `duration_seconds`."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # Quiet sinusoidal noise so the file isn't trivially flagged.
        frame_count = int(duration_seconds * sample_rate)
        wf.writeframes(struct.pack(f"<{frame_count}h", *([1000] * frame_count)))
    return buf.getvalue()


async def _seed_user(db_url: str, user_id: str = "u_voice") -> None:
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        await s.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"{user_id}@example.com"},
        )
        await s.commit()
    await engine.dispose()


async def _truncate(db_url: str) -> None:
    engine = create_async_engine(db_url, future=True)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "voice_enrollment" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


async def _count_enrollment_rows(db_url: str, user_id: str) -> int:
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            result = await s.execute(
                select(VoiceEnrollment).where(VoiceEnrollment.user_id == user_id)
            )
            return len(list(result.scalars().all()))
    finally:
        await engine.dispose()


async def _read_enrollment(db_url: str, user_id: str) -> VoiceEnrollment | None:
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            result = await s.execute(
                select(VoiceEnrollment).where(VoiceEnrollment.user_id == user_id)
            )
            return result.scalar_one_or_none()
    finally:
        await engine.dispose()


def _build_client(db_url_sync: str, tmp_voice_dir: Path) -> TestClient:
    """Build a TestClient that uses the test DB and a tmp voice-enrollment dir.

    Setting `VOICE_ENROLLMENT_DIR` env var is honoured by `get_settings()` —
    the .env-derived default is overridden per-test so the suite never writes
    to the developer's real `~/MeetingPlaybook/voice_enrollments`.
    """
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    import os

    os.environ["VOICE_ENROLLMENT_DIR"] = str(tmp_voice_dir)

    db_url_async = _async_url(db_url_sync)
    # NullPool so each request creates its own connection — TestClient spins
    # a fresh event loop per call and asyncpg connections cannot cross loops.
    engine = create_async_engine(db_url_async, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    return TestClient(app)


def test_get_voice_enrollment_returns_null_when_no_row(_migrated_db_url, tmp_path):
    """No enrollment → 200 with `{enrolled_at: null}`. The endpoint never
    returns 404 so the frontend can render the empty-state without juggling
    a not-found error.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)
    response = client.get("/api/voice_enrollment", headers={"X-User-Id": "u_voice"})

    assert response.status_code == 200, response.text
    assert response.json() == {"enrolled_at": None}


def test_get_voice_enrollment_returns_iso_timestamp_when_row_present(
    _migrated_db_url, monkeypatch, tmp_path
):
    """After upsert, GET returns `{enrolled_at: <iso8601>}` so the
    `/settings/voice` page can render 'previously enrolled' on reload.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url)))
    monkeypatch.setattr(
        "meeting_playbook.voice_enrollment.router.compute_enrollment_embedding",
        lambda wav_path: b"\x01\x02\x03\x04" * 8,
    )

    client = _build_client(_migrated_db_url, tmp_path)
    post_response = client.post(
        "/api/voice_enrollment",
        headers={"X-User-Id": "u_voice"},
        files={"file": ("sample.wav", _build_wav(20), "audio/wav")},
    )
    assert post_response.status_code == 200

    get_response = client.get("/api/voice_enrollment", headers={"X-User-Id": "u_voice"})

    assert get_response.status_code == 200
    body = get_response.json()
    assert isinstance(body["enrolled_at"], str)
    # POST and GET should return the same timestamp for the just-saved row.
    assert body["enrolled_at"] == post_response.json()["enrolled_at"]


def test_post_voice_enrollment_valid_sample_writes_row_and_wav(
    _migrated_db_url, monkeypatch, tmp_path
):
    """Spec scenario: valid single-speaker WAV → 200 + row + wav on disk +
    embedding length divisible by 4 (float32)."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url)))

    # Stub the pyannote pipeline so the test doesn't load 300MB of models.
    stub_embedding = b"\x01\x02\x03\x04" * 4  # 16 bytes, divisible by 4
    monkeypatch.setattr(
        "meeting_playbook.voice_enrollment.router.compute_enrollment_embedding",
        lambda wav_path: stub_embedding,
    )

    client = _build_client(_migrated_db_url, tmp_path)
    wav = _build_wav(duration_seconds=25)

    response = client.post(
        "/api/voice_enrollment",
        headers={"X-User-Id": "u_voice"},
        files={"file": ("sample.wav", wav, "audio/wav")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "enrolled_at" in body

    # Row exists for u_voice, embedding length is divisible by 4.
    assert asyncio.run(_count_enrollment_rows(_async_url(_migrated_db_url), "u_voice")) == 1
    row = asyncio.run(_read_enrollment(_async_url(_migrated_db_url), "u_voice"))
    assert row is not None
    assert len(row.embedding) == len(stub_embedding)
    assert len(row.embedding) % 4 == 0

    # WAV file is on disk at the expected path.
    assert (tmp_path / "u_voice.wav").exists()


def test_post_voice_enrollment_reenroll_replaces_existing_row(
    _migrated_db_url, monkeypatch, tmp_path
):
    """Spec scenario: re-enroll overwrites embedding + WAV; row count stays 1."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url)))

    embeddings = [b"\xaa" * 16, b"\xbb" * 16]
    call_count = {"n": 0}

    def _stub(wav_path):
        i = call_count["n"]
        call_count["n"] = i + 1
        return embeddings[i]

    monkeypatch.setattr(
        "meeting_playbook.voice_enrollment.router.compute_enrollment_embedding",
        _stub,
    )

    client = _build_client(_migrated_db_url, tmp_path)
    wav_a = _build_wav(duration_seconds=10)
    wav_b = _build_wav(duration_seconds=20)

    r1 = client.post(
        "/api/voice_enrollment",
        headers={"X-User-Id": "u_voice"},
        files={"file": ("a.wav", wav_a, "audio/wav")},
    )
    assert r1.status_code == 200, r1.text
    first_ts = r1.json()["enrolled_at"]

    r2 = client.post(
        "/api/voice_enrollment",
        headers={"X-User-Id": "u_voice"},
        files={"file": ("b.wav", wav_b, "audio/wav")},
    )
    assert r2.status_code == 200, r2.text
    second_ts = r2.json()["enrolled_at"]

    # Row count still 1; embedding is the SECOND value; created_at is later.
    assert asyncio.run(_count_enrollment_rows(_async_url(_migrated_db_url), "u_voice")) == 1
    row = asyncio.run(_read_enrollment(_async_url(_migrated_db_url), "u_voice"))
    assert row is not None
    assert row.embedding == embeddings[1]
    assert second_ts >= first_ts


def test_post_voice_enrollment_sample_too_long_is_rejected_and_wav_removed(
    _migrated_db_url, monkeypatch, tmp_path
):
    """Spec scenario: 45-second WAV → 422 voice_enrollment.too_long; WAV
    SHALL be removed from disk so failed uploads do not accumulate."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url)))

    # The embedding stub MUST NOT be called for this path — but patch it
    # anyway so an accidental call fails loud.
    monkeypatch.setattr(
        "meeting_playbook.voice_enrollment.router.compute_enrollment_embedding",
        lambda wav_path: (_ for _ in ()).throw(  # pragma: no cover
            AssertionError("compute_enrollment_embedding must not run for too-long sample")
        ),
    )

    client = _build_client(_migrated_db_url, tmp_path)
    wav = _build_wav(duration_seconds=45)

    response = client.post(
        "/api/voice_enrollment",
        headers={"X-User-Id": "u_voice"},
        files={"file": ("toolong.wav", wav, "audio/wav")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "voice_enrollment.too_long"
    # No row inserted, no WAV left on disk.
    assert asyncio.run(_count_enrollment_rows(_async_url(_migrated_db_url), "u_voice")) == 0
    assert not (tmp_path / "u_voice.wav").exists()


def test_post_voice_enrollment_invalid_sample_is_rejected_and_wav_removed(
    _migrated_db_url, monkeypatch, tmp_path
):
    """Spec scenario: multi-speaker / silent WAV (compute raises
    InvalidEnrollmentSample) → 422 voice_enrollment.invalid_sample; WAV
    SHALL be removed from disk."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url)))

    def _stub_multi_speaker(wav_path):
        raise InvalidEnrollmentSample(
            "Pipeline detected 2 speakers in the sample; enrollment requires exactly 1."
        )

    monkeypatch.setattr(
        "meeting_playbook.voice_enrollment.router.compute_enrollment_embedding",
        _stub_multi_speaker,
    )

    client = _build_client(_migrated_db_url, tmp_path)
    wav = _build_wav(duration_seconds=20)

    response = client.post(
        "/api/voice_enrollment",
        headers={"X-User-Id": "u_voice"},
        files={"file": ("multi.wav", wav, "audio/wav")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "voice_enrollment.invalid_sample"
    assert "speakers" in body["message"].lower()
    # No row + no orphan WAV.
    assert asyncio.run(_count_enrollment_rows(_async_url(_migrated_db_url), "u_voice")) == 0
    assert not (tmp_path / "u_voice.wav").exists()


def test_post_voice_enrollment_unsupported_content_type_rejected(_migrated_db_url, tmp_path):
    """Wrong content-type → 422 voice_enrollment.unsupported_format."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_user(_async_url(_migrated_db_url)))

    client = _build_client(_migrated_db_url, tmp_path)

    response = client.post(
        "/api/voice_enrollment",
        headers={"X-User-Id": "u_voice"},
        files={"file": ("sample.mp3", b"id3\x00\x00\x00", "audio/mpeg")},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "voice_enrollment.unsupported_format"
    assert asyncio.run(_count_enrollment_rows(_async_url(_migrated_db_url), "u_voice")) == 0
