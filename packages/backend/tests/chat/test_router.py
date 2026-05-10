"""Chat HTTP router tests — GET /api/meetings/{id}/chat_messages.

Per spec tactical-advisor ADDED requirement scenarios "Owner GET returns
chronological history" / "Non-owner GET returns 404 not_found" / "Empty
history returns 200 with empty array".
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


async def _seed_meeting_and_messages(
    db_url: str,
    *,
    user_id: str,
    meeting_id: str,
    pairs: list[tuple[str, str]],
) -> None:
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        await s.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"{user_id}@example.com"},
        )
        await s.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
                VALUES (:mid, :uid, 'T', 'C', 'M')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
        await s.commit()

        if pairs:
            from meeting_playbook.chat.repository import ChatMessageRepository

            repo = ChatMessageRepository(s)
            for user_content, advisor_content in pairs:
                await repo.insert_pair_after_advice(
                    meeting_id=meeting_id,
                    user_content=user_content,
                    advisor_content=advisor_content,
                )
    await engine.dispose()


async def _truncate(db_url: str):
    engine = create_async_engine(db_url, future=True)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "chat_message" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


def _build_client(db_url_sync: str) -> TestClient:
    db_url_async = _async_url(db_url_sync)
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    return TestClient(app)


def test_get_chat_messages_owner_returns_chronological_history(_migrated_db_url):
    """Slice-09: owner GET returns rows in created_at ASC with all 5 fields."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_meeting_and_messages(
            _async_url(_migrated_db_url),
            user_id="u_a",
            meeting_id="m_history",
            pairs=[("Q1", "A1"), ("Q2", "A2"), ("Q3", "A3")],
        )
    )

    client = _build_client(_migrated_db_url)
    r = client.get(
        "/api/meetings/m_history/chat_messages",
        headers={"X-User-Id": "u_a"},
    )

    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    # 3 pairs = 6 rows.
    assert len(data) == 6
    # Each row has exactly the 5 expected keys.
    for row in data:
        assert set(row.keys()) == {"id", "meeting_id", "role", "content", "created_at"}
    # Order is interleaved user/advisor by created_at ASC.
    assert [r["content"] for r in data] == ["Q1", "A1", "Q2", "A2", "Q3", "A3"]
    assert [r["role"] for r in data] == [
        "user",
        "advisor",
        "user",
        "advisor",
        "user",
        "advisor",
    ]


def test_get_chat_messages_non_owner_returns_404(_migrated_db_url):
    """Slice-09: cross-user GET returns 404 with the standard meeting.not_found envelope."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_meeting_and_messages(
            _async_url(_migrated_db_url),
            user_id="u_owner",
            meeting_id="m_private",
            pairs=[("Q", "A")],
        )
    )

    client = _build_client(_migrated_db_url)
    r = client.get(
        "/api/meetings/m_private/chat_messages",
        headers={"X-User-Id": "u_attacker"},
    )

    assert r.status_code == 404
    body = r.json()
    # Per server.py _http_exception_handler: HTTPException(detail={"error_code": ...})
    # is unwrapped into a flat envelope `{"error_code": ..., "message": ...}`.
    assert body["error_code"] == "meeting.not_found"


def test_get_chat_messages_empty_history_returns_empty_array(_migrated_db_url):
    """Slice-09: meeting with no chat history returns 200 + []."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_meeting_and_messages(
            _async_url(_migrated_db_url),
            user_id="u_b",
            meeting_id="m_empty",
            pairs=[],
        )
    )

    client = _build_client(_migrated_db_url)
    r = client.get(
        "/api/meetings/m_empty/chat_messages",
        headers={"X-User-Id": "u_b"},
    )

    assert r.status_code == 200
    assert r.json() == []


def test_get_chat_messages_missing_x_user_id_is_rejected(_migrated_db_url):
    """Slice-09: gateway-bypass — no X-User-Id header → 401 auth.gateway_bypass."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _seed_meeting_and_messages(
            _async_url(_migrated_db_url),
            user_id="u_x",
            meeting_id="m_x",
            pairs=[],
        )
    )

    client = _build_client(_migrated_db_url)
    r = client.get("/api/meetings/m_x/chat_messages")

    assert r.status_code == 401
    body = r.json()
    assert body["error_code"] == "auth.gateway_bypass"


# Silence the unused-import warning for `pytest` (used as a marker host elsewhere).
_ = pytest
