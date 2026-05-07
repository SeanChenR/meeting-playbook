"""PUT validation matrix from spec slice-04-playbook-editor.

Per spec example matrix (Requirement: "PUT performs a full upsert with seven
content fields"):

| Body sent on PUT                                  | Resulting `objective` | Resulting `red_lines` |
|---------------------------------------------------|-----------------------|-----------------------|
| `{"objective": "X", "red_lines": "Y"}`            | "X"                   | "Y"                   |
| `{"objective": "X"}` (no red_lines key)           | "X"                   | ""                    |
| `{}` (empty object)                               | ""                    | ""                    |

Plus a long-body round trip and updated_at advancement.
"""

from __future__ import annotations

import asyncio
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


async def _seed(engine: AsyncEngine, user_id: str, meeting_id: str) -> None:
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


_MATRIX = [
    pytest.param(
        {"objective": "X", "red_lines": "Y"},
        "X",
        "Y",
        id="both-set",
    ),
    pytest.param(
        {"objective": "X"},
        "X",
        "",
        id="missing-red-lines-becomes-empty",
    ),
    pytest.param(
        {},
        "",
        "",
        id="empty-body-everything-empty",
    ),
]


@pytest.mark.parametrize("body,expected_objective,expected_red_lines", _MATRIX)
@pytest.mark.asyncio
async def test_put_missing_fields_default_to_empty_string(
    api_client: AsyncClient,
    migrated_engine: AsyncEngine,
    body: dict,
    expected_objective: str,
    expected_red_lines: str,
):
    user_id = "u_v"
    meeting_id = "m_v"
    await _seed(migrated_engine, user_id, meeting_id)
    headers = {"X-User-Id": user_id}

    # Pre-populate so we can prove that missing fields become "" (not unchanged).
    await api_client.put(
        f"/api/meetings/{meeting_id}/playbook",
        headers=headers,
        json={
            "objective": "old goal",
            "red_lines": "old red lines",
        },
    )

    resp = await api_client.put(f"/api/meetings/{meeting_id}/playbook", headers=headers, json=body)
    assert resp.status_code == 200, resp.text
    persisted = resp.json()
    assert persisted["objective"] == expected_objective
    assert persisted["red_lines"] == expected_red_lines


@pytest.mark.asyncio
async def test_put_long_free_form_markdown_round_trips(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """A 10K-character markdown body persists byte-for-byte through PUT + GET."""
    await _seed(migrated_engine, "u_long", "m_long")
    headers = {"X-User-Id": "u_long"}
    body = "# Heading\n\n" + ("- bullet 中英 mixed line\n" * 500)
    assert len(body) > 10_000

    put_resp = await api_client.put(
        "/api/meetings/m_long/playbook",
        headers=headers,
        json={"free_form_markdown": body},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["free_form_markdown"] == body

    get_resp = await api_client.get("/api/meetings/m_long/playbook", headers=headers)
    assert get_resp.json()["free_form_markdown"] == body


@pytest.mark.asyncio
async def test_updated_at_advances_across_consecutive_puts(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    """Scenario: updated_at advances on each PUT."""
    await _seed(migrated_engine, "u_ts", "m_ts")
    headers = {"X-User-Id": "u_ts"}

    first = await api_client.put(
        "/api/meetings/m_ts/playbook", headers=headers, json={"objective": "v1"}
    )
    t1 = first.json()["updated_at"]

    await asyncio.sleep(0.01)

    second = await api_client.put(
        "/api/meetings/m_ts/playbook", headers=headers, json={"objective": "v2"}
    )
    t2 = second.json()["updated_at"]

    assert t2 > t1
