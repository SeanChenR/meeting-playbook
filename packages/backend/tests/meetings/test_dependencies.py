"""FastAPI dependency for the application-wide AsyncSession factory.

Slice-08 added `get_session_factory_dependency` so handlers that spawn
parallel sub-tasks (e.g. the tactical advisor running concurrent with the
capture loop) can open isolated AsyncSessions per task rather than sharing
the single request-scoped session.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.meetings.dependencies import get_session_factory_dependency


@pytest.mark.asyncio
async def test_session_factory_dependency_yields_independent_sessions(monkeypatch):
    """Slice-08: two `factory()` invocations produce distinct AsyncSession instances."""
    # The factory is built lazily from get_settings(); make sure required env
    # vars exist (test conftest already sets DATABASE_URL via _migrated_db_url).
    factory = get_session_factory_dependency()
    s1 = factory()
    s2 = factory()
    assert s1 is not s2, "factory must yield distinct session instances per call"
    assert isinstance(s1, AsyncSession)
    assert isinstance(s2, AsyncSession)
    await s1.close()
    await s2.close()
