"""OfflineIngestPipeline orchestration tests — slice-14 task 4.1.

Verifies the spec scenarios under
"Pipeline writes a single offline recording row and spawns ASR task":

- happy path → exactly one `recording` row (source=offline, stream=me),
  meeting transitions scheduled → in_progress
- ASR runner completes → meeting transitions in_progress → completed AND
  the transcript_chunk rows wear `speaker_cluster_*` labels
- second spawn while in-flight → runtime state ends as `failed` with
  `error_code = "offline_ingest.busy"`

The transcode subprocess is replaced with a stub that just writes a tiny
WAV at the canonical path; the ASR runner is replaced with a stub that
writes a handful of pre-labelled transcript_chunk rows. The integration
test in task 6.1 covers the real ffmpeg + pyannote path against the
slice-12 multi-speakers fixture.
"""

from __future__ import annotations

import asyncio
import struct
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from meeting_playbook.offline_ingest import pipeline, runtime
from meeting_playbook.offline_ingest.transcode import OfflineIngestTranscodeError
from meeting_playbook.offline_ingest.tus_protocol import TusSession
from meeting_playbook.sessions.models import Recording, TranscriptChunk


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


def _write_tiny_wav(path: Path, duration_seconds: float = 1.0) -> None:
    frame_count = int(duration_seconds * 16_000)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16_000)
        wf.writeframes(struct.pack(f"<{frame_count}h", *([0] * frame_count)))


async def _truncate(db_url: str) -> None:
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


async def _seed_eligible_meeting(db_url: str, user_id: str, meeting_id: str) -> None:
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"{user_id}@example.com"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, status, scheduled_start_at, scheduled_end_at
                )
                VALUES (:mid, :uid, 'offline', 'C', 'M', 'scheduled', :start, :end)
                """
            ),
            {
                "mid": meeting_id,
                "uid": user_id,
                "start": datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
                "end": datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
            },
        )
    await engine.dispose()


def _make_session(
    meeting_id: str, user_id: str, staging_path: Path, *, upload_length: int = 1024
) -> TusSession:
    return TusSession(
        upload_id="upload_test",
        meeting_id=meeting_id,
        user_id=user_id,
        upload_length=upload_length,
        current_offset=upload_length,
        metadata={
            "filename": "sample.mp3",
            "mimetype": "audio/mpeg",
        },
        staging_path=staging_path,
        actual_started_at=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
    )


@pytest.fixture(autouse=True)
def _reset():
    runtime.reset()
    yield
    runtime.reset()


def test_pipeline_writes_offline_recording_and_transitions_to_in_progress(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Happy path: pipeline.run writes exactly one recording row with
    `source = "offline"`, transitions the meeting to `in_progress`, and
    spawns the ASR runner.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url), "u_p1", "m_p1"))

    # Stub transcode: skip ffmpeg, just write a tiny wav at the canonical path.
    async def _fake_transcode(*, staging_path, output_path):
        _write_tiny_wav(output_path, duration_seconds=1.0)
        staging_path.unlink(missing_ok=True)

    monkeypatch.setattr(pipeline, "transcode_to_canonical_wav", _fake_transcode)

    # Stub runner: pretend ASR finished instantly.
    async def _fake_runner(meeting_id: str) -> None:
        return None

    monkeypatch.setattr(pipeline, "_build_asr_runner", lambda: _fake_runner)

    staging = tmp_path / "upload_test.partial"
    staging.write_bytes(b"\x00" * 1024)
    session = _make_session("m_p1", "u_p1", staging)

    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)
    monkeypatch.setattr(pipeline, "_get_offline_upload_dir", lambda: tmp_path.resolve())

    try:
        asyncio.run(pipeline.run(session))

        async def _check() -> tuple[int, str, str | None, datetime | None]:
            async with Session() as s:
                count = (
                    await s.execute(
                        text("SELECT COUNT(*) FROM recording WHERE meeting_id = 'm_p1'")
                    )
                ).scalar_one()
                rec = (
                    await s.execute(select(Recording).where(Recording.meeting_id == "m_p1"))
                ).scalar_one()
                meeting_status = (
                    await s.execute(text("SELECT status FROM meeting WHERE id = 'm_p1'"))
                ).scalar_one()
                return count, meeting_status, rec.source, rec.started_at

        count, status_value, source, started_at = asyncio.run(_check())
        assert count == 1
        # Status may already be `completed` if the runner's wrapper finished
        # quickly; `in_progress` is the transitional state pipeline sets.
        assert status_value in ("in_progress", "completed")
        assert source == "offline"
        assert started_at == datetime(2026, 5, 14, 9, 0, tzinfo=UTC)
    finally:
        asyncio.run(engine.dispose())


def test_pipeline_busy_meeting_sets_error_state(_migrated_db_url, tmp_path, monkeypatch):
    """Second pipeline.run while an ASR task is already in-flight for the
    meeting must NOT write a duplicate recording and must surface the busy
    error via runtime state.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url), "u_b1", "m_b1"))

    async def _fake_transcode(*, staging_path, output_path):
        _write_tiny_wav(output_path, duration_seconds=1.0)
        staging_path.unlink(missing_ok=True)

    monkeypatch.setattr(pipeline, "transcode_to_canonical_wav", _fake_transcode)

    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)
    monkeypatch.setattr(pipeline, "_get_offline_upload_dir", lambda: tmp_path.resolve())

    staging = tmp_path / "upload_test.partial"
    staging.write_bytes(b"\x00" * 1024)
    session = _make_session("m_b1", "u_b1", staging)

    async def _orchestrate() -> dict:
        held = asyncio.Event()

        async def _hang(meeting_id: str) -> None:
            await held.wait()

        await runtime.spawn_ingest_task("m_b1", runner=_hang)
        try:
            await pipeline.run(session)
            return runtime.get_state("m_b1")
        finally:
            held.set()
            task = runtime._inflight.get("m_b1")  # type: ignore[attr-defined]
            if task is not None:
                await task

    try:
        state = asyncio.run(_orchestrate())
        assert state["state"] == "failed", state
        assert state.get("error_code") == "offline_ingest.busy", state

        async def _check_no_recording() -> int:
            async with Session() as s:
                return (
                    await s.execute(
                        text("SELECT COUNT(*) FROM recording WHERE meeting_id = 'm_b1'")
                    )
                ).scalar_one()

        assert asyncio.run(_check_no_recording()) == 0
    finally:
        asyncio.run(engine.dispose())


