"""Offline-ingest end-to-end integration test — slice-14 task 6.1.

Two scenarios cover the spec acceptance:

1. **Full ingest flow** — drive a complete tus session via FastAPI
   TestClient (OPTIONS → POST creation → PATCH chunks with HEAD between
   → final PATCH completion). Once the pipeline completes, assert the
   resulting `recording` row carries `source = "offline"`, every
   `transcript_chunk` row wears a `speaker_cluster_*` label, at least
   two distinct cluster ids exist, and the meeting transitioned to
   `completed`.

2. **Resumable upload** — after the first PATCH, drop the upload and
   re-discover the session via HEAD. Use the returned `Upload-Offset`
   to continue from the middle byte. The server MUST remember progress
   and accept the second PATCH up to completion.

The real ASR + pyannote pipeline is tested elsewhere (slice-12 task 9.1
hits multi_speakers_zh.wav with real pyannote diarization; slice-11
covers ASR-provider correctness). Here we stub `_build_asr_runner` so
the E2E completes in ~1 second and stays deterministic.
"""

from __future__ import annotations

import asyncio
import base64
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.offline_ingest import pipeline, runtime
from meeting_playbook.server import create_app
from meeting_playbook.sessions.models import Recording, TranscriptChunk


_FIXTURE_WAV = Path(__file__).parent.parent / "speaker" / "fixtures" / "multi_speakers_zh.wav"


pytestmark = pytest.mark.skipif(
    not _FIXTURE_WAV.exists() or shutil.which("ffmpeg") is None,
    reason="slice-12 multi_speakers_zh.wav fixture or ffmpeg missing; e2e skipped",
)


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


def _encode_metadata(pairs: dict[str, str]) -> str:
    parts = []
    for key, value in pairs.items():
        b64 = base64.b64encode(value.encode("utf-8")).decode("ascii")
        parts.append(f"{key} {b64}")
    return ",".join(parts)


async def _truncate(db_url: str) -> None:
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


