"""End-to-end integration: voice enrollment + single-channel finalize.

Per slice-13 spec, this exercises the full pipeline against the test DB:

1. Seed a user + create a single-channel meeting with two clusters of chunks
   pre-labeled `speaker_cluster_1` / `speaker_cluster_2`.
2. POST a voice enrollment for that user (pyannote pipeline stubbed so the
   test does not load 300MB of ML weights).
3. Call `apply_speaker_attribution` with a stub `SingleChannelStrategy`
   provider that exposes cluster embeddings — one matches the enrolled
   vector, the other does not.
4. Verify the DB row count: chunks for the matching cluster carry
   `speaker = "me"`, the other cluster keeps its `speaker_cluster_*` label.
5. Repeat for a user WITHOUT enrollment — no `me` rename, every chunk
   keeps the original cluster label (the no-rename branch must be safe).

The stub provider is the same shape as the real `PyannoteProvider`:
`diarize(wav_path)` + `cluster_embeddings()` + `last_diarize_output`.
"""

from __future__ import annotations

import io
import struct
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app
from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.sessions.repository import SessionRepository
from meeting_playbook.speaker.diarization import DiarizationSegment
from meeting_playbook.speaker.finalize import apply_speaker_attribution
from meeting_playbook.voice_enrollment.repository import VoiceEnrollmentRepository


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


def _build_wav(duration_seconds: float, sample_rate: int = 16_000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frame_count = int(duration_seconds * sample_rate)
        wf.writeframes(struct.pack(f"<{frame_count}h", *([1000] * frame_count)))
    return buf.getvalue()


# Stable, distinct vectors used across the test fixtures so `find_me_cluster`
# can pick a winner deterministically:
_ENROLLED_VECTOR = [1.0, 0.0, 0.0]
_MATCHING_CLUSTER_VECTOR = [1.0, 0.0, 0.0]  # cosine = 1.0 vs enrolled
_OTHER_CLUSTER_VECTOR = [0.0, 1.0, 0.0]  # cosine = 0.0 vs enrolled


class _StubSingleChannelProvider:
    """Stub PyannoteProvider — supplies the two-method surface
    SingleChannelStrategy + voice-enrollment finalize rely on.
    """

    def __init__(self) -> None:
        self.last_diarize_output = object()  # opaque non-None sentinel

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        # Two clusters, equally sized, back-to-back so chunk-overlap math
        # is unambiguous in the assertions below.
        return [
            DiarizationSegment(start_ms=0, end_ms=2_000, cluster_id=1),
            DiarizationSegment(start_ms=2_000, end_ms=4_000, cluster_id=2),
        ]

    def cluster_embeddings(self) -> dict[int, np.ndarray]:
        return {
            1: np.asarray(_MATCHING_CLUSTER_VECTOR, dtype=np.float32),
            2: np.asarray(_OTHER_CLUSTER_VECTOR, dtype=np.float32),
        }


async def _truncate(db_url: str) -> None:
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "voice_enrollment" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


async def _seed_single_channel_meeting(db_url: str, *, user_id: str, meeting_id: str) -> None:
    """Insert a user + a single-channel meeting + 1 recording + 4 chunks
    pre-labeled `speaker_cluster_1`/`speaker_cluster_2` interleaved across
    the diarization timeline.
    """
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    base = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)
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
        await s.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name,
                                     me_display_name, status)
                VALUES (:mid, :uid, 'face-to-face test', 'Counterparty', 'Me', 'in_progress')
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
        rec = Recording(
            id=f"rec_{meeting_id}_mic",
            meeting_id=meeting_id,
            stream="me",
            file_path=f"/tmp/{meeting_id}_mic.wav",
            bytes=128_000,
            created_at=base,
        )
        s.add(rec)
        await s.flush()
        # Chunks placed inside cluster windows: chunk_1/3 fall in cluster 1's
        # 0–2000ms window, chunk_2/4 fall in cluster 2's 2000–4000ms window.
        offsets_and_clusters = [
            (500, 1),
            (2500, 2),
            (1500, 1),
            (3500, 2),
        ]
        for idx, (offset_ms, cluster_id) in enumerate(offsets_and_clusters, start=1):
            started = base + timedelta(milliseconds=offset_ms)
            chunk = TranscriptChunk(
                id=f"tc_{meeting_id}_{idx}",
                meeting_id=meeting_id,
                speaker=f"speaker_cluster_{cluster_id}",
                text=f"chunk {idx}",
                started_at=started,
                ended_at=started + timedelta(milliseconds=500),
                asr_provider_used="qwen3",
                confidence=0.9,
                created_at=base,
            )
            s.add(chunk)
        await s.commit()
    await engine.dispose()


