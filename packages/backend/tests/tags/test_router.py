"""Tag REST router tests — slice-17 tasks 3.1 / 3.2 / 3.3.

Covers every spec scenario for:
- `GET / POST / PATCH / DELETE /api/tags` (3.1, 3.2)
- `POST / DELETE /api/meetings/{id}/tags(/{tag_id})` (3.3)
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app
from meeting_playbook.tags.models import MeetingTag

PALETTE_PRIMARY = "#DDD6FE"
PALETTE_SECONDARY = "#7C2D12"


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
            "counterparty_display_name": "cp",
            "me_display_name": "me",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_tag(
    client: AsyncClient, user_id: str, name: str, color: str = PALETTE_PRIMARY
) -> str:
    resp = await client.post(
        "/api/tags",
        headers={"X-User-Id": user_id},
        json={"name": name, "color": color},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ─── Task 3.1: GET /api/tags ────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tags_returns_only_owners_tags(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    await _create_tag(api_client, "u_a", "客戶X")
    await _create_tag(api_client, "u_a", "面試")
    await _create_tag(api_client, "u_b", "別人的")

    resp = await api_client.get("/api/tags", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 200
    body = resp.json()
    names = {item["name"] for item in body}
    assert names == {"客戶X", "面試"}
    for item in body:
        assert "meeting_count" not in item


@pytest.mark.asyncio
async def test_get_tags_with_meeting_count_includes_counts(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    t1 = await _create_tag(api_client, "u_a", "t1")
    t2 = await _create_tag(api_client, "u_a", "t2")
    # attach t1 to 5 meetings, t2 to 0.
    for i in range(5):
        mid = await _create_meeting(api_client, "u_a", f"m{i}")
        await api_client.post(
            f"/api/meetings/{mid}/tags",
            headers={"X-User-Id": "u_a"},
            json={"tag_id": t1},
        )

    resp = await api_client.get("/api/tags?with_meeting_count=true", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 200
    by_id = {item["id"]: item for item in resp.json()}
    assert by_id[t1]["meeting_count"] == 5
    assert by_id[t2]["meeting_count"] == 0


# ─── Task 3.2: POST / PATCH / DELETE /api/tags ──────────────────────


@pytest.mark.asyncio
async def test_post_tag_rejects_duplicate_name_case_insensitive(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    await _create_tag(api_client, "u_a", "客戶X")
    resp = await api_client.post(
        "/api/tags",
        headers={"X-User-Id": "u_a"},
        json={"name": "客戶x", "color": PALETTE_PRIMARY},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "tag.name_taken"


@pytest.mark.asyncio
async def test_post_tag_rejects_invalid_color(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    resp = await api_client.post(
        "/api/tags",
        headers={"X-User-Id": "u_a"},
        json={"name": "x", "color": "#123456"},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "tag.invalid_color"


@pytest.mark.asyncio
async def test_post_tag_rejects_empty_name(api_client: AsyncClient, migrated_engine: AsyncEngine):
    await _seed_user(migrated_engine, "u_a")
    resp = await api_client.post(
        "/api/tags",
        headers={"X-User-Id": "u_a"},
        json={"name": "   ", "color": PALETTE_PRIMARY},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "tag.name_required"


@pytest.mark.asyncio
async def test_patch_own_tag_updates_name_and_color(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    tag = await _create_tag(api_client, "u_a", "old", PALETTE_PRIMARY)
    resp = await api_client.patch(
        f"/api/tags/{tag}",
        headers={"X-User-Id": "u_a"},
        json={"name": "new", "color": PALETTE_SECONDARY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "new"
    assert body["color"] == PALETTE_SECONDARY


@pytest.mark.asyncio
async def test_patch_with_duplicate_name_returns_422(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    a = await _create_tag(api_client, "u_a", "客戶X")
    b = await _create_tag(api_client, "u_a", "面試", color=PALETTE_SECONDARY)
    resp = await api_client.patch(
        f"/api/tags/{b}",
        headers={"X-User-Id": "u_a"},
        json={"name": "客戶x"},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "tag.name_taken"
    # The original `a` was untouched.
    assert a is not None


@pytest.mark.asyncio
async def test_patch_with_invalid_color_returns_422(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    tag = await _create_tag(api_client, "u_a", "t")
    resp = await api_client.patch(
        f"/api/tags/{tag}",
        headers={"X-User-Id": "u_a"},
        json={"color": "#123456"},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "tag.invalid_color"


@pytest.mark.asyncio
async def test_delete_other_users_tag_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    other = await _create_tag(api_client, "u_b", "other")
    resp = await api_client.delete(f"/api/tags/{other}", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_attach_to_missing_meeting_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    tag = await _create_tag(api_client, "u_a", "客戶X")
    resp = await api_client.post(
        "/api/meetings/m_missing/tags",
        headers={"X-User-Id": "u_a"},
        json={"tag_id": tag},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_other_users_tag_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    other_tag = await _create_tag(api_client, "u_b", "other")
    resp = await api_client.patch(
        f"/api/tags/{other_tag}",
        headers={"X-User-Id": "u_a"},
        json={"name": "stolen"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_tag_cascades_meeting_tag_rows(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    tag = await _create_tag(api_client, "u_a", "客戶X")
    m1 = await _create_meeting(api_client, "u_a", "m1")
    m2 = await _create_meeting(api_client, "u_a", "m2")
    for mid in (m1, m2):
        await api_client.post(
            f"/api/meetings/{mid}/tags",
            headers={"X-User-Id": "u_a"},
            json={"tag_id": tag},
        )

    resp = await api_client.delete(f"/api/tags/{tag}", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 204

    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    async with Session() as s:
        rows = (await s.execute(select(MeetingTag).where(MeetingTag.tag_id == tag))).scalars().all()
        assert list(rows) == []


# ─── Task 3.3: POST / DELETE /api/meetings/{id}/tags ────────────────


@pytest.mark.asyncio
async def test_attach_eleventh_tag_returns_422_with_count(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    mid = await _create_meeting(api_client, "u_a", "big")
    for i in range(10):
        tag = await _create_tag(api_client, "u_a", f"t{i}")
        resp = await api_client.post(
            f"/api/meetings/{mid}/tags",
            headers={"X-User-Id": "u_a"},
            json={"tag_id": tag},
        )
        assert resp.status_code == 201
    eleventh = await _create_tag(api_client, "u_a", "eleventh")

    resp = await api_client.post(
        f"/api/meetings/{mid}/tags",
        headers={"X-User-Id": "u_a"},
        json={"tag_id": eleventh},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "tag.too_many_for_meeting"
    assert "10" in body["message"]


@pytest.mark.asyncio
async def test_detach_non_attached_pair_returns_204(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    mid = await _create_meeting(api_client, "u_a", "m")
    tag = await _create_tag(api_client, "u_a", "客戶X")

    resp = await api_client.delete(f"/api/meetings/{mid}/tags/{tag}", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_attach_using_other_users_tag_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    mid = await _create_meeting(api_client, "u_a", "m")
    other_tag = await _create_tag(api_client, "u_b", "other")

    resp = await api_client.post(
        f"/api/meetings/{mid}/tags",
        headers={"X-User-Id": "u_a"},
        json={"tag_id": other_tag},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_re_attach_same_pair_is_idempotent(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    mid = await _create_meeting(api_client, "u_a", "m")
    tag = await _create_tag(api_client, "u_a", "客戶X")
    first = await api_client.post(
        f"/api/meetings/{mid}/tags",
        headers={"X-User-Id": "u_a"},
        json={"tag_id": tag},
    )
    second = await api_client.post(
        f"/api/meetings/{mid}/tags",
        headers={"X-User-Id": "u_a"},
        json={"tag_id": tag},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["attached_at"] == second.json()["attached_at"]
