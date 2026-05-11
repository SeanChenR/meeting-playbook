"""Re-run REST endpoint tests — slice-11 tasks 5.2 + 5.3.

Per spec asr-provider-selection ADDED requirements
"POST /api/meetings/{id}/rerun_asr triggers atomic transcript replacement"
+ "GET /api/meetings/{id}/rerun_asr_status returns polling-friendly progress shape".

POST status code matrix:
  202 / 409 / 410 / 422 / 404 — each verified with the standard envelope
  `{error_code, message}` shape.

GET shape:
  always `{status: "idle"|"pending", chunks_processed, chunks_total}`;
  ownership 404 still applies.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_session_factory_dependency,
)
from meeting_playbook.rerun import runtime as rerun_runtime
from meeting_playbook.server import create_app

# ─── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_registries():
    rerun_runtime._inflight.clear()
    rerun_runtime._progress.clear()
    yield
    rerun_runtime._inflight.clear()
    rerun_runtime._progress.clear()


@pytest_asyncio.fixture
async def api_client(migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    app.dependency_overrides[get_session_factory_dependency] = lambda: Session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client


# ─── Seed helpers ───────────────────────────────────────────────────


async def _seed_user(engine: AsyncEngine, user_id: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:id, :id, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )


async def _seed_meeting(
    engine: AsyncEngine,
    *,
    user_id: str,
    meeting_id: str,
    status_value: str = "completed",
    asr_provider: str = "whisper",
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, status, asr_provider
                )
                VALUES (:mid, :uid, 'T', 'C', 'M', :s, :p)
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status
                """
            ),
            {"mid": meeting_id, "uid": user_id, "s": status_value, "p": asr_provider},
        )


async def _seed_recording(
    engine: AsyncEngine,
    *,
    meeting_id: str,
    file_path: Path,
    deleted: bool = False,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes, created_at, deleted_at
                )
                VALUES (
                    'r_' || :mid || '_me', :mid, 'me', :fp, 100, now(),
                    CASE WHEN :del THEN now() ELSE NULL END
                )
                """
            ),
            {"mid": meeting_id, "fp": str(file_path), "del": deleted},
        )


# ─── POST /rerun_asr — 5 status cases ──────────────────────────────


@pytest.mark.asyncio
async def test_post_rerun_returns_202_when_task_spawns(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path, monkeypatch
):
    """Spec: 202 + {status: pending} when validation passes + spawn returns True."""
    await _seed_user(migrated_engine, "u_ok")
    await _seed_meeting(migrated_engine, user_id="u_ok", meeting_id="m_ok")
    wav = tmp_path / "m_ok.wav"
    wav.write_bytes(b"\x00" * 100)
    await _seed_recording(migrated_engine, meeting_id="m_ok", file_path=wav)

    async def _fake_spawn(*args, **kwargs):
        return True

    monkeypatch.setattr(rerun_runtime, "spawn_rerun_task", _fake_spawn)

    resp = await api_client.post("/api/meetings/m_ok/rerun_asr", headers={"X-User-Id": "u_ok"})
    assert resp.status_code == 202, resp.text
    assert resp.json() == {"status": "pending"}


@pytest.mark.asyncio
async def test_post_rerun_returns_409_when_already_in_flight(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path, monkeypatch
):
    """Spec: 409 rerun.busy when spawn returns False."""
    await _seed_user(migrated_engine, "u_busy")
    await _seed_meeting(migrated_engine, user_id="u_busy", meeting_id="m_busy")
    wav = tmp_path / "m_busy.wav"
    wav.write_bytes(b"\x00" * 100)
    await _seed_recording(migrated_engine, meeting_id="m_busy", file_path=wav)

    async def _fake_spawn(*args, **kwargs):
        return False  # simulates an existing in-flight task

    monkeypatch.setattr(rerun_runtime, "spawn_rerun_task", _fake_spawn)

    resp = await api_client.post("/api/meetings/m_busy/rerun_asr", headers={"X-User-Id": "u_busy"})
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["error_code"] == "rerun.busy"
    assert body.get("message")


@pytest.mark.asyncio
async def test_post_rerun_returns_410_when_recordings_expired(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Spec: 410 rerun.recording_expired when no recording has deleted_at IS NULL."""
    await _seed_user(migrated_engine, "u_expired")
    await _seed_meeting(migrated_engine, user_id="u_expired", meeting_id="m_expired")
    wav = tmp_path / "m_expired.wav"
    wav.write_bytes(b"\x00" * 100)
    await _seed_recording(migrated_engine, meeting_id="m_expired", file_path=wav, deleted=True)

    resp = await api_client.post(
        "/api/meetings/m_expired/rerun_asr", headers={"X-User-Id": "u_expired"}
    )
    assert resp.status_code == 410, resp.text
    body = resp.json()
    assert body["error_code"] == "rerun.recording_expired"


