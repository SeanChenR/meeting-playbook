"""Playbook REST endpoint tests.

Per spec (slice-04-playbook-editor, playbook-management):
- GET /api/meetings/{id}/playbook auto-creates an empty row on first read,
  returns the same id on subsequent reads
- PUT performs a full upsert
- Both endpoints gate on meeting ownership; cross-user access returns 404
  with `error_code: meeting.not_found` (no existence leak)
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
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client


async def _seed_user_and_meeting(engine: AsyncEngine, user_id: str, meeting_id: str) -> None:
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
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
                VALUES (:mid, :uid, 'T', 'C', 'M')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )


@pytest.mark.asyncio
async def test_first_get_auto_creates_empty_playbook(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: First GET returns a fully-formed empty playbook."""
    await _seed_user_and_meeting(migrated_engine, "u_first", "m_first")

    resp = await api_client.get("/api/meetings/m_first/playbook", headers={"X-User-Id": "u_first"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["meeting_id"] == "m_first"
    assert body["id"].startswith("pb_")
    for field in (
        "free_form_markdown",
        "objective",
        "counterparty_profile",
        "anticipated_topics",
        "anticipated_objections",
        "talking_points",
        "red_lines",
    ):
        assert body[field] == "", f"{field} should default to '' but was {body[field]!r}"


@pytest.mark.asyncio
async def test_second_get_returns_same_playbook_id(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Subsequent GET returns the same row id, not a new one."""
    await _seed_user_and_meeting(migrated_engine, "u_idem", "m_idem")
    headers = {"X-User-Id": "u_idem"}

    first = await api_client.get("/api/meetings/m_idem/playbook", headers=headers)
    second = await api_client.get("/api/meetings/m_idem/playbook", headers=headers)
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_put_full_payload_persists_and_round_trips(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Full payload persists and returns the same values."""
    await _seed_user_and_meeting(migrated_engine, "u_put", "m_put")
    headers = {"X-User-Id": "u_put"}

    payload = {
        "free_form_markdown": "# Brief",
        "objective": "Close Q3 deal",
        "counterparty_profile": "林經理",
        "anticipated_topics": "pricing",
        "anticipated_objections": "budget",
        "talking_points": "value prop",
        "red_lines": "no discount below 30%",
    }
    put_resp = await api_client.put("/api/meetings/m_put/playbook", headers=headers, json=payload)
    assert put_resp.status_code == 200, put_resp.text
    for field, expected in payload.items():
        assert put_resp.json()[field] == expected

    follow = await api_client.get("/api/meetings/m_put/playbook", headers=headers)
    for field, expected in payload.items():
        assert follow.json()[field] == expected


@pytest.mark.asyncio
async def test_cross_user_get_returns_404_meeting_not_found(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Reading another user's playbook returns 404."""
    await _seed_user_and_meeting(migrated_engine, "u_a_get", "m_get_owned_by_b")
    # Override owner to user B by re-inserting the meeting under B.
    async with migrated_engine.begin() as conn:
        await conn.execute(text("DELETE FROM meeting WHERE id = :mid"), {"mid": "m_get_owned_by_b"})
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('u_b_get', 'b', 'u_b_get@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
                VALUES ('m_get_owned_by_b', 'u_b_get', 'B-secret', 'C', 'M')
                """
            )
        )

    resp = await api_client.get(
        "/api/meetings/m_get_owned_by_b/playbook", headers={"X-User-Id": "u_a_get"}
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "meeting.not_found"
    flat = str(body).lower()
    assert "secret" not in flat
    assert "u_b_get" not in flat


@pytest.mark.asyncio
async def test_cross_user_put_returns_404_and_keeps_playbook_unchanged(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: Writing another user's playbook returns 404 and persists nothing."""
    await _seed_user_and_meeting(migrated_engine, "u_b_put", "m_put_owned_by_b")

    # User A tries to PUT user B's playbook.
    resp = await api_client.put(
        "/api/meetings/m_put_owned_by_b/playbook",
        headers={"X-User-Id": "u_a_attacker"},
        json={"free_form_markdown": "INJECTED"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "meeting.not_found"

    # Owner reads — must not see "INJECTED".
    follow = await api_client.get(
        "/api/meetings/m_put_owned_by_b/playbook", headers={"X-User-Id": "u_b_put"}
    )
    assert follow.status_code == 200
    assert follow.json()["free_form_markdown"] == ""


@pytest.mark.asyncio
async def test_request_without_x_user_id_is_rejected(api_client: AsyncClient):
    resp = await api_client.get("/api/meetings/m_any/playbook")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "auth.gateway_bypass"


# ─── Slice-23: PlaybookRead exposes previous-version snapshot fields ─────


@pytest.mark.asyncio
async def test_get_without_snapshot_returns_null_previous_fields(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Spec `playbook-management` scenario:
    GET on row without snapshot returns null previous fields + has_previous_version=false.
    """
    await _seed_user_and_meeting(migrated_engine, "u_s23_get_null", "m_s23_get_null")
    resp = await api_client.get(
        "/api/meetings/m_s23_get_null/playbook",
        headers={"X-User-Id": "u_s23_get_null"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["previous_free_form_markdown"] is None
    assert body["previous_updated_at"] is None
    assert body["has_previous_version"] is False


@pytest.mark.asyncio
async def test_get_with_snapshot_returns_full_previous_fields(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Spec `playbook-management` scenario:
    GET on row WITH snapshot returns the full previous_* triple + has_previous_version=true.
    """
    await _seed_user_and_meeting(migrated_engine, "u_s23_get_full", "m_s23_get_full")
    # Manually set previous_* via UPDATE so we don't depend on regenerate handler
    # (that's exercised in test_regenerate_*).
    async with migrated_engine.begin() as conn:
        # First write through the normal POST → PUT path so the row exists.
        # Easier: insert via SQL.
        await conn.execute(
            text(
                """
                INSERT INTO playbook (id, meeting_id, free_form_markdown,
                  objective, counterparty_profile, anticipated_topics,
                  anticipated_objections, talking_points, red_lines,
                  created_at, updated_at,
                  previous_free_form_markdown, previous_updated_at)
                VALUES ('pb_s23_get_full', 'm_s23_get_full', 'draft v2',
                  '', '', '', '', '', '',
                  now(), now(),
                  'draft v1', '2026-05-17T10:00:00+00:00')
                """
            )
        )

    resp = await api_client.get(
        "/api/meetings/m_s23_get_full/playbook",
        headers={"X-User-Id": "u_s23_get_full"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["previous_free_form_markdown"] == "draft v1"
    assert body["previous_updated_at"] == "2026-05-17T10:00:00Z"
    assert body["has_previous_version"] is True
