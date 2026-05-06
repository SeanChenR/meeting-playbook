"""Tests for FastAPI gateway-trust endpoints — /api/health, /api/me.

Spec: `auth-gateway-contract` requirement
"FastAPI backend trusts X-User-Id without re-validation".
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from meeting_playbook.server import create_app


@pytest.fixture
def client() -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_health_returns_ok_without_auth(client: AsyncClient):
    """/api/health is a probe endpoint — no auth header required."""
    async with client as c:
        response = await c.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_me_returns_user_id_when_x_user_id_header_present(client: AsyncClient):
    """Spec: 'Request via gateway succeeds' — header → 200 with user_id body."""
    async with client as c:
        response = await c.get("/api/me", headers={"X-User-Id": "usr_abc123"})

    assert response.status_code == 200
    assert response.json() == {"user_id": "usr_abc123"}


@pytest.mark.asyncio
async def test_me_returns_401_when_x_user_id_header_missing(client: AsyncClient):
    """Spec: 'Direct request without header is rejected' — error_code identifies bypass."""
    async with client as c:
        response = await c.get("/api/me")

    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "auth.gateway_bypass"
    assert "message" in body


@pytest.mark.asyncio
async def test_me_returns_401_when_x_user_id_header_empty(client: AsyncClient):
    """Empty header value is treated the same as missing — still a bypass."""
    async with client as c:
        response = await c.get("/api/me", headers={"X-User-Id": ""})

    assert response.status_code == 401
    assert response.json()["error_code"] == "auth.gateway_bypass"


@pytest.mark.asyncio
async def test_me_preserves_user_id_value_verbatim(client: AsyncClient):
    """The header value is the user identifier — no transformation."""
    async with client as c:
        for uid in ("usr_legit", "user-with-dashes", "uuid-v4-12345-67890-abcdef"):
            response = await c.get("/api/me", headers={"X-User-Id": uid})
            assert response.status_code == 200
            assert response.json() == {"user_id": uid}
