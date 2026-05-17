"""Meeting-link REST endpoint tests — slice-21 tasks 3.1, 3.2, 3.3.

Covered scenarios (from `meeting-linking/spec.md`):
- GET — `User views related links for their own meeting`
- GET — `Ownership isolation hides another user's meeting`
- POST — `First-time link creation succeeds`
- POST — `Duplicate link rejected regardless of direction`
- POST — `Self-reference rejected with 422`
- DELETE — `Either-side delete removes the link once`
- DELETE — `Delete on a foreign link returns 404 without leaking existence`
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


async def _create_meeting(api_client: AsyncClient, user_id: str, title: str) -> str:
    resp = await api_client.post(
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


# ─── Task 3.1: GET ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_links_for_own_meeting_returns_list(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Owner GETs their meeting's links + sees the other-meeting view."""
    await _seed_user(migrated_engine, "u_get_self")
    a = await _create_meeting(api_client, "u_get_self", "A")
    b = await _create_meeting(api_client, "u_get_self", "B")

    # Create a link via the POST endpoint so the integration is end-to-end.
    create_resp = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_get_self"},
        json={"to_meeting_id": b},
    )
    assert create_resp.status_code == 201, create_resp.text

    resp = await api_client.get(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_get_self"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "links" in body
    assert len(body["links"]) == 1
    link = body["links"][0]
    assert link["other_meeting_id"] == b
    assert link["other_meeting_title"] == "B"
    assert link["link_type"] == "related"


@pytest.mark.asyncio
async def test_get_links_returns_404_for_other_users_meeting(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """U2 cannot peek at U1's meeting's links — must 404 with meeting.not_found."""
    await _seed_user(migrated_engine, "u_owner")
    await _seed_user(migrated_engine, "u_intruder")
    a = await _create_meeting(api_client, "u_owner", "Owner-only")

    resp = await api_client.get(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_intruder"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "meeting.not_found"


# ─── Task 3.2: POST ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_post_link_creates_201(api_client: AsyncClient, migrated_engine: AsyncEngine) -> None:
    """First-time create returns 201 with link_id."""
    await _seed_user(migrated_engine, "u_post_ok")
    a = await _create_meeting(api_client, "u_post_ok", "A")
    b = await _create_meeting(api_client, "u_post_ok", "B")

    resp = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_post_ok"},
        json={"to_meeting_id": b},
    )
    assert resp.status_code == 201, resp.text
    assert "link_id" in resp.json()


@pytest.mark.asyncio
async def test_post_same_direction_duplicate_returns_409(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """A second POST in the same direction returns 409 meeting_link.duplicate."""
    await _seed_user(migrated_engine, "u_post_dup")
    a = await _create_meeting(api_client, "u_post_dup", "A")
    b = await _create_meeting(api_client, "u_post_dup", "B")

    first = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_post_dup"},
        json={"to_meeting_id": b},
    )
    assert first.status_code == 201
    second = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_post_dup"},
        json={"to_meeting_id": b},
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "meeting_link.duplicate"


@pytest.mark.asyncio
async def test_post_reverse_direction_duplicate_returns_409(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """A second POST in the REVERSE direction also returns 409."""
    await _seed_user(migrated_engine, "u_post_rev")
    a = await _create_meeting(api_client, "u_post_rev", "A")
    b = await _create_meeting(api_client, "u_post_rev", "B")

    first = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_post_rev"},
        json={"to_meeting_id": b},
    )
    assert first.status_code == 201
    second = await api_client.post(
        f"/api/meetings/{b}/links",
        headers={"X-User-Id": "u_post_rev"},
        json={"to_meeting_id": a},
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "meeting_link.duplicate"


@pytest.mark.asyncio
async def test_post_self_reference_returns_422(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """POST `{to_meeting_id: id}` for the URL's own id returns 422
    meeting_link.self_reference."""
    await _seed_user(migrated_engine, "u_post_self")
    a = await _create_meeting(api_client, "u_post_self", "A")

    resp = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_post_self"},
        json={"to_meeting_id": a},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "meeting_link.self_reference"


@pytest.mark.asyncio
async def test_post_to_other_users_meeting_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """POST linking to someone else's meeting is 404 (cannot leak existence)."""
    await _seed_user(migrated_engine, "u_post_x_self")
    await _seed_user(migrated_engine, "u_post_x_other")
    self_a = await _create_meeting(api_client, "u_post_x_self", "Mine")
    others = await _create_meeting(api_client, "u_post_x_other", "Theirs")

    resp = await api_client.post(
        f"/api/meetings/{self_a}/links",
        headers={"X-User-Id": "u_post_x_self"},
        json={"to_meeting_id": others},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "meeting.not_found"


# ─── Task 3.3: DELETE ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_from_either_side_returns_204(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Owner deletes from EITHER side path -> 204; subsequent GET shows empty."""
    await _seed_user(migrated_engine, "u_del_ok")
    a = await _create_meeting(api_client, "u_del_ok", "A")
    b = await _create_meeting(api_client, "u_del_ok", "B")

    create = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_del_ok"},
        json={"to_meeting_id": b},
    )
    link_id = create.json()["link_id"]

    # Delete from the B-side path — bidirectional contract.
    resp = await api_client.delete(
        f"/api/meetings/{b}/links/{link_id}",
        headers={"X-User-Id": "u_del_ok"},
    )
    assert resp.status_code == 204, resp.text

    # Both sides should now report zero links.
    for side in (a, b):
        list_resp = await api_client.get(
            f"/api/meetings/{side}/links",
            headers={"X-User-Id": "u_del_ok"},
        )
        assert list_resp.json()["links"] == []


@pytest.mark.asyncio
async def test_delete_foreign_link_via_own_meeting_path_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """U2 cannot use one of their own meeting ids on the path to delete U1's link."""
    await _seed_user(migrated_engine, "u_del_owner")
    await _seed_user(migrated_engine, "u_del_intruder")
    a = await _create_meeting(api_client, "u_del_owner", "A")
    b = await _create_meeting(api_client, "u_del_owner", "B")
    intruder_x = await _create_meeting(api_client, "u_del_intruder", "X")

    create = await api_client.post(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_del_owner"},
        json={"to_meeting_id": b},
    )
    link_id = create.json()["link_id"]

    # Intruder tries to delete via their own meeting id on the path.
    resp = await api_client.delete(
        f"/api/meetings/{intruder_x}/links/{link_id}",
        headers={"X-User-Id": "u_del_intruder"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "meeting_link.not_found"

    # Confirm the row was NOT deleted — owner can still see it.
    list_resp = await api_client.get(
        f"/api/meetings/{a}/links",
        headers={"X-User-Id": "u_del_owner"},
    )
    assert len(list_resp.json()["links"]) == 1
