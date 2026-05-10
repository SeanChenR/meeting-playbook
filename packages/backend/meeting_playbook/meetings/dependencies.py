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
from urllib.parse import unquote

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


def get_session_factory_dependency() -> async_sessionmaker[AsyncSession]:
    """Return the application-wide session factory.

    Slice-08: handlers that spawn parallel sub-tasks (e.g. the tactical
    advisor running concurrent with the capture/transcribe loop) MUST NOT
    share the request-scoped AsyncSession across coroutines — SQLAlchemy
    AsyncSession is not safe for concurrent use. Inject this dependency
    instead and open a fresh `async with session_factory() as ...` per task.
    """
    return _sessionmaker()


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


def get_user_name_dependency(
    x_user_name: Annotated[str | None, Header(alias="X-User-Name")] = None,
) -> str:
    """Return the gateway-injected user name (empty string when absent / blank).

    Slice 5 ingest: the gateway URL-encodes this header because HTTP headers
    reject non-ISO-8859-1 (user.name is often Chinese / Japanese / emoji).
    Decode here so endpoints see the original string.
    """
    return unquote(x_user_name) if x_user_name else ""


def get_user_email_dependency(
    x_user_email: Annotated[str | None, Header(alias="X-User-Email")] = None,
) -> str:
    """Return the gateway-injected user email (empty string when absent / blank).

    Decoded for symmetry with X-User-Name; emails are normally ASCII so the
    decode is a no-op, but staying consistent prevents subtle drift bugs.
    """
    return unquote(x_user_email) if x_user_email else ""
