"""FastAPI dependency providers for the meetings router.

`get_session_dependency` returns an AsyncSession bound to the application
engine. Tests override this to point at the test DB engine.

`get_user_id_dependency` extracts the gateway-injected `X-User-Id` header.
A missing header MUST yield the same `auth.gateway_bypass` envelope used by
`/api/me` (per ADR-0021 + slice-01 contract).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from meeting_playbook.config import get_settings


@lru_cache
def _engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.async_database_url, future=True)


@lru_cache
def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(_engine(), expire_on_commit=False)


async def get_session_dependency() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped AsyncSession."""
    Session = _sessionmaker()
    async with Session() as session:
        yield session


def get_user_id_dependency(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    """Return the gateway-injected user id, or 401 with auth.gateway_bypass if missing."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "auth.gateway_bypass",
                "message": (
                    "Missing X-User-Id header. This endpoint must be reached "
                    "through the auth gateway."
                ),
            },
        )
    return x_user_id
