"""Meeting endpoints — slice-17 tag integration (tasks 4.1 + 4.2).

Covers the MODIFIED `meeting-management` spec requirements:
- List + detail response payload include `tags: [{id, name, color}]`.
- `GET /api/meetings?tag_ids=...` filters with AND semantics.
- `tag_ids` referencing another user's tag returns 422 `tag.unknown_id`.
- Empty `tag_ids=` is a no-op.
- N+1 prevention: listing N meetings issues ≤ 2 SELECTs against `tag` /
  `meeting_tag` combined.
- Detail payload includes `tags` ordered by `attached_at` ascending; empty
  meetings return `tags: []`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


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


async def _attach(client: AsyncClient, user_id: str, meeting_id: str, tag_id: str) -> None:
    resp = await client.post(
        f"/api/meetings/{meeting_id}/tags",
        headers={"X-User-Id": user_id},
        json={"tag_id": tag_id},
    )
    assert resp.status_code == 201, resp.text


# ─── Task 4.1: list endpoint ────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_response_items_include_tags_array(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    mid_with = await _create_meeting(api_client, "u_a", "with-tags")
    mid_empty = await _create_meeting(api_client, "u_a", "no-tags")
    t = await _create_tag(api_client, "u_a", "客戶X")
    await _attach(api_client, "u_a", mid_with, t)

    resp = await api_client.get("/api/meetings", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 200
    by_id = {m["id"]: m for m in resp.json()}
    assert by_id[mid_with]["tags"] == [{"id": t, "name": "客戶X", "color": PALETTE_PRIMARY}]
    assert by_id[mid_empty]["tags"] == []


@pytest.mark.asyncio
async def test_list_tag_ids_filters_with_and_semantics(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    m1 = await _create_meeting(api_client, "u_a", "m_1")
    m2 = await _create_meeting(api_client, "u_a", "m_2")
    m3 = await _create_meeting(api_client, "u_a", "m_3")
    ta = await _create_tag(api_client, "u_a", "ta")
    tb = await _create_tag(api_client, "u_a", "tb")
    tc = await _create_tag(api_client, "u_a", "tc")
    # m_1 has both ta + tb, m_2 has only ta, m_3 has tb + tc.
    await _attach(api_client, "u_a", m1, ta)
    await _attach(api_client, "u_a", m1, tb)
    await _attach(api_client, "u_a", m2, ta)
    await _attach(api_client, "u_a", m3, tb)
    await _attach(api_client, "u_a", m3, tc)

    resp = await api_client.get(f"/api/meetings?tag_ids={ta},{tb}", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()}
    assert ids == {m1}


@pytest.mark.asyncio
async def test_list_tag_ids_with_other_users_tag_returns_422_unknown_id(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    foreign = await _create_tag(api_client, "u_b", "other")
    resp = await api_client.get(f"/api/meetings?tag_ids={foreign}", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "tag.unknown_id"


@pytest.mark.asyncio
async def test_list_empty_tag_ids_param_is_noop(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    await _create_meeting(api_client, "u_a", "m1")
    await _create_meeting(api_client, "u_a", "m2")
    plain = await api_client.get("/api/meetings", headers={"X-User-Id": "u_a"})
    empty = await api_client.get("/api/meetings?tag_ids=", headers={"X-User-Id": "u_a"})
    assert plain.status_code == 200 and empty.status_code == 200
    assert [m["id"] for m in plain.json()] == [m["id"] for m in empty.json()]


@pytest.mark.asyncio
async def test_list_50_meetings_issues_at_most_two_tag_selects(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Listing many meetings MUST NOT N+1 query the tag tables.

    We attach the same tag to a subset to exercise the secondary
    `selectinload` path, then count SELECT statements issued during the
    GET that touch either `tag` or `meeting_tag`.
    """
    await _seed_user(migrated_engine, "u_a")
    tag = await _create_tag(api_client, "u_a", "客戶X")
    meeting_ids = []
    for i in range(50):
        mid = await _create_meeting(api_client, "u_a", f"m{i}")
        meeting_ids.append(mid)
        if i % 2 == 0:
            await _attach(api_client, "u_a", mid, tag)

    # Hook in BEFORE the GET so we count only that request's SQL.
    counter = {"tag_selects": 0}

    @event.listens_for(migrated_engine.sync_engine, "before_cursor_execute")
    def _count(_conn, _cursor, statement, _params, _ctx, _exec):
        lowered = statement.lower()
        if lowered.startswith("select") and (
            "meeting_tag" in lowered
            or " tag " in lowered
            or " tag\n" in lowered
            or "from tag" in lowered
        ):
            counter["tag_selects"] += 1

    try:
        resp = await api_client.get("/api/meetings", headers={"X-User-Id": "u_a"})
        assert resp.status_code == 200
        assert len(resp.json()) == 50
        assert counter["tag_selects"] <= 2, (
            f"Expected ≤ 2 SELECTs against tag / meeting_tag, got {counter['tag_selects']}"
        )
    finally:
        event.remove(migrated_engine.sync_engine, "before_cursor_execute", _count)


# ─── Task 4.2: detail endpoint ──────────────────────────────────────


@pytest.mark.asyncio
async def test_detail_returns_tags_array_ordered_by_attached_at(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    mid = await _create_meeting(api_client, "u_a", "m")
    t1 = await _create_tag(api_client, "u_a", "first")
    t2 = await _create_tag(api_client, "u_a", "second", color=PALETTE_SECONDARY)
    await _attach(api_client, "u_a", mid, t1)
    await _attach(api_client, "u_a", mid, t2)

    resp = await api_client.get(f"/api/meetings/{mid}", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 200
    tags = resp.json()["tags"]
    assert [t["id"] for t in tags] == [t1, t2]
    assert tags[0]["name"] == "first"
    assert tags[1]["color"] == PALETTE_SECONDARY


@pytest.mark.asyncio
async def test_detail_returns_empty_tags_array_when_none_attached(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_a")
    mid = await _create_meeting(api_client, "u_a", "m")
    resp = await api_client.get(f"/api/meetings/{mid}", headers={"X-User-Id": "u_a"})
    assert resp.status_code == 200
    assert resp.json()["tags"] == []