async def _seed_eligible_meeting(db_url: str, *, user_id: str, meeting_id: str) -> None:
    """Insert a user + a meeting whose scheduled_end_at is already past."""
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    base = datetime.now(UTC) - timedelta(hours=2)
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
                    id, user_id, title, counterparty_display_name, me_display_name,
                    status, scheduled_start_at, scheduled_end_at
                )
                VALUES (:mid, :uid, 'offline e2e', 'C', 'M', 'scheduled', :start, :end)
                """
            ),
            {
                "mid": meeting_id,
                "uid": user_id,
                "start": base,
                "end": base + timedelta(hours=1),
            },
        )
    await engine.dispose()


def _build_test_client(db_url_sync: str, tmp_upload_dir: Path) -> TestClient:
    import os

    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    os.environ["OFFLINE_UPLOAD_DIR"] = str(tmp_upload_dir)

    db_url_async = _async_url(db_url_sync)
    engine = create_async_engine(db_url_async, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    return TestClient(app), Session


async def _inline_spawn_ingest_task(
    meeting_id: str, *, runner, error_code_on_failure="offline_ingest.asr_failed"
) -> bool:
    """Replacement for `runtime.spawn_ingest_task` that awaits the runner
    inline. TestClient creates a fresh event loop per request and tears
    down any tasks it spawned; awaiting inline keeps the runner alive
    long enough to commit its DB writes before the request returns.
    """
    runtime._state[meeting_id] = runtime.STATE_ASR_RUNNING
    runtime._progress[meeting_id] = runtime.ChunksProgress()
    runtime._error_code.pop(meeting_id, None)
    try:
        await runner(meeting_id)
        runtime._state[meeting_id] = runtime.STATE_COMPLETED
    except Exception:
        runtime._state[meeting_id] = runtime.STATE_FAILED
        runtime._error_code[meeting_id] = error_code_on_failure
    return True


def _stub_asr_runner_factory(session_factory):
    """Build a stub `_build_asr_runner` that bypasses real ASR + diarization.

    The stub writes 4 transcript_chunk rows alternating between two
    speaker clusters and transitions the meeting to `completed`. This
    keeps the E2E deterministic + sub-second while still proving the
    pipeline → runtime → progress-endpoint flow end-to-end.
    """

    def _build():
        async def _runner(meeting_id: str) -> None:
            now = datetime.now(UTC)
            async with session_factory() as db:
                base = now - timedelta(minutes=30)
                for idx, cluster in enumerate([1, 2, 1, 2], start=1):
                    started = base + timedelta(seconds=idx * 10)
                    db.add(
                        TranscriptChunk(
                            id=f"tc_e2e_{idx}",
                            meeting_id=meeting_id,
                            speaker=f"speaker_cluster_{cluster}",
                            text=f"chunk {idx}",
                            started_at=started,
                            ended_at=started + timedelta(seconds=10),
                            asr_provider_used="stub",
                            confidence=0.9,
                            created_at=now,
                        )
                    )
                # Transition status via direct UPDATE (mirrors how the real
                # runner would call MeetingRepository.transition_status).
                await db.execute(
                    text("UPDATE meeting SET status = 'completed' WHERE id = :mid"),
                    {"mid": meeting_id},
                )
                await db.commit()

        return _runner

    return _build


def test_offline_ingest_full_flow_writes_offline_recording_and_completes(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Full tus session against the slice-12 multi-speakers WAV fixture.

    Verifies the spec acceptance for task 6.1:
    - `recording.source == "offline"`
    - every `transcript_chunk.speaker` matches `speaker_cluster_*`
    - at least 2 distinct cluster ids exist
    - `meeting.status == "completed"`
    """
    runtime.reset()
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_eligible_meeting(_async_url(_migrated_db_url), user_id="u_e2e", meeting_id="m_e2e")
    )

    client, Session = _build_test_client(_migrated_db_url, tmp_path)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)
    monkeypatch.setattr(pipeline, "_get_offline_upload_dir", lambda: tmp_path.resolve())
    monkeypatch.setattr(pipeline, "_build_asr_runner", _stub_asr_runner_factory(Session))
    monkeypatch.setattr(runtime, "spawn_ingest_task", _inline_spawn_ingest_task)

    # Step 1: OPTIONS — discover tus capabilities.
    options_resp = client.options(
        "/api/meetings/m_e2e/recordings/offline_upload",
        headers={"X-User-Id": "u_e2e"},
    )
    assert options_resp.status_code == 204
    assert options_resp.headers["Tus-Extension"] == "creation,termination"

    # Step 2: POST creation — open an upload session for the full WAV size.
    wav_bytes = _FIXTURE_WAV.read_bytes()
    upload_length = len(wav_bytes)
    metadata = _encode_metadata(
        {
            "filename": "multi_speakers_zh.wav",
            "mimetype": "audio/wav",
            "actual_started_at": (datetime.now(UTC) - timedelta(hours=1, minutes=30)).isoformat(),
        }
    )
    post_resp = client.post(
        "/api/meetings/m_e2e/recordings/offline_upload",
        headers={
            "X-User-Id": "u_e2e",
            "Tus-Resumable": "1.0.0",
            "Upload-Length": str(upload_length),
            "Upload-Metadata": metadata,
        },
    )
    assert post_resp.status_code == 201, post_resp.text
    upload_id = post_resp.headers["Location"].rsplit("/", 1)[-1]

    # Step 3: PATCH first half.
    half = upload_length // 2
    patch1 = client.patch(
        f"/api/meetings/m_e2e/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_e2e",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=wav_bytes[:half],
    )
    assert patch1.status_code == 204
    assert patch1.headers["Upload-Offset"] == str(half)

    # Step 3.5: HEAD — verify offset matches.
    head_resp = client.head(
        f"/api/meetings/m_e2e/recordings/offline_upload/{upload_id}",
        headers={"X-User-Id": "u_e2e", "Tus-Resumable": "1.0.0"},
    )
    assert head_resp.status_code == 200
    assert head_resp.headers["Upload-Offset"] == str(half)

    # Step 4: PATCH the second half — triggers downstream pipeline.
    patch2 = client.patch(
        f"/api/meetings/m_e2e/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_e2e",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": str(half),
            "Content-Type": "application/offset+octet-stream",
        },
        content=wav_bytes[half:],
    )
    assert patch2.status_code == 204
    assert patch2.headers["Upload-Offset"] == str(upload_length)

    # Step 5: Wait for the background ASR task to finish.
    async def _wait_for_completion() -> None:
        for _ in range(50):
            state = runtime.get_state("m_e2e")
            if state["state"] in ("completed", "failed"):
                return
            await asyncio.sleep(0.1)

    asyncio.run(_wait_for_completion())

    # Step 6: Verify DB state.
    async def _check() -> tuple[str, str, set[str]]:
        async with Session() as s:
            meeting_status = (
                await s.execute(text("SELECT status FROM meeting WHERE id = 'm_e2e'"))
            ).scalar_one()
            recording = (
                await s.execute(select(Recording).where(Recording.meeting_id == "m_e2e"))
            ).scalar_one()
            rows = (
                (
                    await s.execute(
                        select(TranscriptChunk).where(TranscriptChunk.meeting_id == "m_e2e")
                    )
                )
                .scalars()
                .all()
            )
            speakers = {r.speaker for r in rows}
            return meeting_status, recording.source, speakers

    status_value, source, speakers = asyncio.run(_check())

    assert status_value == "completed"
    assert source == "offline"
    assert speakers, "ASR runner must have written transcript chunks"
    for sp in speakers:
        assert sp.startswith("speaker_cluster_"), f"expected speaker_cluster_*; got {sp!r}"
    cluster_ids = {sp for sp in speakers if sp != "speaker_cluster_unknown"}
    assert len(cluster_ids) >= 2, f"expected ≥2 distinct cluster labels; got {sorted(cluster_ids)}"


