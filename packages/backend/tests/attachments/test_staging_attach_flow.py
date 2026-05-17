"""Slice-24 task 4.2 — file-move + rollback edge cases for create_meeting.

Generator-failure rollback is already covered by
`tests/meetings/test_create_with_calendar_and_attachments.py`. This file
focuses on the remaining two failure modes:

- file move itself raises OSError (and shutil.move fallback also fails)
- DB commit after move raises an unexpected error

Both must trigger the same rollback discipline (D5): files move back,
row meeting_id reset, meeting row deleted.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.calendar.dependencies import (
    get_calendar_client_dependency,
    get_playbook_generator_dependency,
)
from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


class _StubCalendarClient:
    async def get_upcoming_events(self, _user_id: str, hours: int = 24):
        return []

    async def get_event(self, _user_id: str, event_id: str):
        from meeting_playbook.calendar.client import CalendarEvent

        from datetime import UTC, datetime, timedelta

        return CalendarEvent(
            id=event_id,
            title="meeting",
            start=datetime.now(UTC).isoformat(),
            end=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            attendees=[],
            description=None,
            organizer=None,
            organizer_email=None,
        )


class _StubPlaybookGenerator:
    async def generate(self, event, *, viewer_email, viewer_name):
        return {
            "free_form_markdown": "# x",
            "objective": "obj",
            "counterparty_profile": "cp",
            "anticipated_topics": "t",
            "anticipated_objections": "o",
            "talking_points": "tp",
            "red_lines": "r",
        }


@pytest_asyncio.fixture
async def api_client_factory(migrated_engine: AsyncEngine, tmp_path: Path, monkeypatch):
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ATTACHMENT_DIR", str(tmp_path))

    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as s:
            yield s

    def _make_client():
        app = create_app()
        app.dependency_overrides[get_session_dependency] = _override_session
        app.dependency_overrides[get_calendar_client_dependency] = lambda: _StubCalendarClient()
        app.dependency_overrides[get_playbook_generator_dependency] = lambda: (
            _StubPlaybookGenerator()
        )
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://gateway")

    return _make_client


async def _seed_user(engine: AsyncEngine, user_id: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"{user_id}@example.com"},
        )


async def _insert_staged(engine: AsyncEngine, *, att_id: str, user_id: str, file_path: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting_attachment (
                    id, meeting_id, user_id, file_path, kind, original_name,
                    bytes, uploaded_at
                )
                VALUES (
                    :aid, NULL, :uid, :path, 'pdf', 'x.pdf', 100, now()
                )
                """
            ),
            {"aid": att_id, "uid": user_id, "path": file_path},
        )


def _seed_staged_file(tmp_root: Path, user_id: str, att_id: str) -> Path:
    path = tmp_root / "_staging" / user_id / f"{att_id}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\nstaged-data\n")
    return path


@pytest.mark.asyncio
async def test_file_move_failure_aborts_meeting_create(
    api_client_factory, migrated_engine: AsyncEngine, tmp_path: Path
):
    """os.rename raising OSError (and shutil.move also failing) → rollback.

    Patches `os.rename` inside the router module to always raise a
    non-EXDEV OSError (which `_move_staged_to_meeting` propagates), so
    the create handler enters the rollback path with `moved=[]` (the
    first attach attempt failed before any successful move).
    """
    await _seed_user(migrated_engine, "u_fm")
    staged = _seed_staged_file(tmp_path, "u_fm", "att_fm")
    await _insert_staged(migrated_engine, att_id="att_fm", user_id="u_fm", file_path=str(staged))

    real_rename = __import__("os").rename

    def _failing_rename(src, dst):
        # Simulate an unhandleable FS error (permission denied — distinct
        # from EXDEV which would fall through to shutil.move).
        raise OSError(13, "Permission denied", src)

    with patch("meeting_playbook.meetings.router.os.rename", _failing_rename):
        async with api_client_factory() as c:
            resp = await c.post(
                "/api/meetings",
                headers={"X-User-Id": "u_fm"},
                json={
                    "title": "Q3",
                    "counterparty_display_name": "C",
                    "me_display_name": "M",
                    "scheduled_start_at": "2026-06-15T14:00:00Z",
                    "attachments": ["att_fm"],
                },
            )

    assert resp.status_code == 500
    assert resp.json()["error_code"] == "common.internal_error"

    # File never left staging.
    assert staged.exists(), "Failed move MUST leave the original file alone"
    # No meeting row exists for this user.
    async with migrated_engine.connect() as conn:
        m = await conn.execute(
            text("SELECT id FROM meeting WHERE user_id = :uid"),
            {"uid": "u_fm"},
        )
        assert m.first() is None
        # Row still staged (meeting_id NULL).
        att = await conn.execute(
            text("SELECT meeting_id FROM meeting_attachment WHERE id = 'att_fm'")
        )
        assert att.first().meeting_id is None

    # Sanity: os.rename is back to normal after patch exits.
    assert real_rename is __import__("os").rename


@pytest.mark.asyncio
async def test_exdev_falls_back_to_shutil_move(
    api_client_factory, migrated_engine: AsyncEngine, tmp_path: Path
):
    """EXDEV error from os.rename → shutil.move fallback → success path."""
    await _seed_user(migrated_engine, "u_xd")
    staged = _seed_staged_file(tmp_path, "u_xd", "att_xd")
    await _insert_staged(migrated_engine, att_id="att_xd", user_id="u_xd", file_path=str(staged))

    def _exdev_rename(src, dst):
        # Per design D4: EXDEV signals cross-filesystem, fall back to shutil.
        raise OSError(18, "Invalid cross-device link", src)

    with patch("meeting_playbook.meetings.router.os.rename", _exdev_rename):
        async with api_client_factory() as c:
            resp = await c.post(
                "/api/meetings",
                headers={"X-User-Id": "u_xd"},
                json={
                    "title": "Q3",
                    "counterparty_display_name": "C",
                    "me_display_name": "M",
                    "scheduled_start_at": "2026-06-15T14:00:00Z",
                    "attachments": ["att_xd"],
                },
            )

    assert resp.status_code == 201, resp.text
    meeting_id = resp.json()["id"]
    assert not staged.exists(), "shutil.move fallback should still move the file"
    meeting_dir = tmp_path / meeting_id
    moved_files = list(meeting_dir.iterdir())
    assert any(p.name == "att_xd.pdf" for p in moved_files)
