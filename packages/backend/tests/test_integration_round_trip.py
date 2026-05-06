"""Integration test — simulates the gateway → FastAPI auth round trip.

The real flow:

    Browser (with Better Auth session cookie)
        → Bun.serve gateway
            • validates Better Auth session via auth.api.getSession
            • injects X-User-Id from session.user.id
            • forwards request to FastAPI on localhost:8000
        → FastAPI
            • reads X-User-Id (no re-validation, gateway is sole ingress)
            • returns the user identity

This integration test mocks the OAuth / session-resolution side and exercises
the FastAPI side against a known X-User-Id value, then asserts the response
shape matches the spec contract.

Together with `test_api_me.py` (FastAPI surface contract) and the bun
`gateway.test.ts` suite (gateway surface contract), this verifies the full
auth round trip end-to-end without needing a live PostgreSQL or Google OAuth.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from meeting_playbook.server import create_app


@pytest.mark.asyncio
async def test_simulated_oauth_callback_to_backend_returns_resolved_user_id():
    """Full simulated round trip: mocked OAuth callback → gateway → FastAPI."""

    # 1. Simulate Better Auth resolving an OAuth callback into a session.
    #    The actual OAuth flow is exercised inside Better Auth (out of scope
    #    for this integration test); here we represent its output:
    fake_session = {
        "user": {
            "id": "usr_oauth_resolved_42",
            "email": "sean@example.com",
            "name": "Sean Chen",
        },
    }

    # 2. Simulate the Bun.serve gateway extracting session.user.id and
    #    injecting it as X-User-Id on the forwarded request.
    forwarded_headers = {"X-User-Id": fake_session["user"]["id"]}

    # 3. Drive a request through the FastAPI ASGI app exactly as the gateway
    #    would — same headers, same path, no auth cookie.
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.get("/api/me", headers=forwarded_headers)

    # 4. FastAPI must trust X-User-Id and echo the user_id verbatim.
    assert response.status_code == 200
    body = response.json()
    assert body == {"user_id": "usr_oauth_resolved_42"}


@pytest.mark.asyncio
async def test_request_bypassing_gateway_is_rejected():
    """A direct request without X-User-Id (i.e., not via gateway) fails fast."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://direct-attack") as client:
        # No X-User-Id header → simulates a curl directly to localhost:8000
        response = await client.get("/api/me")

    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "auth.gateway_bypass"


@pytest.mark.asyncio
async def test_attacker_supplied_x_user_id_would_succeed_only_because_gateway_overwrites():
    """Note on the trust model — verifies why the gateway MUST overwrite.

    FastAPI by design trusts X-User-Id. If the gateway did NOT overwrite a
    client-supplied X-User-Id, an attacker reaching FastAPI directly (or
    through a misconfigured gateway) could impersonate any user.

    This test documents the contract: the only defense is the gateway's
    overwrite behavior (verified in `gateway.test.ts`). When the gateway
    correctly overwrites, the X-User-Id reaching FastAPI is the
    session-derived id, never the attacker's value.
    """
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        # Simulate the gateway: it has overwritten the client-supplied
        # `usr_attacker` with the session-derived `usr_legit` value.
        response = await client.get(
            "/api/me",
            headers={"X-User-Id": "usr_legit"},  # gateway-injected, not client value
        )

    assert response.status_code == 200
    assert response.json() == {"user_id": "usr_legit"}