def test_pipeline_asr_runner_completion_marks_meeting_completed(
    _migrated_db_url, tmp_path, monkeypatch
):
    """The ASR runner stub writes a couple of `speaker_cluster_*` chunks
    and transitions the meeting to completed. Pipeline.run + runtime
    together must surface that final state.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url), "u_p2", "m_p2"))

    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _fake_transcode(*, staging_path, output_path):
        _write_tiny_wav(output_path, duration_seconds=1.0)
        staging_path.unlink(missing_ok=True)

    monkeypatch.setattr(pipeline, "transcode_to_canonical_wav", _fake_transcode)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)
    monkeypatch.setattr(pipeline, "_get_offline_upload_dir", lambda: tmp_path.resolve())

    async def _fake_runner(meeting_id: str) -> None:
        base = datetime(2026, 5, 14, 9, 0, tzinfo=UTC)
        async with Session() as s:
            for i, cluster in enumerate([1, 2, 1], start=1):
                started = base + timedelta(seconds=i * 2)
                s.add(
                    TranscriptChunk(
                        id=f"tc_p2_{i}",
                        meeting_id=meeting_id,
                        speaker=f"speaker_cluster_{cluster}",
                        text=f"chunk {i}",
                        started_at=started,
                        ended_at=started + timedelta(seconds=2),
                        asr_provider_used="stub",
                        confidence=0.9,
                        created_at=datetime.now(UTC),
                    )
                )
            await s.execute(
                text("UPDATE meeting SET status = 'completed' WHERE id = :mid"),
                {"mid": meeting_id},
            )
            await s.commit()

    monkeypatch.setattr(pipeline, "_build_asr_runner", lambda: _fake_runner)

    staging = tmp_path / "upload_test.partial"
    staging.write_bytes(b"\x00" * 1024)
    session = _make_session("m_p2", "u_p2", staging)

    async def _run_and_wait() -> None:
        await pipeline.run(session)
        task = runtime._inflight.get("m_p2")  # type: ignore[attr-defined]
        if task is not None:
            await task

    try:
        asyncio.run(_run_and_wait())

        async def _check() -> tuple[str, set[str]]:
            async with Session() as s:
                meeting_status = (
                    await s.execute(text("SELECT status FROM meeting WHERE id = 'm_p2'"))
                ).scalar_one()
                rows = (
                    (
                        await s.execute(
                            select(TranscriptChunk).where(TranscriptChunk.meeting_id == "m_p2")
                        )
                    )
                    .scalars()
                    .all()
                )
                speakers = {r.speaker for r in rows}
                return meeting_status, speakers

        status_value, speakers = asyncio.run(_check())
        assert status_value == "completed"
        assert speakers, "ASR runner must have written transcript chunks"
        for sp in speakers:
            assert sp.startswith("speaker_cluster_"), f"expected speaker_cluster_*; got {sp!r}"

        state = runtime.get_state("m_p2")
        assert state["state"] == "completed", state
    finally:
        asyncio.run(engine.dispose())


# ─── Error paths in pipeline.run ───────────────────────────────────────


def test_pipeline_transcode_failure_sets_error_state(_migrated_db_url, tmp_path, monkeypatch):
    """When ffmpeg fails the pipeline MUST set runtime state to failed with
    `offline_ingest.transcode_failed` and not write any recording row.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url), "u_tf", "m_tf"))

    async def _failing_transcode(*, staging_path, output_path):
        raise OfflineIngestTranscodeError("ffmpeg crashed in the test stub")

    monkeypatch.setattr(pipeline, "transcode_to_canonical_wav", _failing_transcode)

    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)
    monkeypatch.setattr(pipeline, "_get_offline_upload_dir", lambda: tmp_path.resolve())

    staging = tmp_path / "upload_test.partial"
    staging.write_bytes(b"\x00" * 1024)
    session = _make_session("m_tf", "u_tf", staging)

    try:
        asyncio.run(pipeline.run(session))

        state = runtime.get_state("m_tf")
        assert state["state"] == "failed"
        assert state["error_code"] == "offline_ingest.transcode_failed"

        async def _count() -> int:
            async with Session() as s:
                return (
                    await s.execute(
                        text("SELECT COUNT(*) FROM recording WHERE meeting_id = 'm_tf'")
                    )
                ).scalar_one()

        assert asyncio.run(_count()) == 0
    finally:
        asyncio.run(engine.dispose())


