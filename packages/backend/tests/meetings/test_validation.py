"""Required-field validation matrix from spec slice-03-meeting-crud.

The spec example matrix maps each (body, status, error_code) tuple as the
agreed contract for what `POST /api/meetings` MUST return when a required
free-text field is missing or whitespace-only.

Per spec: every error_code is a structured `meeting.<field>.required` so the
frontend can resolve a localized message via the i18n key registry.
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


@pytest.fixture
async def _seed_user_v(migrated_engine: AsyncEngine):
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES ('user_v', 'V', 'v@example.com', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )


# Spec example matrix — each row is one parameterized test case.
_VALIDATION_CASES = [
    pytest.param(
        {"title": "", "counterparty_display_name": "林", "me_display_name": "Sean"},
        422,
        "meeting.title.required",
        id="empty-title",
    ),
    pytest.param(
        {"title": "Q3", "counterparty_display_name": "  ", "me_display_name": "Sean"},
        422,
        "meeting.counterparty_display_name.required",
        id="whitespace-counterparty",
    ),
    pytest.param(
        {"title": "Q3", "counterparty_display_name": "林", "me_display_name": ""},
        422,
        "meeting.me_display_name.required",
        id="empty-me",
    ),
    pytest.param(
        {"title": "Q3", "counterparty_display_name": "林", "me_display_name": "Sean"},
        201,
        None,
        id="happy-path",
    ),
]


@pytest.mark.parametrize("body,expected_status,expected_error_code", _VALIDATION_CASES)
@pytest.mark.asyncio
async def test_required_field_validation_matrix(
    api_client: AsyncClient,
    _seed_user_v: None,
    body: dict,
    expected_status: int,
    expected_error_code: str | None,
):
    resp = await api_client.post(
        "/api/meetings",
        headers={"X-User-Id": "user_v"},
        json=body,
    )
    assert resp.status_code == expected_status, resp.text
    if expected_error_code is not None:
        assert resp.json()["error_code"] == expected_error_code
    else:
        # Happy path: no error_code field; meeting body returned.
        assert "error_code" not in resp.json()
