"""Slice-10 summary router — POST + GET integration tests.

Per spec meeting-summary ADDED requirement scenarios for both endpoints.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app
from meeting_playbook.summarization import runtime


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


async def _setup_meeting(db_url: str, *, user_id: str, meeting_id: str):
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
        await s.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
                VALUES (:mid, :uid, 'T', 'C', 'M')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
        await s.commit()
    await engine.dispose()


async def _seed_summary_row(db_url: str, *, meeting_id: str, markdown: str = "# md"):
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        from meeting_playbook.summarization.repository import SummaryRepository

        await SummaryRepository(s).upsert(meeting_id=meeting_id, markdown=markdown)
    await engine.dispose()


async def _truncate(db_url: str):
    engine = create_async_engine(db_url, future=True)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "summary" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "chat_message" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "playbook" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


def _build_client(db_url_sync: str) -> TestClient:
    db_url_async = _async_url(db_url_sync)
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_inflight():
    runtime._inflight.clear()
    yield
    runtime._inflight.clear()


# ─── POST /summary tests ─────────────────────────────────────────────────


def test_post_summary_owner_idle_returns_202_pending(_migrated_db_url, monkeypatch):
    """Slice-10 4.1: idle meeting → POST returns 202 + pending; spawn was called."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_post"))

    # Track spawn invocation. We can't keep a real `asyncio.sleep` task
    # alive across the TestClient call (its event loop shuts down between
    # sync requests and would cancel anything pending), so verify the
    # router-level wiring (got the right meeting_id, returned 202) rather
    # than asserting on the post-call registry state.
    called: list[str] = []

    async def _stub_spawn(meeting_id, **_kw):
        called.append(meeting_id)
        return True

    monkeypatch.setattr(runtime, "spawn_summary_task", _stub_spawn)

    client = _build_client(_migrated_db_url)
    r = client.post("/api/meetings/m_post/summary", headers={"X-User-Id": "u_a"})

    assert r.status_code == 202, r.text
    assert r.json() == {"status": "pending"}
    assert called == ["m_post"], "spawn_summary_task should be called once with the meeting id"


def test_post_summary_busy_returns_409_summary_busy(_migrated_db_url):
    """Slice-10 4.2: in-flight task → POST returns 409 summary.busy."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_busy"))

    # Pre-populate the registry with a sleeping task.
    async def _hang():
        await asyncio.sleep(5)

    loop = asyncio.new_event_loop()
    try:
        task = loop.create_task(_hang())
        runtime._inflight["m_busy"] = task
        client = _build_client(_migrated_db_url)
        r = client.post("/api/meetings/m_busy/summary", headers={"X-User-Id": "u_a"})
    finally:
        task.cancel()
        loop.close()

    assert r.status_code == 409, r.text
    assert r.json()["error_code"] == "summary.busy"
    # Only the original task remains.
    assert len(runtime._inflight) == 1


def test_post_summary_non_owner_returns_404_meeting_not_found(_migrated_db_url):
    """Slice-10 4.3: non-owner POST → 404 meeting.not_found."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _setup_meeting(_async_url(_migrated_db_url), user_id="u_owner", meeting_id="m_priv")
    )

    client = _build_client(_migrated_db_url)
    r = client.post("/api/meetings/m_priv/summary", headers={"X-User-Id": "u_attacker"})

    assert r.status_code == 404
    assert r.json()["error_code"] == "meeting.not_found"


def test_post_summary_missing_x_user_id_returns_401(_migrated_db_url):
    """Slice-10 4.4: missing X-User-Id → 401 auth.gateway_bypass."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_x"))

    client = _build_client(_migrated_db_url)
    r = client.post("/api/meetings/m_x/summary")
    assert r.status_code == 401
    assert r.json()["error_code"] == "auth.gateway_bypass"


# ─── GET /summary tests ──────────────────────────────────────────────────


def test_get_summary_returns_persisted_row_with_is_stale_false_for_fresh_summary(
    _migrated_db_url,
):
    """Slice-10 4.5: row exists + nothing newer → 200 + Summary + is_stale=False."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_get"))
    asyncio.run(_seed_summary_row(_async_url(_migrated_db_url), meeting_id="m_get"))

    client = _build_client(_migrated_db_url)
    r = client.get("/api/meetings/m_get/summary", headers={"X-User-Id": "u_a"})
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"id", "meeting_id", "markdown", "generated_at", "is_stale"}
    assert body["meeting_id"] == "m_get"
    assert body["is_stale"] is False


def test_get_summary_returns_pending_when_in_flight_no_row(_migrated_db_url):
    """Slice-10 4.6: no row + in-flight → 200 + `{status: pending}`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_pen"))

    async def _hang():
        await asyncio.sleep(5)

    loop = asyncio.new_event_loop()
    try:
        task = loop.create_task(_hang())
        runtime._inflight["m_pen"] = task
        client = _build_client(_migrated_db_url)
        r = client.get("/api/meetings/m_pen/summary", headers={"X-User-Id": "u_a"})
    finally:
        task.cancel()
        loop.close()

    assert r.status_code == 200
    assert r.json() == {"status": "pending", "generated_at": None}


def test_get_summary_returns_404_summary_not_found_when_no_row_no_pending(
    _migrated_db_url,
):
    """Slice-10 4.7: no row + not in-flight → 404 summary.not_found."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_nope"))

    client = _build_client(_migrated_db_url)
    r = client.get("/api/meetings/m_nope/summary", headers={"X-User-Id": "u_a"})
    assert r.status_code == 404
    assert r.json()["error_code"] == "summary.not_found"


def test_get_summary_returns_is_stale_true_when_transcript_chunk_newer(_migrated_db_url):
    """Slice-10 4.8: transcript_chunk newer than summary → is_stale=True in GET response."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_st"))
    asyncio.run(_seed_summary_row(_async_url(_migrated_db_url), meeting_id="m_st"))

    # Insert a transcript_chunk with started_at + created_at strictly later.
    async def _newer_chunk():
        engine = create_async_engine(_async_url(_migrated_db_url), future=True)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        future = datetime.now(UTC) + timedelta(seconds=30)
        async with Session() as s:
            await s.execute(
                text(
                    """
                    INSERT INTO transcript_chunk (id, meeting_id, speaker, text, started_at,
                                                  ended_at, asr_provider_used, created_at)
                    VALUES ('tc_x', 'm_st', 'me', 'x', :ts, :ts2, 'whisper', :ts)
                    """
                ),
                {"ts": future, "ts2": future + timedelta(seconds=10)},
            )
            await s.commit()
        await engine.dispose()

    asyncio.run(_newer_chunk())

    client = _build_client(_migrated_db_url)
    r = client.get("/api/meetings/m_st/summary", headers={"X-User-Id": "u_a"})
    assert r.status_code == 200
    assert r.json()["is_stale"] is True


def test_get_summary_non_owner_returns_404_meeting_not_found(_migrated_db_url):
    """Slice-10: non-owner GET → 404 meeting.not_found (existence not leaked)."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_owner", meeting_id="m_pr"))
    asyncio.run(_seed_summary_row(_async_url(_migrated_db_url), meeting_id="m_pr"))

    client = _build_client(_migrated_db_url)
    r = client.get("/api/meetings/m_pr/summary", headers={"X-User-Id": "u_attacker"})
    assert r.status_code == 404
    assert r.json()["error_code"] == "meeting.not_found"
