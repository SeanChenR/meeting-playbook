"""`GET /api/meetings` filter / order / limit integration tests (slice-18 task 2.3).

Covers the spec requirement "Meeting list endpoint SHALL support filters and
ordering required by the home page regions" and Decision 7 (each region calls
the existing list endpoint with a filter combo).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app

TAIPEI = ZoneInfo("Asia/Taipei")


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


async def _insert(
    engine: AsyncEngine,
    *,
    user_id: str,
    title: str,
    scheduled: datetime,
    status: str = "scheduled",
    updated_at: datetime | None = None,
) -> str:
    import secrets

    mid = f"m_{secrets.token_urlsafe(8)}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name,
                    status, asr_provider, created_at, scheduled_start_at, updated_at
                ) VALUES (
                    :id, :user_id, :title, 'cp', 'me', :status, 'qwen3',
                    :scheduled, :scheduled, :updated_at
                )
                """
            ),
            {
                "id": mid,
                "user_id": user_id,
                "title": title,
                "status": status,
                "scheduled": scheduled,
                "updated_at": updated_at or scheduled,
            },
        )
    return mid


@pytest.mark.asyncio
async def test_scheduled_date_filter(api_client: AsyncClient, migrated_engine: AsyncEngine):
    user_id = "filter_user"
    await _seed_user(migrated_engine, user_id)
    # 2026-05-15 in Asia/Taipei = 2026-05-14 16:00 UTC → 2026-05-15 16:00 UTC
    today_morning = datetime(2026, 5, 15, 9, 0, tzinfo=TAIPEI).astimezone(UTC)
    today_evening = datetime(2026, 5, 15, 18, 0, tzinfo=TAIPEI).astimezone(UTC)
    other_day = datetime(2026, 5, 14, 23, 0, tzinfo=TAIPEI).astimezone(UTC)

    await _insert(migrated_engine, user_id=user_id, title="today-morning", scheduled=today_morning)
    await _insert(migrated_engine, user_id=user_id, title="today-evening", scheduled=today_evening)
    await _insert(migrated_engine, user_id=user_id, title="yesterday", scheduled=other_day)

    resp = await api_client.get(
        "/api/meetings",
        params={"scheduled_date": "2026-05-15", "order": "scheduled_start_at:asc"},
        headers={"X-User-Id": user_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    titles = [m["title"] for m in body]
    assert titles == ["today-morning", "today-evening"]


@pytest.mark.asyncio
async def test_status_filter(api_client: AsyncClient, migrated_engine: AsyncEngine):
    user_id = "status_user"
    await _seed_user(migrated_engine, user_id)
    anchor = datetime(2026, 5, 10, 10, 0, tzinfo=TAIPEI).astimezone(UTC)
    await _insert(
        migrated_engine, user_id=user_id, title="active", scheduled=anchor, status="in_progress"
    )
    await _insert(
        migrated_engine, user_id=user_id, title="done", scheduled=anchor, status="completed"
    )
    await _insert(
        migrated_engine, user_id=user_id, title="future", scheduled=anchor, status="scheduled"
    )

    resp = await api_client.get(
        "/api/meetings", params={"status": "in_progress"}, headers={"X-User-Id": user_id}
    )
    assert resp.status_code == 200
    titles = [m["title"] for m in resp.json()]
    assert titles == ["active"]


@pytest.mark.asyncio
async def test_pending_filter(api_client: AsyncClient, migrated_engine: AsyncEngine):
    """pending=true → meetings with status=completed and no summary row OR
    those still ingest-pending (recording without final state).

    For this slice we cover the summary-pending half because that's the only
    pending signal currently exposed via SQL. Ingest-pending is handled by the
    offline-ingest module and out-of-scope for this test.
    """
    user_id = "pending_user"
    await _seed_user(migrated_engine, user_id)
    anchor = datetime(2026, 5, 10, 10, 0, tzinfo=TAIPEI).astimezone(UTC)
    mid_completed_no_summary = await _insert(
        migrated_engine,
        user_id=user_id,
        title="needs-summary",
        scheduled=anchor,
        status="completed",
    )
    mid_completed_with_summary = await _insert(
        migrated_engine,
        user_id=user_id,
        title="summarized",
        scheduled=anchor,
        status="completed",
    )
    # Seed a summary row for the second meeting.
    import secrets

    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO summary (id, meeting_id, markdown, generated_at)
                VALUES (:id, :mid, 'x', now())
                """
            ),
            {"id": f"s_{secrets.token_urlsafe(8)}", "mid": mid_completed_with_summary},
        )

    # Also seed a non-completed meeting so it is excluded.
    await _insert(
        migrated_engine,
        user_id=user_id,
        title="scheduled-not-pending",
        scheduled=anchor,
        status="scheduled",
    )

    resp = await api_client.get(
        "/api/meetings", params={"pending": "true"}, headers={"X-User-Id": user_id}
    )
    assert resp.status_code == 200
    titles = [m["title"] for m in resp.json()]
    assert titles == ["needs-summary"]
    assert mid_completed_no_summary in [m["id"] for m in resp.json()]


@pytest.mark.asyncio
async def test_order_updated_at_desc_with_limit(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    user_id = "order_user"
    await _seed_user(migrated_engine, user_id)
    anchor = datetime(2026, 5, 10, 10, 0, tzinfo=TAIPEI).astimezone(UTC)
    for i, title in enumerate(["a", "b", "c", "d"]):
        await _insert(
            migrated_engine,
            user_id=user_id,
            title=title,
            scheduled=anchor,
            updated_at=anchor + timedelta(hours=i),
        )

    resp = await api_client.get(
        "/api/meetings",
        params={"order": "updated_at:desc", "limit": "3"},
        headers={"X-User-Id": user_id},
    )
    assert resp.status_code == 200
    titles = [m["title"] for m in resp.json()]
    assert titles == ["d", "c", "b"]


@pytest.mark.asyncio
async def test_order_scheduled_start_at_asc(api_client: AsyncClient, migrated_engine: AsyncEngine):
    user_id = "order_asc_user"
    await _seed_user(migrated_engine, user_id)
    base = datetime(2026, 5, 15, 9, 0, tzinfo=TAIPEI).astimezone(UTC)
    for i, title in enumerate(["first", "second", "third"]):
        await _insert(
            migrated_engine,
            user_id=user_id,
            title=title,
            scheduled=base + timedelta(hours=i * 2),
        )

    resp = await api_client.get(
        "/api/meetings",
        params={"order": "scheduled_start_at:asc"},
        headers={"X-User-Id": user_id},
    )
    assert resp.status_code == 200
    titles = [m["title"] for m in resp.json()]
    assert titles == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_list_without_filters_unchanged(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Existing default sort by `created_at DESC` MUST remain when no order is given."""
    user_id = "default_user"
    await _seed_user(migrated_engine, user_id)
    anchor = datetime(2026, 5, 1, 10, 0, tzinfo=TAIPEI).astimezone(UTC)
    # Insert older first; SQL `created_at` defaults to scheduled here.
    await _insert(migrated_engine, user_id=user_id, title="older", scheduled=anchor)
    await _insert(
        migrated_engine,
        user_id=user_id,
        title="newer",
        scheduled=anchor + timedelta(days=2),
    )

    resp = await api_client.get("/api/meetings", headers={"X-User-Id": user_id})
    assert resp.status_code == 200
    titles = [m["title"] for m in resp.json()]
    # Default = created_at DESC (already-established slice-03 behaviour); we
    # set created_at = scheduled, so "newer" comes first.
    assert titles[0] == "newer"