def test_pipeline_duration_too_long_sets_error_state(_migrated_db_url, tmp_path, monkeypatch):
    """A transcoded WAV that exceeds the duration budget rejects ingest
    with `offline_ingest.too_long` and no recording row.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url), "u_long", "m_long"))

    async def _fake_transcode(*, staging_path, output_path):
        # Write a "long" WAV by claiming a very low max in the next step;
        # the duration helper compares actual frames to the max.
        _write_tiny_wav(output_path, duration_seconds=2.0)
        staging_path.unlink(missing_ok=True)

    monkeypatch.setattr(pipeline, "transcode_to_canonical_wav", _fake_transcode)
    monkeypatch.setattr(pipeline, "_get_max_duration_seconds", lambda: 1)

    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)
    monkeypatch.setattr(pipeline, "_get_offline_upload_dir", lambda: tmp_path.resolve())

    staging = tmp_path / "upload_long.partial"
    staging.write_bytes(b"\x00" * 1024)
    session = _make_session("m_long", "u_long", staging)

    try:
        asyncio.run(pipeline.run(session))

        state = runtime.get_state("m_long")
        assert state["state"] == "failed"
        assert state["error_code"] == "offline_ingest.too_long"

        async def _count() -> int:
            async with Session() as s:
                return (
                    await s.execute(
                        text("SELECT COUNT(*) FROM recording WHERE meeting_id = 'm_long'")
                    )
                ).scalar_one()

        assert asyncio.run(_count()) == 0
    finally:
        asyncio.run(engine.dispose())


def test_pipeline_status_conflict_sets_error_state(_migrated_db_url, tmp_path, monkeypatch):
    """If the meeting is not in `scheduled` state when pipeline tries to
    transition, the MeetingStatusConflict path SHALL surface as
    `offline_ingest.conditions_not_met` via the runtime state.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url), "u_sc", "m_sc"))

    # Flip the meeting out of `scheduled` BEFORE pipeline.run executes.
    async def _flip():
        engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE meeting SET status = 'in_progress' WHERE id = 'm_sc'"))
        await engine.dispose()

    asyncio.run(_flip())

    async def _fake_transcode(*, staging_path, output_path):
        _write_tiny_wav(output_path, duration_seconds=1.0)
        staging_path.unlink(missing_ok=True)

    monkeypatch.setattr(pipeline, "transcode_to_canonical_wav", _fake_transcode)

    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)
    monkeypatch.setattr(pipeline, "_get_offline_upload_dir", lambda: tmp_path.resolve())

    staging = tmp_path / "upload_sc.partial"
    staging.write_bytes(b"\x00" * 1024)
    session = _make_session("m_sc", "u_sc", staging)

    try:
        asyncio.run(pipeline.run(session))

        state = runtime.get_state("m_sc")
        assert state["state"] == "failed"
        assert state["error_code"] == "offline_ingest.conditions_not_met"
    finally:
        asyncio.run(engine.dispose())