@pytest.mark.asyncio
async def test_post_rerun_returns_422_when_meeting_not_completed(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Spec: 422 rerun.not_completed when meeting.status != completed."""
    await _seed_user(migrated_engine, "u_sched")
    await _seed_meeting(
        migrated_engine,
        user_id="u_sched",
        meeting_id="m_sched",
        status_value="scheduled",
    )
    wav = tmp_path / "m_sched.wav"
    wav.write_bytes(b"\x00" * 100)
    await _seed_recording(migrated_engine, meeting_id="m_sched", file_path=wav)

    resp = await api_client.post(
        "/api/meetings/m_sched/rerun_asr", headers={"X-User-Id": "u_sched"}
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error_code"] == "rerun.not_completed"


@pytest.mark.asyncio
async def test_post_rerun_returns_404_for_other_users_meeting(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Spec: 404 meeting.not_found for cross-user request (no leak)."""
    await _seed_user(migrated_engine, "u_owner")
    await _seed_user(migrated_engine, "u_attacker")
    await _seed_meeting(migrated_engine, user_id="u_owner", meeting_id="m_owned")
    wav = tmp_path / "m_owned.wav"
    wav.write_bytes(b"\x00" * 100)
    await _seed_recording(migrated_engine, meeting_id="m_owned", file_path=wav)

    resp = await api_client.post(
        "/api/meetings/m_owned/rerun_asr", headers={"X-User-Id": "u_attacker"}
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["error_code"] == "meeting.not_found"


# ─── GET /rerun_asr_status — 3 cases ───────────────────────────────


@pytest.mark.asyncio
async def test_get_status_returns_idle_for_meeting_with_no_task(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Spec: idle shape + 200 when no task ever spawned."""
    await _seed_user(migrated_engine, "u_idle")
    await _seed_meeting(migrated_engine, user_id="u_idle", meeting_id="m_idle")

    resp = await api_client.get(
        "/api/meetings/m_idle/rerun_asr_status", headers={"X-User-Id": "u_idle"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "idle", "chunks_processed": 0, "chunks_total": 0}


@pytest.mark.asyncio
async def test_get_status_returns_pending_with_progress_during_run(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Spec: pending shape with chunks_processed / chunks_total counters."""
    await _seed_user(migrated_engine, "u_pending")
    await _seed_meeting(migrated_engine, user_id="u_pending", meeting_id="m_pending")

    # Manually populate the registries to simulate an in-flight task
    # without spawning real work.
    held = asyncio.Event()

    async def _hang() -> None:
        await held.wait()

    rerun_runtime._inflight["m_pending"] = asyncio.create_task(_hang())
    rerun_runtime._progress["m_pending"] = rerun_runtime.ChunksProgress(processed=2, total=6)

    try:
        resp = await api_client.get(
            "/api/meetings/m_pending/rerun_asr_status",
            headers={"X-User-Id": "u_pending"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {
            "status": "pending",
            "chunks_processed": 2,
            "chunks_total": 6,
        }
    finally:
        held.set()
        await rerun_runtime._inflight["m_pending"]


@pytest.mark.asyncio
async def test_get_status_returns_404_for_other_users_meeting(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Spec: 404 meeting.not_found for cross-user request."""
    await _seed_user(migrated_engine, "u_status_owner")
    await _seed_user(migrated_engine, "u_status_attacker")
    await _seed_meeting(migrated_engine, user_id="u_status_owner", meeting_id="m_status_owned")

    resp = await api_client.get(
        "/api/meetings/m_status_owned/rerun_asr_status",
        headers={"X-User-Id": "u_status_attacker"},
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["error_code"] == "meeting.not_found"
