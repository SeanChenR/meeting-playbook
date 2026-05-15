"""GET /api/meetings/{id} runtime flag tests — slice-11 task 3.3.

Per spec meeting-management ADDED requirement
"GET /api/meetings/{id} returns recordings_available and rerun_asr_pending
derived fields" — 4 scenarios:

  (a) Completed meeting with non-deleted recordings →
      recordings_available=true, rerun_asr_pending=false.
  (b) Completed meeting whose recordings are all deleted →
      recordings_available=false.
  (c) Scheduled meeting with no recording rows yet →
      recordings_available=false, rerun_asr_pending=false.
  (d) Active re-run flips rerun_asr_pending true; clears after completion.
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

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.rerun import runtime as rerun_runtime
from meeting_playbook.server import create_app


@pytest.fixture(autouse=True)
def _reset_rerun_registry():
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client


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
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, status
                )
                VALUES (:mid, :uid, 'T', 'C', 'M', :s)
                """
            ),
            {"mid": meeting_id, "uid": user_id, "s": status_value},
        )


async def _seed_recording(
    engine: AsyncEngine,
    *,
    meeting_id: str,
    stream: str,
    file_path: Path,
    deleted: bool = False,
    source: str = "live",
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes,
                    created_at, started_at, deleted_at, source
                )
                VALUES (
                    'r_' || :mid || '_' || :stream, :mid, :stream, :fp, 100,
                    now(), now(),
                    CASE WHEN :del THEN now() ELSE NULL END,
                    :source
                )
                """
            ),
            {
                "mid": meeting_id,
                "stream": stream,
                "fp": str(file_path),
                "del": deleted,
                "source": source,
            },
        )


# ─── Scenario (a) — completed + 2 live recordings ──────────────────


@pytest.mark.asyncio
async def test_completed_meeting_with_recordings_reports_available_true(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    await _seed_user(migrated_engine, "u_avail")
    await _seed_meeting(migrated_engine, user_id="u_avail", meeting_id="m_avail")
    me_wav = tmp_path / "me.wav"
    cp_wav = tmp_path / "cp.wav"
    me_wav.write_bytes(b"\x00")
    cp_wav.write_bytes(b"\x00")
    await _seed_recording(migrated_engine, meeting_id="m_avail", stream="me", file_path=me_wav)
    await _seed_recording(
        migrated_engine, meeting_id="m_avail", stream="counterparty", file_path=cp_wav
    )

    resp = await api_client.get("/api/meetings/m_avail", headers={"X-User-Id": "u_avail"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recordings_available"] is True
    assert body["rerun_asr_pending"] is False


# ─── Scenario (b) — all recordings soft-deleted ────────────────────


@pytest.mark.asyncio
async def test_meeting_with_all_deleted_recordings_reports_available_false(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    await _seed_user(migrated_engine, "u_del")
    await _seed_meeting(migrated_engine, user_id="u_del", meeting_id="m_del")
    me_wav = tmp_path / "me.wav"
    cp_wav = tmp_path / "cp.wav"
    me_wav.write_bytes(b"\x00")
    cp_wav.write_bytes(b"\x00")
    await _seed_recording(
        migrated_engine, meeting_id="m_del", stream="me", file_path=me_wav, deleted=True
    )
    await _seed_recording(
        migrated_engine,
        meeting_id="m_del",
        stream="counterparty",
        file_path=cp_wav,
        deleted=True,
    )

    resp = await api_client.get("/api/meetings/m_del", headers={"X-User-Id": "u_del"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recordings_available"] is False
    assert body["rerun_asr_pending"] is False


# ─── Scenario (c) — scheduled, no recordings ───────────────────────


@pytest.mark.asyncio
async def test_scheduled_meeting_with_no_recordings_reports_both_false(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_sched")
    await _seed_meeting(
        migrated_engine,
        user_id="u_sched",
        meeting_id="m_sched",
        status_value="scheduled",
    )

    resp = await api_client.get("/api/meetings/m_sched", headers={"X-User-Id": "u_sched"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recordings_available"] is False
    assert body["rerun_asr_pending"] is False


# ─── Scenario (d) — pending flips true → false on completion ───────


@pytest.mark.asyncio
async def test_rerun_pending_flips_true_then_false(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_pend")
    await _seed_meeting(migrated_engine, user_id="u_pend", meeting_id="m_pend")

    # Simulate an in-flight task by populating the registries directly.
    held = asyncio.Event()

    async def _hang() -> None:
        await held.wait()

    rerun_runtime._inflight["m_pend"] = asyncio.create_task(_hang())
    rerun_runtime._progress["m_pend"] = rerun_runtime.ChunksProgress()

    try:
        # While the task is in-flight: pending should be True.
        resp = await api_client.get("/api/meetings/m_pend", headers={"X-User-Id": "u_pend"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["rerun_asr_pending"] is True
    finally:
        held.set()
        await rerun_runtime._inflight["m_pend"]
        # Mirror the real runtime's `finally`: pop the registry once the task
        # is done. (In production `_run` does this; our stub didn't.)
        rerun_runtime._inflight.pop("m_pend", None)
        rerun_runtime._progress.pop("m_pend", None)

    # After the task completes + registry cleared: pending should be False.
    resp_after = await api_client.get("/api/meetings/m_pend", headers={"X-User-Id": "u_pend"})
    assert resp_after.status_code == 200, resp_after.text
    body_after = resp_after.json()
    assert body_after["rerun_asr_pending"] is False


# ─── Scenario (e, slice-14) — offline-only recording counts as available ───


@pytest.mark.asyncio
async def test_meeting_with_only_offline_recording_reports_available_true(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Slice-14 regression: a `completed` meeting whose only recording is
    `source = 'offline'` SHALL report `recordings_available: true`. The
    derived field MUST NOT filter on `source`.
    """
    await _seed_user(migrated_engine, "u_off_avail")
    await _seed_meeting(migrated_engine, user_id="u_off_avail", meeting_id="m_off_avail")
    me_wav = tmp_path / "offline.wav"
    me_wav.write_bytes(b"\x00")
    await _seed_recording(
        migrated_engine,
        meeting_id="m_off_avail",
        stream="me",
        file_path=me_wav,
        source="offline",
    )

    resp = await api_client.get("/api/meetings/m_off_avail", headers={"X-User-Id": "u_off_avail"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recordings_available"] is True
    assert body["rerun_asr_pending"] is False
