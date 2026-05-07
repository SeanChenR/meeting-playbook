"""Tests for the FastAPI error-envelope contract (AC-7, slice 2).

Per ADR-0022 + slice-02 design: every error response from FastAPI MUST
be a JSON object of shape `{"error_code": <snake.dot.code>, "message": <str>}`.

This file verifies:
    - Already-handled paths (`/api/me` missing header) honor the envelope.
    - Unhandled exceptions are wrapped in `common.internal_error`.
    - HTTPException raised by route code is wrapped, status preserved.
    - Validation errors are wrapped as `common.validation_error`.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from meeting_playbook.server import create_app


def _app_with_test_routes():
    app = create_app()

    @app.get("/api/_test/boom")
    async def _boom():
        raise RuntimeError("kaboom — simulated unhandled error")

    @app.get("/api/_test/forbidden")
    async def _forbidden():
        raise HTTPException(status_code=403, detail="nope")

    @app.get("/api/_test/needs-int")
    async def _needs_int(value: int):
        return {"got": value}

    return app


@pytest.fixture
def client() -> AsyncClient:
    # raise_app_exceptions=False so the FastAPI Exception handler runs
    # (otherwise ASGITransport re-raises the route's exception in the test).
    transport = ASGITransport(app=_app_with_test_routes(), raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_api_me_missing_header_uses_envelope(client: AsyncClient):
    async with client as c:
        response = await c.get("/api/me")

    assert response.status_code == 401
    body = response.json()
    assert set(body.keys()) >= {"error_code", "message"}
    assert body["error_code"] == "auth.gateway_bypass"


@pytest.mark.asyncio
async def test_unhandled_exception_returns_internal_error_envelope(client: AsyncClient):
    async with client as c:
        response = await c.get("/api/_test/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "common.internal_error"
    assert isinstance(body["message"], str) and body["message"]


@pytest.mark.asyncio
async def test_http_exception_wrapped_in_envelope_preserving_status(
    client: AsyncClient,
):
    async with client as c:
        response = await c.get("/api/_test/forbidden")

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "http.403"
    assert "nope" in body["message"]


@pytest.mark.asyncio
async def test_validation_error_returns_validation_envelope(client: AsyncClient):
    async with client as c:
        response = await c.get("/api/_test/needs-int", params={"value": "not-a-number"})

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "common.validation_error"
    assert isinstance(body["message"], str) and body["message"]
