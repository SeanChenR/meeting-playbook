"""End-to-end integration test for meeting linking — slice-21 task 7.2.

Single-user flow:
  (a) POST creates A↔B link → 201
  (b) GET  /api/meetings/A/links shows B
  (c) GET  /api/meetings/B/links shows A
  (d) Second POST in REVERSE direction → 409 meeting_link.duplicate
  (e) DELETE → 204, both sides see empty list

Cross-user flow verifies ownership isolation maintains 404 leaks-protection.
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


async def _create_meeting(client: AsyncClient, user_id: str, title: str) -> str:
    resp = await client.post(
        "/api/meetings",
        headers={"X-User-Id": user_id},
        json={
            "title": title,
            "counterparty_display_name": "C",
            "me_display_name": "Me",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_meeting_link_full_lifecycle(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """POST → GET both sides → reverse-POST 409 → DELETE → both sides empty."""
    await _seed_user(migrated_engine, "u_e2e")
    a = await _create_meeting(api_client, "u_e2e", "Meeting A")
    b = await _create_meeting(api_client, "u_e2e", "Meeting B")

    # (a) Create A→B link
    create = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_e2e"},
        json={"to_meeting_id": b},
    )
    assert create.status_code == 201, create.text
    link_id = create.json()["link_id"]
    assert link_id  # non-empty UUID string

    # (b) GET from A's side — sees B as other_meeting
    list_a = await api_client.get(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_e2e"},
    )
    assert list_a.status_code == 200
    assert len(list_a.json()["links"]) == 1
    assert list_a.json()["links"][0]["other_meeting_id"] == b
    assert list_a.json()["links"][0]["other_meeting_title"] == "Meeting B"

    # (c) GET from B's side — sees A as other_meeting
    list_b = await api_client.get(
        f"/api/meetings/{b}/links",
        headers={"X-User-Id": "u_e2e"},
    )
    assert list_b.status_code == 200
    assert len(list_b.json()["links"]) == 1
    assert list_b.json()["links"][0]["other_meeting_id"] == a
    assert list_b.json()["links"][0]["link_id"] == link_id  # same row

    # (d) Reverse-direction POST → 409
    dup = await api_client.post(
        f"/api/meetings/{b}/links",
        headers={"X-User-Id": "u_e2e"},
        json={"to_meeting_id": a},
    )
    assert dup.status_code == 409
    assert dup.json()["error_code"] == "meeting_link.duplicate"

    # (e) DELETE — both sides now empty
    delete = await api_client.delete(
        f"/api/meetings/{a}/links/{link_id}",
        headers={"X-User-Id": "u_e2e"},
    )
    assert delete.status_code == 204
    for side in (a, b):
        listing = await api_client.get(
            f"/api/meetings/{side}/links",
            headers={"X-User-Id": "u_e2e"},
        )
        assert listing.status_code == 200
        assert listing.json()["links"] == []


@pytest.mark.asyncio
async def test_meeting_link_cross_user_ownership_isolation(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """U2 cannot see / touch U1's meeting via the links endpoints — always 404."""
    await _seed_user(migrated_engine, "u_e2e_owner")
    await _seed_user(migrated_engine, "u_e2e_intruder")
    a = await _create_meeting(api_client, "u_e2e_owner", "Owner-A")
    b = await _create_meeting(api_client, "u_e2e_owner", "Owner-B")
    create = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_e2e_owner"},
        json={"to_meeting_id": b},
    )
    assert create.status_code == 201
    link_id = create.json()["link_id"]

    # U2 cannot GET U1's meeting's links
    list_resp = await api_client.get(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_e2e_intruder"},
    )
    assert list_resp.status_code == 404
    assert list_resp.json()["error_code"] == "meeting.not_found"

    # U2 cannot DELETE U1's link by borrowing the path meeting_id
    delete = await api_client.delete(
        f"/api/meetings/{a}/links/{link_id}",
        headers={"X-User-Id": "u_e2e_intruder"},
    )
    assert delete.status_code == 404
    assert delete.json()["error_code"] == "meeting_link.not_found"

    # Owner can still see the link — row was not deleted.
    list_owner = await api_client.get(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_e2e_owner"},
    )
    assert list_owner.status_code == 200
    assert len(list_owner.json()["links"]) == 1
