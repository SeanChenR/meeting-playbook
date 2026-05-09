"""TokenStore — Python ↔ gateway bridge for Calendar OAuth tokens.

Per slice-05 design + ADR-0027: the Better Auth `account` table is the
single source of truth for Google OAuth tokens. Python never reads that
table directly; instead it asks the Bun gateway through internal endpoints
that require an `X-Internal-Auth` shared secret.
"""

from __future__ import annotations

import os

import httpx


class CalendarNotConnected(Exception):
    """Raised when the user has not granted Calendar scope."""


class CalendarTokenExpired(Exception):
    """Raised when the stored refresh token can no longer be exchanged."""


class CalendarNetworkError(Exception):
    """Raised when the Calendar API call cannot reach Google."""


class TokenStore:
    """Asks the gateway for a user's Google access token (and triggers refresh).

    Args:
        base_url: Gateway internal-endpoint base URL. Defaults to
            BACKEND_INTERNAL_AUTH_URL env var.
        secret:   Shared secret for X-Internal-Auth. Defaults to
            BACKEND_INTERNAL_AUTH_SECRET env var.
        client:   Optional httpx.AsyncClient (injected for tests).
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        secret: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url or os.environ.get(
            "BACKEND_INTERNAL_AUTH_URL", "http://localhost:3001"
        )
        self._secret = secret or os.environ.get("BACKEND_INTERNAL_AUTH_SECRET", "")
        self._client = client

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Auth": self._secret}

    async def _do(self, method: str, path: str) -> httpx.Response:
        if self._client is not None:
            return await self._client.request(method, path, headers=self._headers)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
            return await client.request(method, path, headers=self._headers)

    async def get_access_token(self, user_id: str) -> dict:
        """Return {access_token, scope, expires_at} for the user; raise on failure."""
        resp = await self._do("GET", f"/__internal__/users/{user_id}/calendar-token")
        if resp.status_code == 404:
            raise CalendarNotConnected(
                "User has not granted Calendar scope or token row is missing."
            )
        if resp.status_code == 401:
            raise CalendarTokenExpired("Stored access token is no longer valid.")
        if resp.status_code >= 500 or resp.status_code != 200:
            raise CalendarNetworkError(
                f"Gateway internal token endpoint returned {resp.status_code}."
            )
        return resp.json()

    async def refresh(self, user_id: str) -> dict:
        """Trigger a server-side refresh; return the new {access_token, expires_at}."""
        resp = await self._do("POST", f"/__internal__/users/{user_id}/refresh-calendar-token")
        if resp.status_code == 401:
            raise CalendarTokenExpired(
                "Refresh token rejected by Google; user must reconnect Calendar."
            )
        if resp.status_code == 404:
            raise CalendarNotConnected("No refresh token stored for this user.")
        if resp.status_code != 200:
            raise CalendarNetworkError(f"Refresh endpoint returned {resp.status_code}.")
        return resp.json()