async def _read_chunk_speakers(db_url: str, meeting_id: str) -> dict[str, str]:
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            result = await s.execute(
                select(TranscriptChunk)
                .where(TranscriptChunk.meeting_id == meeting_id)
                .order_by(TranscriptChunk.id)
            )
            return {c.id: c.speaker for c in result.scalars().all()}
    finally:
        await engine.dispose()


def _build_client(db_url_sync: str, tmp_voice_dir: Path) -> TestClient:
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    import os

    os.environ["VOICE_ENROLLMENT_DIR"] = str(tmp_voice_dir)

    db_url_async = _async_url(db_url_sync)
    engine = create_async_engine(db_url_async, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    return TestClient(app)


@pytest.mark.asyncio
async def test_e2e_enrolled_user_single_channel_meeting_renames_matching_cluster_to_me(
    _migrated_db_url, monkeypatch, tmp_path
) -> None:
    """Spec scenario: user has enrollment → cluster whose embedding matches
    the enrolled vector above threshold is renamed to `me`; the non-matching
    cluster's chunks keep their `speaker_cluster_*` labels.
    """
    await _truncate(_async_url(_migrated_db_url))

    user_id = "u_e2e"
    meeting_id = "m_e2e_single"
    await _seed_single_channel_meeting(
        _async_url(_migrated_db_url), user_id=user_id, meeting_id=meeting_id
    )

    # Step A: POST enrollment via HTTP — stub the pyannote pipeline so we
    # can control the exact embedding bytes that land in voice_enrollment.
    stub_embedding = np.asarray(_ENROLLED_VECTOR, dtype=np.float32).tobytes()
    monkeypatch.setattr(
        "meeting_playbook.voice_enrollment.router.compute_enrollment_embedding",
        lambda wav_path: stub_embedding,
    )
    client = _build_client(_migrated_db_url, tmp_path)
    response = client.post(
        "/api/voice_enrollment",
        headers={"X-User-Id": user_id},
        files={"file": ("sample.wav", _build_wav(25), "audio/wav")},
    )
    assert response.status_code == 200, response.text

    # Step B: drive `apply_speaker_attribution` with a stub provider that
    # exposes `cluster_embeddings()` matching cluster 1 against the enrolled
    # vector. We run against the same DB the endpoint just wrote into.
    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            session_repo = SessionRepository(s)
            ve_repo = VoiceEnrollmentRepository(s)
            await apply_speaker_attribution(
                meeting_id=meeting_id,
                repo=session_repo,
                single_channel_provider=_StubSingleChannelProvider(),
                voice_enrollment_repo=ve_repo,
                current_user_id=user_id,
                match_threshold=0.5,
            )
            await s.commit()
    finally:
        await engine.dispose()

    speakers = await _read_chunk_speakers(_async_url(_migrated_db_url), meeting_id)

    # Cluster 1 matches the enrolled vector → chunks for cluster 1 are now `me`.
    # Cluster 2's chunks keep their `speaker_cluster_2` label.
    assert speakers[f"tc_{meeting_id}_1"] == "me"
    assert speakers[f"tc_{meeting_id}_2"] == "speaker_cluster_2"
    assert speakers[f"tc_{meeting_id}_3"] == "me"
    assert speakers[f"tc_{meeting_id}_4"] == "speaker_cluster_2"


@pytest.mark.asyncio
async def test_e2e_unenrolled_user_single_channel_meeting_keeps_cluster_labels(
    _migrated_db_url, tmp_path
) -> None:
    """Spec scenario: user has NO `voice_enrollment` row → all chunks
    keep their `speaker_cluster_*` labels (no rename to `me`).
    """
    await _truncate(_async_url(_migrated_db_url))

    user_id = "u_unenrolled"
    meeting_id = "m_e2e_unenrolled"
    await _seed_single_channel_meeting(
        _async_url(_migrated_db_url), user_id=user_id, meeting_id=meeting_id
    )

    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as s:
            session_repo = SessionRepository(s)
            ve_repo = VoiceEnrollmentRepository(s)
            await apply_speaker_attribution(
                meeting_id=meeting_id,
                repo=session_repo,
                single_channel_provider=_StubSingleChannelProvider(),
                voice_enrollment_repo=ve_repo,
                current_user_id=user_id,
                match_threshold=0.5,
            )
            await s.commit()
    finally:
        await engine.dispose()

    speakers = await _read_chunk_speakers(_async_url(_migrated_db_url), meeting_id)

    # Every chunk keeps its cluster label — no `me` substitution anywhere.
    assert {sp for sp in speakers.values()} == {"speaker_cluster_1", "speaker_cluster_2"}
    assert "me" not in speakers.values()