# ─── _build_asr_runner production code exercise ─────────────────────────


def test_build_asr_runner_chunks_transcribes_and_finalizes(_migrated_db_url, tmp_path, monkeypatch):
    """Exercise the production `_build_asr_runner` end-to-end with stubbed
    ASR + diarization providers. The runner SHALL: load the recording,
    chunk the WAV, write transcript_chunk rows, call
    `apply_speaker_attribution`, and transition the meeting to completed.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_seed_eligible_meeting(_async_url(_migrated_db_url), "u_run", "m_run"))

    # Seed a recording row + 25-second silent WAV on disk so `_load_wav_chunks`
    # produces multiple chunks (10-second windows).
    wav_path = tmp_path / "m_run_source.wav"
    _write_tiny_wav(wav_path, duration_seconds=25.0)
    bytes_on_disk = wav_path.stat().st_size

    engine = create_async_engine(_async_url(_migrated_db_url), future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)

    async def _seed_rec_and_progress() -> None:
        async with Session() as s:
            s.add(
                Recording(
                    id="rec_run",
                    meeting_id="m_run",
                    stream="me",
                    file_path=str(wav_path),
                    bytes=bytes_on_disk,
                    created_at=datetime.now(UTC),
                    source="offline",
                    started_at=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
                )
            )
            await s.execute(text("UPDATE meeting SET status = 'in_progress' WHERE id = 'm_run'"))
            await s.commit()
        # `_build_asr_runner` calls `runtime.get_progress(meeting_id)` which
        # returns a default-constructed ChunksProgress when no entry exists;
        # seed one explicitly so the assertion below sees the real counter.
        runtime._progress["m_run"] = runtime.ChunksProgress()

    asyncio.run(_seed_rec_and_progress())

    # Stub ASR provider: returns a deterministic transcript per chunk.
    # The asr `TranscriptChunk` carries text + start/end + provider_used + confidence.
    from meeting_playbook.asr.base import TranscriptChunk as _AsrTranscriptChunk

    class _StubProvider:
        name = "stub"

        async def warmup(self) -> None:
            return None

        async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
            now = datetime.now(UTC)
            return _AsrTranscriptChunk(
                text="stub speech",
                started_at=now,
                ended_at=now + timedelta(seconds=10),
                asr_provider_used="stub",
                confidence=0.9,
            )

    def _stub_factory(_provider_name):
        return (_StubProvider(), _StubProvider())

    monkeypatch.setattr("meeting_playbook.asr.factory.get_asr_providers_for_meeting", _stub_factory)

    # Stub diarization provider so SingleChannelStrategy returns 2 clusters.
    from meeting_playbook.speaker.diarization import DiarizationSegment

    class _StubDiarizationProvider:
        def diarize(self, wav_path):
            return [
                DiarizationSegment(start_ms=0, end_ms=12_000, cluster_id=1),
                DiarizationSegment(start_ms=12_000, end_ms=25_000, cluster_id=2),
            ]

    # `apply_speaker_attribution` uses `select_strategy(recordings, single_channel_provider=...)`,
    # but the production path doesn't pass a provider. We monkeypatch the
    # default factory so SingleChannelStrategy gets our stub instead of pyannote.
    monkeypatch.setattr(
        "meeting_playbook.speaker.strategy._default_diarization_provider",
        lambda: _StubDiarizationProvider(),
    )

    runner = pipeline._build_asr_runner()
    asyncio.run(runner("m_run"))

    async def _verify() -> tuple[str, set[str]]:
        async with Session() as s:
            meeting_status = (
                await s.execute(text("SELECT status FROM meeting WHERE id = 'm_run'"))
            ).scalar_one()
            rows = (
                (
                    await s.execute(
                        select(TranscriptChunk).where(TranscriptChunk.meeting_id == "m_run")
                    )
                )
                .scalars()
                .all()
            )
            speakers = {r.speaker for r in rows}
            return meeting_status, speakers

    status_value, speakers = asyncio.run(_verify())

    assert status_value == "completed"
    assert speakers, "runner must write transcript chunks"
    for sp in speakers:
        assert sp.startswith("speaker_cluster_"), (
            f"single-channel finalize must label every chunk as speaker_cluster_*; got {sp!r}"
        )