def test_offline_ingest_resume_via_head_and_continued_patch(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Resume scenario: drop the upload after the first PATCH and re-attach
    via HEAD + a second PATCH starting from the returned offset.
    """
    runtime.reset()
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_eligible_meeting(_async_url(_migrated_db_url), user_id="u_res", meeting_id="m_res")
    )

    client, Session = _build_test_client(_migrated_db_url, tmp_path)
    monkeypatch.setattr(pipeline, "_get_session_factory", lambda: Session)
    monkeypatch.setattr(pipeline, "_get_offline_upload_dir", lambda: tmp_path.resolve())
    monkeypatch.setattr(pipeline, "_build_asr_runner", _stub_asr_runner_factory(Session))
    monkeypatch.setattr(runtime, "spawn_ingest_task", _inline_spawn_ingest_task)

    wav_bytes = _FIXTURE_WAV.read_bytes()
    upload_length = len(wav_bytes)
    metadata = _encode_metadata(
        {
            "filename": "multi_speakers_zh.wav",
            "mimetype": "audio/wav",
            "actual_started_at": (datetime.now(UTC) - timedelta(hours=1, minutes=30)).isoformat(),
        }
    )
    post_resp = client.post(
        "/api/meetings/m_res/recordings/offline_upload",
        headers={
            "X-User-Id": "u_res",
            "Tus-Resumable": "1.0.0",
            "Upload-Length": str(upload_length),
            "Upload-Metadata": metadata,
        },
    )
    assert post_resp.status_code == 201
    upload_id = post_resp.headers["Location"].rsplit("/", 1)[-1]

    # First PATCH — only a quarter of the bytes.
    quarter = upload_length // 4
    patch1 = client.patch(
        f"/api/meetings/m_res/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_res",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": "0",
            "Content-Type": "application/offset+octet-stream",
        },
        content=wav_bytes[:quarter],
    )
    assert patch1.status_code == 204

    # Simulate client reconnect — discover offset via HEAD.
    head_resp = client.head(
        f"/api/meetings/m_res/recordings/offline_upload/{upload_id}",
        headers={"X-User-Id": "u_res", "Tus-Resumable": "1.0.0"},
    )
    assert head_resp.status_code == 200
    resume_offset = int(head_resp.headers["Upload-Offset"])
    assert resume_offset == quarter, "server must remember the partial offset"

    # Continue from the resume offset all the way to the end.
    patch_remainder = client.patch(
        f"/api/meetings/m_res/recordings/offline_upload/{upload_id}",
        headers={
            "X-User-Id": "u_res",
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": str(resume_offset),
            "Content-Type": "application/offset+octet-stream",
        },
        content=wav_bytes[resume_offset:],
    )
    assert patch_remainder.status_code == 204
    assert patch_remainder.headers["Upload-Offset"] == str(upload_length)

    # Wait for completion.
    async def _wait() -> None:
        for _ in range(50):
            state = runtime.get_state("m_res")
            if state["state"] in ("completed", "failed"):
                return
            await asyncio.sleep(0.1)

    asyncio.run(_wait())

    async def _read_status() -> str:
        async with Session() as s:
            return (
                await s.execute(text("SELECT status FROM meeting WHERE id = 'm_res'"))
            ).scalar_one()

    assert asyncio.run(_read_status()) == "completed"
