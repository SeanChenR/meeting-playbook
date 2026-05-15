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
            "scheduled_start_at": "2026-06-15T14:00:00Z",
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
            json={
                "title": title,
                "counterparty_display_name": "C",
                "me_display_name": "M",
                "scheduled_start_at": "2026-06-15T14:00:00Z",
            },
        )
        assert resp.status_code == 201
    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_b"},
        json={
            "title": "B-only",
            "counterparty_display_name": "C",
            "me_display_name": "M",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
        },
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
            "scheduled_start_at": "2026-06-15T14:00:00Z",
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
        json={
            "title": "Protected",
            "counterparty_display_name": "C",
            "me_display_name": "M",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
        },
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
        json={
            "title": "X",
            "counterparty_display_name": "C",
            "me_display_name": "M",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
        },
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
            "scheduled_start_at": "2026-06-15T14:00:00Z",
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
        json={
            "title": "T",
            "counterparty_display_name": "C",
            "me_display_name": "M",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
        },
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
        json={
            "title": "T",
            "counterparty_display_name": "C",
            "me_display_name": "M",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
        },
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
async def test_create_without_scheduled_start_returns_422(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Slice-15: scheduled_start_at became required for new meetings —
    omitting it from the POST body MUST return 422.
    """
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
    assert resp.status_code == 422, resp.text
    # FastAPI's default validation envelope mentions the missing field path.
    flat = str(resp.json()).lower()
    assert "scheduled_start_at" in flat


@pytest.mark.asyncio
async def test_create_with_end_before_start_returns_422(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Slice-15: scheduled_end_at, when supplied, MUST be >= scheduled_start_at."""
    await _seed_user(migrated_engine, "user_end_before_start")

    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_end_before_start"},
        json={
            "title": "bad range",
            "counterparty_display_name": "C",
            "me_display_name": "M",
            "scheduled_start_at": "2026-06-15T15:00:00Z",
            "scheduled_end_at": "2026-06-15T14:00:00Z",
        },
    )
    assert resp.status_code == 422, resp.text
    flat = str(resp.json()).lower()
    assert "scheduled_end_at" in flat or "scheduled_start_at" in flat


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
            "title": "without end",
            "counterparty_display_name": "L",
            "me_display_name": "S",
            # Slice-15 requires scheduled_start_at; omit scheduled_end_at to
            # still cover the "end is nullable" wire shape per spec.
            "scheduled_start_at": "2026-06-16T09:00:00Z",
        },
    )

    resp = await api_client.get("/api/meetings", headers={"X-User-Id": "user_list_sched"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    for item in items:
        assert "scheduled_start_at" in item
        assert "scheduled_end_at" in item


# ─── Slice-15: PATCH router scenarios ──────────────────────────────────


async def _create_test_meeting(api_client, user_id: str, **extra):
    body = {
        "title": "before",
        "counterparty_display_name": "C",
        "me_display_name": "M",
        "scheduled_start_at": "2026-06-15T14:00:00Z",
        **extra,
    }
    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": user_id},
        json=body,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_patch_title_only_returns_updated_row(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Slice-15: PATCH with just `title` succeeds and echoes the new value."""
    await _seed_user(migrated_engine, "user_patch_title")
    mid = await _create_test_meeting(api_client, "user_patch_title")

    resp = await api_client.patch(
        f"/api/meetings/{mid}",
        headers={"X-User-Id": "user_patch_title"},
        json={"title": "after"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "after"
    # Other fields untouched.
    assert body["counterparty_display_name"] == "C"


@pytest.mark.asyncio
async def test_patch_multi_field_updates_all(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Slice-15: multi-field PATCH writes them all in one request."""
    await _seed_user(migrated_engine, "user_patch_multi")
    mid = await _create_test_meeting(api_client, "user_patch_multi")

    resp = await api_client.patch(
        f"/api/meetings/{mid}",
        headers={"X-User-Id": "user_patch_multi"},
        json={
            "title": "after",
            "counterparty_display_name": "新對方",
            "me_display_name": "Sean Chen",
            "scheduled_start_at": "2026-07-01T09:00:00Z",
            "scheduled_end_at": "2026-07-01T10:00:00Z",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "after"
    assert body["counterparty_display_name"] == "新對方"
    assert body["me_display_name"] == "Sean Chen"
    assert body["scheduled_start_at"].startswith("2026-07-01T09:00:00")
    assert body["scheduled_end_at"].startswith("2026-07-01T10:00:00")


@pytest.mark.asyncio
async def test_patch_empty_body_is_noop_200(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Slice-15: empty `{}` body returns current row idempotently."""
    await _seed_user(migrated_engine, "user_patch_empty")
    mid = await _create_test_meeting(api_client, "user_patch_empty")

    resp = await api_client.patch(
        f"/api/meetings/{mid}",
        headers={"X-User-Id": "user_patch_empty"},
        json={},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "before"


@pytest.mark.asyncio
async def test_patch_whitespace_only_string_returns_422(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Whitespace-only `title` is rejected with 422 per shared schema rule."""
    await _seed_user(migrated_engine, "user_patch_ws")
    mid = await _create_test_meeting(api_client, "user_patch_ws")

    resp = await api_client.patch(
        f"/api/meetings/{mid}",
        headers={"X-User-Id": "user_patch_ws"},
        json={"title": "   "},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_patch_end_with_existing_start_after_returns_422(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Slice-15: when only `scheduled_end_at` is sent but the persisted
    `scheduled_start_at` is later than it, the router merges body+row and
    rejects with 422.
    """
    await _seed_user(migrated_engine, "user_patch_range")
    mid = await _create_test_meeting(
        api_client,
        "user_patch_range",
        scheduled_start_at="2026-08-01T15:00:00Z",
    )

    resp = await api_client.patch(
        f"/api/meetings/{mid}",
        headers={"X-User-Id": "user_patch_range"},
        # Existing start is 15:00; this would be 14:00 < 15:00 → must reject.
        json={"scheduled_end_at": "2026-08-01T14:00:00Z"},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error_code"] == "meeting.invalid_time_range"


@pytest.mark.asyncio
async def test_patch_cross_user_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Cross-user PATCH MUST return 404 without leaking existence."""
    await _seed_user(migrated_engine, "user_owner_p")
    await _seed_user(migrated_engine, "user_intruder_p")
    mid = await _create_test_meeting(api_client, "user_owner_p")

    resp = await api_client.patch(
        f"/api/meetings/{mid}",
        headers={"X-User-Id": "user_intruder_p"},
        json={"title": "stolen"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_asr_provider_only_still_works(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Slice-11 behaviour kept: PATCH with just `asr_provider` flips the
    persisted engine. Slice-15 implementation delegates through the new
    multi-field path.
    """
    await _seed_user(migrated_engine, "user_patch_asr")
    mid = await _create_test_meeting(api_client, "user_patch_asr")

    resp = await api_client.patch(
        f"/api/meetings/{mid}",
        headers={"X-User-Id": "user_patch_asr"},
        json={"asr_provider": "whisper"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["asr_provider"] == "whisper"
