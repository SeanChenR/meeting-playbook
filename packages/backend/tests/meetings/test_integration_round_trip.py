"""Backend integration round-trip — create → list → get → delete.

Simulates the gateway → FastAPI flow exactly as the production stack would,
exercising every meeting endpoint in sequence against a real PostgreSQL
test DB. This is the slice-03 vertical-slice end-to-end coverage seed
(Test strategy → "backend integration test充當端到端覆蓋").

Per ADR-0021: the gateway is the sole ingress; FastAPI trusts the
gateway-injected `X-User-Id` header without re-validation.
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


@pytest.mark.asyncio
async def test_meeting_full_lifecycle(api_client: AsyncClient, migrated_engine: AsyncEngine):
    """Round trip — POST → GET list → GET id → DELETE → GET id 404."""
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('user_rt', 'RT', 'rt@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )

    headers = {"X-User-Id": "user_rt"}

    # 1. Create — backend enforces defaults despite client noise.
    create = await api_client.post(
        "/api/meetings",
        headers=headers,
        json={
            "title": "Round trip",
            "counterparty_display_name": "林經理",
            "me_display_name": "Sean",
            "scheduled_start_at": "2026-06-15T14:00:00Z",
            "status": "completed",  # ignored on create per spec
        },
    )
    assert create.status_code == 201, create.text
    created = create.json()
    mid = created["id"]
    assert created["status"] == "scheduled"
    assert created["asr_provider"] == "qwen3"  # slice-11 migration 0008 default
    assert created["calendar_event_id"] is None

    # 2. List — returns the just-created meeting.
    listed = await api_client.get("/api/meetings", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()
    assert any(m["id"] == mid for m in rows)

    # 3. Get by id — owner can read.
    fetched = await api_client.get(f"/api/meetings/{mid}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Round trip"

    # 4. Delete — owner can delete.
    deleted = await api_client.delete(f"/api/meetings/{mid}", headers=headers)
    assert deleted.status_code == 204

    # 5. After delete: 404 with no existence leak.
    follow = await api_client.get(f"/api/meetings/{mid}", headers=headers)
    assert follow.status_code == 404
    body = follow.json()
    assert body["error_code"] == "meeting.not_found"
