"""End-to-end integration for slice-12 Task 9.1.

Two scenarios:

1. **Single-channel + real pyannote pipeline**: seed a meeting with a single
   `recording` row pointing at `tests/speaker/fixtures/multi_speakers_zh.wav`
   and pre-existing transcript chunks whose `speaker` value is a placeholder
   (`"system"`). Run `apply_speaker_attribution` end-to-end. The post-DB
   state SHALL have every chunk labelled `speaker_cluster_*` and SHALL
   contain at least two distinct cluster ids — proving the SingleChannelStrategy
   wires `select_strategy → PyannoteProvider.diarize → assign_speakers →
   bulk update` correctly against a real audio fixture.

2. **Dual-channel pass-through**: seed a meeting with two recordings
   (`me` + `counterparty` streams) and chunks already labelled `me` /
   `counterparty` by the dual-channel ASR path. Running the finalize step
   SHALL leave the labels untouched (DualChannelStrategy validates without
   rewriting). No pyannote dependency on this branch.

The single-channel test is skipped unless `PYANNOTE_AUTH_TOKEN` is set AND
the fixture exists. The dual-channel test runs unconditionally.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.sessions.repository import SessionRepository
from meeting_playbook.speaker.finalize import apply_speaker_attribution


_FIXTURE = Path(__file__).parent.parent / "speaker" / "fixtures" / "multi_speakers_zh.wav"


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


async def _truncate(db_url: str) -> None:
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


async def _seed_single_channel_meeting(
    db_url: str, *, user_id: str, meeting_id: str, wav_path: Path
) -> None:
    """Insert a user + a single-channel meeting + 1 recording pointing at
    `wav_path` + 8 chunks spaced ~10s apart so each chunk falls inside a
    different diarization window. Initial `speaker = "system"` placeholder
    is used so the assertions can prove the finalize step rewrote them.
    """
    wav_bytes = wav_path.stat().st_size if wav_path.exists() else 0
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
                VALUES (:mid, :uid, 's12 single-channel e2e', 'Counterparty',
                        'Me', 'in_progress')
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
        rec = Recording(
            id=f"rec_{meeting_id}_mic",
            meeting_id=meeting_id,
            stream="me",
            file_path=str(wav_path),
            bytes=wav_bytes,
            created_at=base,
        )
        s.add(rec)
        await s.flush()
        for idx in range(8):
            started = base + timedelta(seconds=idx * 10)
            chunk = TranscriptChunk(
                id=f"tc_{meeting_id}_{idx + 1}",
                meeting_id=meeting_id,
                speaker="system",
                text=f"chunk {idx + 1}",
                started_at=started,
                ended_at=started + timedelta(seconds=8),
                asr_provider_used="qwen3",
                confidence=0.9,
                created_at=base,
            )
            s.add(chunk)
        await s.commit()
    await engine.dispose()


async def _seed_dual_channel_meeting(db_url: str, *, user_id: str, meeting_id: str) -> None:
    """Insert a user + dual-channel meeting + 2 recordings + 4 chunks
    pre-labelled as the dual-channel ASR pipeline would produce them.
    """
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    base = datetime(2026, 5, 15, 11, 0, 0, tzinfo=UTC)
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
                VALUES (:mid, :uid, 's12 dual-channel e2e', 'Counterparty',
                        'Me', 'in_progress')
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
        for stream in ("me", "counterparty"):
            s.add(
                Recording(
                    id=f"rec_{meeting_id}_{stream}",
                    meeting_id=meeting_id,
                    stream=stream,
                    file_path=f"/tmp/{meeting_id}_{stream}.wav",
                    bytes=64_000,
                    created_at=base,
                )
            )
        await s.flush()
        for idx, speaker in enumerate(["me", "counterparty", "me", "counterparty"], start=1):
            started = base + timedelta(seconds=idx * 2)
            s.add(
                TranscriptChunk(
                    id=f"tc_{meeting_id}_{idx}",
                    meeting_id=meeting_id,
                    speaker=speaker,
                    text=f"chunk {idx}",
                    started_at=started,
                    ended_at=started + timedelta(seconds=2),
                    asr_provider_used="qwen3",
                    confidence=0.9,
                    created_at=base,
                )
            )
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


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("PYANNOTE_AUTH_TOKEN"),
    reason="PYANNOTE_AUTH_TOKEN not set; real-audio single-channel e2e skipped",
)
@pytest.mark.skipif(
    not _FIXTURE.exists(),
    reason=f"fixture not present at {_FIXTURE}",
)
def test_single_channel_e2e_labels_all_chunks_as_speaker_cluster(
    _migrated_db_url,
) -> None:
    """Single-channel finalize against the real multi-speaker fixture.

    Acceptance (per slice-12 Task 9.1):
    - every chunk's `speaker` matches `speaker_cluster_*`
    - at least two distinct cluster ids are observed
    """
    db_url = _async_url(_migrated_db_url)
    user_id = "u_s12_single"
    meeting_id = "m_s12_single"

    async def _run() -> dict[str, str]:
        await _truncate(db_url)
        await _seed_single_channel_meeting(
            db_url, user_id=user_id, meeting_id=meeting_id, wav_path=_FIXTURE
        )
        engine = create_async_engine(db_url, future=True, poolclass=NullPool)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with Session() as s:
                repo = SessionRepository(s)
                result = await apply_speaker_attribution(meeting_id=meeting_id, repo=repo)
                await s.commit()
            assert result.strategy_name == "SingleChannelStrategy"
        finally:
            await engine.dispose()
        return await _read_chunk_speakers(db_url, meeting_id)

    speakers = asyncio.run(_run())

    assert speakers, "no chunks survived finalize"
    for chunk_id, sp in speakers.items():
        assert sp.startswith("speaker_cluster_"), (
            f"chunk {chunk_id!r} kept non-cluster label {sp!r} after SingleChannelStrategy"
        )

    cluster_ids = {sp for sp in speakers.values() if sp != "speaker_cluster_unknown"}
    assert len(cluster_ids) >= 2, (
        f"expected ≥2 distinct cluster labels across chunks, got {sorted(cluster_ids)}"
    )


def test_dual_channel_e2e_keeps_me_and_counterparty_labels(
    _migrated_db_url,
) -> None:
    """Dual-channel finalize is a pass-through validator — the chunks
    arrive already labelled `me` / `counterparty` from the ASR pipeline,
    and the finalize step SHALL leave them untouched.
    """
    db_url = _async_url(_migrated_db_url)
    user_id = "u_s12_dual"
    meeting_id = "m_s12_dual"

    async def _run() -> dict[str, str]:
        await _truncate(db_url)
        await _seed_dual_channel_meeting(db_url, user_id=user_id, meeting_id=meeting_id)
        engine = create_async_engine(db_url, future=True, poolclass=NullPool)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with Session() as s:
                repo = SessionRepository(s)
                result = await apply_speaker_attribution(meeting_id=meeting_id, repo=repo)
                await s.commit()
            assert result.strategy_name == "DualChannelStrategy"
            assert result.chunks_updated == 0
        finally:
            await engine.dispose()
        return await _read_chunk_speakers(db_url, meeting_id)

    speakers = asyncio.run(_run())

    assert set(speakers.values()) == {"me", "counterparty"}
