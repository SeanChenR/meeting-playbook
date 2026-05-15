"""PATCH /api/meetings/{id}/transcript_chunks/{chunk_id} tests — slice-16 task 5.1.

Six scenarios per spec:
  (a) valid text → 200 + DB row text_edited_at not NULL
  (b) body with speaker → 422 transcript_edit.immutable_field listing speaker
  (c) empty text → 422 transcript_edit.invalid_text
  (d) 10001-char text → 422 transcript_edit.invalid_text
  (e) non-owner → 403 transcript_edit.forbidden
  (f) chunk belongs to different meeting → 404 transcript_edit.chunk_not_found
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


async def _seed(engine: AsyncEngine, *, user_id: str, meeting_id: str, chunk_id: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                'INSERT INTO "user" (id, name, email, "emailVerified") '
                "VALUES (:id, :id, :email, true) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, scheduled_start_at, created_at
                )
                VALUES (:mid, :uid, 'T', 'C', 'M', now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
        await conn.execute(
            text(
                """
                INSERT INTO transcript_chunk (
                    id, meeting_id, speaker, text,
                    started_at, ended_at, asr_provider_used,
                    confidence, created_at
                )
                VALUES (
                    :cid, :mid, 'me', 'original',
                    now(), now() + interval '1 second',
                    'qwen3', 0.95, now()
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"cid": chunk_id, "mid": meeting_id},
        )


@pytest.mark.asyncio
async def test_a_valid_text_updates_and_stamps_text_edited_at(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed(migrated_engine, user_id="u_a", meeting_id="m_a", chunk_id="c_a")
    resp = await api_client.patch(
        "/api/meetings/m_a/transcript_chunks/c_a",
        headers={"X-User-Id": "u_a"},
        json={"text": "corrected"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "corrected"
    assert body["text_edited_at"] is not None

    async with migrated_engine.connect() as conn:
        edited_at = (
            await conn.execute(text("SELECT text_edited_at FROM transcript_chunk WHERE id = 'c_a'"))
        ).scalar_one()
    assert edited_at is not None


@pytest.mark.asyncio
async def test_b_speaker_in_body_rejected_as_immutable(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed(migrated_engine, user_id="u_b", meeting_id="m_b", chunk_id="c_b")
    resp = await api_client.patch(
        "/api/meetings/m_b/transcript_chunks/c_b",
        headers={"X-User-Id": "u_b"},
        json={"text": "ok", "speaker": "counterparty"},
    )
    assert resp.status_code == 422
    payload = resp.json()
    assert payload["error_code"] == "transcript_edit.immutable_field"
    assert "speaker" in payload["message"]


@pytest.mark.asyncio
async def test_c_empty_text_rejected(api_client: AsyncClient, migrated_engine: AsyncEngine):
    await _seed(migrated_engine, user_id="u_c", meeting_id="m_c", chunk_id="c_c")
    resp = await api_client.patch(
        "/api/meetings/m_c/transcript_chunks/c_c",
        headers={"X-User-Id": "u_c"},
        json={"text": ""},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "transcript_edit.invalid_text"


@pytest.mark.asyncio
async def test_d_overlong_text_rejected(api_client: AsyncClient, migrated_engine: AsyncEngine):
    await _seed(migrated_engine, user_id="u_d", meeting_id="m_d", chunk_id="c_d")
    resp = await api_client.patch(
        "/api/meetings/m_d/transcript_chunks/c_d",
        headers={"X-User-Id": "u_d"},
        json={"text": "x" * 10_001},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "transcript_edit.invalid_text"


@pytest.mark.asyncio
async def test_e_non_owner_forbidden(api_client: AsyncClient, migrated_engine: AsyncEngine):
    await _seed(migrated_engine, user_id="u_owner", meeting_id="m_e", chunk_id="c_e")
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                'INSERT INTO "user" (id, name, email, "emailVerified") '
                "VALUES ('u_attacker', 'A', 'a@x.test', true) "
                "ON CONFLICT (id) DO NOTHING"
            )
        )
    resp = await api_client.patch(
        "/api/meetings/m_e/transcript_chunks/c_e",
        headers={"X-User-Id": "u_attacker"},
        json={"text": "evil"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "transcript_edit.forbidden"


@pytest.mark.asyncio
async def test_f_chunk_in_wrong_meeting_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine
):
    await _seed(migrated_engine, user_id="u_f", meeting_id="m_f_real", chunk_id="c_f")
    resp = await api_client.patch(
        "/api/meetings/m_f_wrong/transcript_chunks/c_f",
        headers={"X-User-Id": "u_f"},
        json={"text": "test"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "transcript_edit.chunk_not_found"
