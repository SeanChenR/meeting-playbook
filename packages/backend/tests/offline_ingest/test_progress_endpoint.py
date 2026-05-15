"""GET /api/meetings/{id}/offline_ingest_progress tests — slice-14 task 4.3.

Verifies the spec scenarios under
"GET /api/meetings/{id}/offline_ingest_progress reports pipeline state":

- ASR running → 200 with state + chunks_processed + chunks_total
- failed → 200 with state + error_code
- non-owner → 404 (no leak of meeting existence)
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.offline_ingest import runtime
from meeting_playbook.server import create_app


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


async def _truncate(db_url: str) -> None:
    engine = create_async_engine(db_url, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


async def _seed_user_and_meeting(db_url: str, *, user_id: str, meeting_id: str) -> None:
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
                    id, user_id, title, counterparty_display_name, me_display_name
                )
                VALUES (:mid, :uid, 'offline progress test', 'C', 'M')
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
    await engine.dispose()


def _build_client(db_url_sync: str, tmp_dir: Path) -> TestClient:
    import os

    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    os.environ["OFFLINE_UPLOAD_DIR"] = str(tmp_dir)

    db_url_async = _async_url(db_url_sync)
    engine = create_async_engine(db_url_async, future=True, poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    return TestClient(app)


def test_progress_reports_asr_running_with_counts(_migrated_db_url, tmp_path):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_user_and_meeting(_async_url(_migrated_db_url), user_id="u_p", meeting_id="m_p")
    )

    # Inject runtime state matching an in-progress ASR pass.
    runtime.reset()
    runtime._state["m_p"] = runtime.STATE_ASR_RUNNING
    progress = runtime.ChunksProgress(processed=12, total=20)
    runtime._progress["m_p"] = progress

    try:
        client = _build_client(_migrated_db_url, tmp_path)
        response = client.get(
            "/api/meetings/m_p/offline_ingest_progress",
            headers={"X-User-Id": "u_p"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body == {
            "state": "asr_running",
            "chunks_processed": 12,
            "chunks_total": 20,
        }
    finally:
        runtime.reset()


def test_progress_failed_state_carries_error_code(_migrated_db_url, tmp_path):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_user_and_meeting(_async_url(_migrated_db_url), user_id="u_f", meeting_id="m_f")
    )

    runtime.reset()
    runtime.set_error("m_f", "offline_ingest.transcode_failed")

    try:
        client = _build_client(_migrated_db_url, tmp_path)
        response = client.get(
            "/api/meetings/m_f/offline_ingest_progress",
            headers={"X-User-Id": "u_f"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["state"] == "failed"
        assert body["error_code"] == "offline_ingest.transcode_failed"
    finally:
        runtime.reset()


def test_progress_non_owner_gets_404(_migrated_db_url, tmp_path):
    """Per spec scenario `Non-owner gets 404` — no leak of meeting existence."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_user_and_meeting(_async_url(_migrated_db_url), user_id="u_owner", meeting_id="m_own")
    )
    asyncio.run(
        _seed_user_and_meeting(
            _async_url(_migrated_db_url), user_id="u_other", meeting_id="m_other"
        )
    )

    runtime.reset()
    runtime._state["m_own"] = runtime.STATE_COMPLETED
    runtime._progress["m_own"] = runtime.ChunksProgress(processed=5, total=5)

    try:
        client = _build_client(_migrated_db_url, tmp_path)
        response = client.get(
            "/api/meetings/m_own/offline_ingest_progress",
            headers={"X-User-Id": "u_other"},
        )

        assert response.status_code == 404, response.text
        # The response body should NOT leak progress data.
        body = response.json()
        assert "chunks_processed" not in body
    finally:
        runtime.reset()
