"""Calendar REST endpoint tests.

Per spec slice-05-calendar-llm-playbook (calendar-integration):
- GET /api/calendar/upcoming returns events ordered by start asc; default
  hours=24, accepts 1..168
- Unauthenticated → 401 + auth.gateway_bypass
- Not-connected → 401 + calendar.not_connected
- Token expired → 401 + calendar.token_expired
- Persistent network error → 502 + calendar.network_error

Slice-20b updates:
- POST /api/meetings/from-calendar is removed → HTTP 410 +
  `calendar.import_endpoint_removed`. The replacement contract lives in
  `tests/meetings/test_create_with_calendar_and_attachments.py` for
  `POST /api/meetings` with calendar_event_id + attachments[].
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.calendar.client import (
    CalendarEvent,
    CalendarNetworkError,
    CalendarNotConnected,
    CalendarTokenExpired,
)
from meeting_playbook.calendar.dependencies import (
    get_calendar_client_dependency,
    get_playbook_generator_dependency,
)
from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


def _sample_event(event_id: str = "gcal_evt_42", title: str = "Q3 review") -> CalendarEvent:
    return CalendarEvent(
        id=event_id,
        title=title,
        start=datetime.now(UTC).isoformat(),
        end=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        attendees=["lin@acme.com", "sean@example.com"],
        description="quarterly review",
        organizer="Sean",
    )


class _StubCalendarClient:
    """Inject as override for `get_calendar_client_dependency` in tests."""

    def __init__(self, *, upcoming=None, get_event=None, error=None):
        self._upcoming = upcoming or []
        self._get_event = get_event
        self._error = error

    async def get_upcoming_events(self, _user_id: str, hours: int = 24):
        if self._error:
            raise self._error
        return list(self._upcoming)

    async def get_event(self, _user_id: str, event_id: str):
        if self._get_event:
            return await self._get_event(event_id)
        return _sample_event(event_id)


class _StubPlaybookGenerator:
    def __init__(self, *, draft=None, error=None):
        self._draft = draft or {
            "free_form_markdown": "# Brief\n\nline 2\n\nline 3",
            "objective": "obj",
            "counterparty_profile": "cp",
            "anticipated_topics": "topics",
            "anticipated_objections": "objections",
            "talking_points": "tps",
            "red_lines": "rl",
        }
        self._error = error
        # Round-2 ingest: record the viewer args the router passed in.
        self.calls: list[dict] = []

    async def generate(
        self,
        event: CalendarEvent,
        *,
        viewer_email: str,
        viewer_name: str,
    ):
        self.calls.append(
            {"event": event, "viewer_email": viewer_email, "viewer_name": viewer_name}
        )
        if self._error:
            raise self._error
        return self._draft


@pytest_asyncio.fixture
async def api_client_factory(migrated_engine: AsyncEngine):
    """Factory that builds an AsyncClient with custom calendar / generator stubs."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    def _make_client(*, calendar_client, playbook_generator):
        app = create_app()
        app.dependency_overrides[get_session_dependency] = _override_session
        app.dependency_overrides[get_calendar_client_dependency] = lambda: calendar_client
        app.dependency_overrides[get_playbook_generator_dependency] = lambda: playbook_generator
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


