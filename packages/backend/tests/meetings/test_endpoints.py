"""Meeting REST endpoint tests — POST/GET list/GET id/DELETE four-piece set.

Per spec (slice-03-meeting-crud, meeting-management/spec.md):
- Requirement: Meeting belongs to exactly one user with strict ownership isolation
- Cross-user reads/deletes return 404 with no existence leak
- Empty list returns 200 with empty array (never 404)

Per design.md:
- All endpoints derive the actor from the gateway-injected `X-User-Id` header.
- DB session is provided via a FastAPI dependency that tests override.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


@pytest_asyncio.fixture
async def api_client(migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """Yield an httpx AsyncClient bound to a FastAPI app with the meeting router.

    The DB session dependency is overridden to use the test engine.
    """
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
                VALUES (:id, :name, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": user_id, "name": user_id, "email": f"{user_id}@example.com"},
        )


@pytest.mark.asyncio
async def test_post_meeting_returns_201_with_body(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Successful create persists all three fields."""
    await _seed_user(migrated_engine, "user_post")

    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_post"},
        json={
            "title": "Q3 review",
            "counterparty_display_name": "林經理",
            "me_display_name": "Sean",
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Q3 review"
    assert body["counterparty_display_name"] == "林經理"
    assert body["me_display_name"] == "Sean"
    assert body["status"] == "scheduled"
    # Slice-11 (migration 0008): default flipped from "whisper" → "qwen3".
    assert body["asr_provider"] == "qwen3"
    assert body["calendar_event_id"] is None
    assert body["user_id"] == "user_post"
    assert body["id"].startswith("m_")


@pytest.mark.asyncio
async def test_list_returns_only_owners_meetings(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: List returns only meetings owned by the requesting user."""
    await _seed_user(migrated_engine, "user_a")
    await _seed_user(migrated_engine, "user_b")

    for title in ("A1", "A2"):
        resp = await api_client.post(
            "/api/meetings",
            headers={"X-User-Id": "user_a"},
            json={"title": title, "counterparty_display_name": "C", "me_display_name": "M"},
        )
        assert resp.status_code == 201
    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_b"},
        json={"title": "B-only", "counterparty_display_name": "C", "me_display_name": "M"},
    )
    assert resp.status_code == 201

    resp = await api_client.get("/api/meetings", headers={"X-User-Id": "user_a"})
    assert resp.status_code == 200
    titles = [m["title"] for m in resp.json()]
    assert "B-only" not in titles
    assert set(titles) == {"A1", "A2"}


@pytest.mark.asyncio
async def test_empty_list_returns_200_with_empty_array(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Empty list returns 200 with empty array."""
    await _seed_user(migrated_engine, "user_empty")
    resp = await api_client.get("/api/meetings", headers={"X-User-Id": "user_empty"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_other_users_meeting_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Reading another user's meeting returns 404 and body MUST NOT reveal existence."""
    await _seed_user(migrated_engine, "user_a")
    await _seed_user(migrated_engine, "user_b")

    create = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_b"},
        json={
            "title": "B's secret",
            "counterparty_display_name": "C",
            "me_display_name": "M",
        },
    )
    meeting_id = create.json()["id"]

    resp = await api_client.get(
        f"/api/meetings/{meeting_id}",
        headers={"X-User-Id": "user_a"},
    )
    assert resp.status_code == 404
    body = resp.json()
    # Error envelope must not contain user B's data, the meeting id beyond the
    # url echo, or any "owned by another user" hint.
    flat = str(body).lower()
    assert "secret" not in flat
    assert "user_b" not in flat


@pytest.mark.asyncio
async def test_delete_other_users_meeting_returns_404_and_keeps_row(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Deleting another user's meeting returns 404 and meeting stays."""
    await _seed_user(migrated_engine, "user_a")
    await _seed_user(migrated_engine, "user_b")

    create = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_b"},
        json={"title": "Protected", "counterparty_display_name": "C", "me_display_name": "M"},
    )
    meeting_id = create.json()["id"]

    resp = await api_client.delete(
        f"/api/meetings/{meeting_id}",
        headers={"X-User-Id": "user_a"},
    )
    assert resp.status_code == 404

    # Owner can still see it.
    follow = await api_client.get(
        f"/api/meetings/{meeting_id}",
        headers={"X-User-Id": "user_b"},
    )
    assert follow.status_code == 200
    assert follow.json()["title"] == "Protected"


@pytest.mark.asyncio
async def test_delete_own_meeting_returns_204_and_removes_row(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Owner-side delete actually removes the meeting."""
    await _seed_user(migrated_engine, "user_o")
    create = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_o"},
        json={"title": "X", "counterparty_display_name": "C", "me_display_name": "M"},
    )
    mid = create.json()["id"]

    resp = await api_client.delete(f"/api/meetings/{mid}", headers={"X-User-Id": "user_o"})
    assert resp.status_code == 204

    follow = await api_client.get(f"/api/meetings/{mid}", headers={"X-User-Id": "user_o"})
    assert follow.status_code == 404


@pytest.mark.asyncio
async def test_request_without_x_user_id_is_rejected(api_client: AsyncClient):
    """Gateway-bypass attempt: without X-User-Id, requests must fail fast."""
    resp = await api_client.get("/api/meetings")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "auth.gateway_bypass"


@pytest.mark.asyncio
async def test_create_ignores_client_supplied_status(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Client-supplied status on create is ignored."""
    await _seed_user(migrated_engine, "user_status")

    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_status"},
        json={
            "title": "T",
            "counterparty_display_name": "C",
            "me_display_name": "M",
            "status": "completed",  # client lies; backend MUST ignore.
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "scheduled"


@pytest.mark.asyncio
async def test_create_returns_null_calendar_event_id(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: New meeting has null calendar_event_id."""
    await _seed_user(migrated_engine, "user_cal")

    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_cal"},
        json={"title": "T", "counterparty_display_name": "C", "me_display_name": "M"},
    )
    assert resp.status_code == 201
    assert resp.json()["calendar_event_id"] is None


@pytest.mark.asyncio
async def test_get_returns_persisted_asr_provider_qwen3(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: GET returns the persisted ASR provider — defaults to qwen3 (slice-11)."""
    await _seed_user(migrated_engine, "user_asr")

    create = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_asr"},
        json={"title": "T", "counterparty_display_name": "C", "me_display_name": "M"},
    )
    mid = create.json()["id"]

    resp = await api_client.get(f"/api/meetings/{mid}", headers={"X-User-Id": "user_asr"})
    assert resp.status_code == 200
    assert resp.json()["asr_provider"] == "qwen3"


@pytest.mark.asyncio
async def test_create_with_scheduled_times(api_client: AsyncClient, migrated_engine: AsyncEngine):
    """Slice-07: POST accepts scheduled_start_at + scheduled_end_at and echoes them."""
    await _seed_user(migrated_engine, "user_sched_post")

    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_sched_post"},
        json={
            "title": "Q3 review",
            "counterparty_display_name": "林",
            "me_display_name": "Sean",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
            "scheduled_end_at": "2026-06-15T15:00:00Z",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["scheduled_start_at"].startswith("2026-06-15T14:00:00")
    assert body["scheduled_end_at"].startswith("2026-06-15T15:00:00")


@pytest.mark.asyncio
async def test_create_without_scheduled_times_returns_null(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Slice-07: scheduled fields default to null when omitted from POST body."""
    await _seed_user(migrated_engine, "user_no_sched_post")

    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_no_sched_post"},
        json={
            "title": "no schedule",
            "counterparty_display_name": "林",
            "me_display_name": "Sean",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["scheduled_start_at"] is None
    assert body["scheduled_end_at"] is None


@pytest.mark.asyncio
async def test_list_includes_scheduled_times(api_client: AsyncClient, migrated_engine: AsyncEngine):
    """Slice-07: GET /api/meetings includes scheduled fields per row (mix of null + set)."""
    await _seed_user(migrated_engine, "user_list_sched")

    await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_list_sched"},
        json={
            "title": "with",
            "counterparty_display_name": "L",
            "me_display_name": "S",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
            "scheduled_end_at": "2026-06-15T15:00:00Z",
        },
    )
    await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_list_sched"},
        json={
            "title": "without",
            "counterparty_display_name": "L",
            "me_display_name": "S",
        },
    )

    resp = await api_client.get("/api/meetings", headers={"X-User-Id": "user_list_sched"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    for item in items:
        assert "scheduled_start_at" in item
        assert "scheduled_end_at" in item