@pytest.mark.asyncio
async def test_upcoming_returns_200_with_events(api_client_factory, migrated_engine):
    await _seed_user(migrated_engine, "u_alpha")
    cal = _StubCalendarClient(upcoming=[_sample_event("e1"), _sample_event("e2", "later")])
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.get(
            "/api/calendar/upcoming?hours=24",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert {e["id"] for e in body} == {"e1", "e2"}


@pytest.mark.asyncio
async def test_upcoming_without_x_user_id_is_rejected(api_client_factory, migrated_engine):
    cal = _StubCalendarClient()
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.get("/api/calendar/upcoming?hours=24")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "auth.gateway_bypass"


@pytest.mark.asyncio
async def test_upcoming_not_connected_returns_401_calendar_not_connected(
    api_client_factory, migrated_engine
):
    await _seed_user(migrated_engine, "u_alpha")
    cal = _StubCalendarClient(error=CalendarNotConnected("never connected"))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.get(
            "/api/calendar/upcoming?hours=24",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "calendar.not_connected"


@pytest.mark.asyncio
async def test_upcoming_token_expired_returns_401_calendar_token_expired(
    api_client_factory, migrated_engine
):
    await _seed_user(migrated_engine, "u_alpha")
    cal = _StubCalendarClient(error=CalendarTokenExpired("expired"))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.get(
            "/api/calendar/upcoming?hours=24",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "calendar.token_expired"


@pytest.mark.asyncio
async def test_upcoming_network_error_returns_502_calendar_network_error(
    api_client_factory, migrated_engine
):
    await _seed_user(migrated_engine, "u_alpha")
    cal = _StubCalendarClient(error=CalendarNetworkError("503 from google"))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.get(
            "/api/calendar/upcoming?hours=24",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 502
    assert resp.json()["error_code"] == "calendar.network_error"


# ─── POST /api/meetings/from-calendar — slice-20b REMOVED ──────────────────
#
# Slice-20b moves the calendar-import flow from a single fire-and-forget
# POST to a preview-and-confirm flow rooted at
# `/meetings/new?from_calendar=<event_id>`. The legacy endpoint is retained
# only as an HTTP 410 deprecation surface (per meeting-management ADDED
# requirement "POST /api/meetings/from-calendar is removed and returns
# HTTP 410 Gone" + calendar-integration REMOVED requirement). The
# replacement contract — meeting create + Playbook generation in one
# request — lives in `tests/meetings/test_create_with_calendar_and_attachments.py`.


@pytest.mark.asyncio
async def test_from_calendar_returns_410_on_any_body(api_client_factory, migrated_engine):
    """Scenario: Calling the legacy endpoint returns HTTP 410.

    Spec: every request, regardless of body or auth state, MUST return 410
    with `error_code: calendar.import_endpoint_removed`.
    """
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(_sample_event(_eid)))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={"X-User-Id": "u_import"},
            json={"event_id": "gcal_evt_42"},
        )
    assert resp.status_code == 410, resp.text
    assert resp.json()["error_code"] == "calendar.import_endpoint_removed"


@pytest.mark.asyncio
async def test_from_calendar_410_without_auth_or_body(api_client_factory, migrated_engine):
    """Spec: 410 emitted regardless of body content or authentication state.

    The handler declares NO request dependencies (no body, no session) so the
    response is identical whether the caller has X-User-Id or not.
    """
    cal = _StubCalendarClient()
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post("/api/meetings/from-calendar")
    assert resp.status_code == 410
    assert resp.json()["error_code"] == "calendar.import_endpoint_removed"


@pytest.mark.asyncio
async def test_from_calendar_never_creates_a_meeting_or_invokes_generator(
    api_client_factory, migrated_engine
):
    """Scenario: Legacy endpoint never creates a meeting.

    The handler MUST NOT touch the DB and MUST NOT call the generator,
    regardless of request body. Verified via a generator stub that raises
    on any invocation + a post-call DB scan for new meeting rows.
    """
    await _seed_user(migrated_engine, "u_dead_path")

    class _ExplodingGenerator:
        async def generate(self, *args, **kwargs):
            raise AssertionError(
                "Playbook generator MUST NOT be invoked by the legacy "
                "from-calendar endpoint after slice-20b."
            )

    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(_sample_event(_eid)))
    async with api_client_factory(
        calendar_client=cal, playbook_generator=_ExplodingGenerator()
    ) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={"X-User-Id": "u_dead_path"},
            json={"event_id": "gcal_evt_42"},
        )
    assert resp.status_code == 410

    # No meeting row was created as a side effect of this request.
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id FROM meeting WHERE user_id = :uid"),
            {"uid": "u_dead_path"},
        )
        assert rows.first() is None


# ─── helpers ────────────────────────────────────────────────────────────────


async def _async_return(value):
    return value
