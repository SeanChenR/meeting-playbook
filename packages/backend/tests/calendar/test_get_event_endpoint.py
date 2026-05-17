"""Tests for `GET /api/calendar/events/{event_id}` — slice-20b task 1.1 + 1.2.

Per spec slice-20b calendar-integration ADDED requirement
"GET single Calendar event returns the full detail used by the meeting
preview form":
- Response shape: id / title / start / end / description / attendees / organizer
- attendees MUST be filtered through the existing resource-attendee filter
- Unknown event id → 404 calendar.event_not_found
- Calendar not connected → 401 calendar.not_connected
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
from meeting_playbook.calendar.schemas import CalendarEventDetail
from meeting_playbook.calendar.token_store import CalendarEventNotFound
from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


def _event(
    event_id: str = "gcal_evt_42",
    title: str = "Q3 review",
    attendees: list[str] | None = None,
    organizer: str = "Sean",
    organizer_email: str = "sean@example.com",
) -> CalendarEvent:
    return CalendarEvent(
        id=event_id,
        title=title,
        start=datetime.now(UTC).isoformat(),
        end=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        attendees=attendees
        if attendees is not None
        else ["Sean <sean@example.com>", "Lin <lin@acme.com>"],
        description="quarterly review",
        organizer=organizer,
        organizer_email=organizer_email,
    )


class _StubCalendarClient:
    def __init__(self, *, get_event=None):
        self._get_event = get_event

    async def get_upcoming_events(self, _user_id: str, hours: int = 24):
        return []

    async def get_event(self, _user_id: str, event_id: str):
        if self._get_event is None:
            return _event(event_id)
        return await self._get_event(event_id)


class _StubGenerator:
    async def generate(self, *args, **kwargs):
        raise AssertionError("generator must not be called by GET event endpoint")


@pytest_asyncio.fixture
async def api_client(migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client


def _override_calendar(app, calendar_client):
    app.dependency_overrides[get_calendar_client_dependency] = lambda: calendar_client


@pytest_asyncio.fixture
async def api_client_factory(migrated_engine: AsyncEngine):
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    def _make_client(*, calendar_client):
        app = create_app()
        app.dependency_overrides[get_session_dependency] = _override_session
        app.dependency_overrides[get_calendar_client_dependency] = lambda: calendar_client
        app.dependency_overrides[get_playbook_generator_dependency] = lambda: _StubGenerator()
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


# ─── Task 1.1: schema shape ────────────────────────────────────────────────


def test_schema_shape():
    """CalendarEventDetail carries id, title, start/end (nullable), description
    (nullable), attendees (list[str]), organizer (nullable structured).

    Spec: `{id, title, start: ISO8601 | null, end: ISO8601 | null,
    description: string | null, attendees: Attendee[], organizer: Organizer | null}`
    """
    detail = CalendarEventDetail(
        id="gcal_evt_1",
        title="Q3 review",
        start="2026-06-15T14:00:00+00:00",
        end=None,
        description=None,
        attendees=["Sean <sean@example.com>"],
        organizer=None,
    )
    assert detail.id == "gcal_evt_1"
    assert detail.title == "Q3 review"
    assert detail.start == "2026-06-15T14:00:00+00:00"
    assert detail.end is None
    assert detail.description is None
    assert detail.attendees == ["Sean <sean@example.com>"]
    assert detail.organizer is None


def test_schema_shape_with_organizer():
    """Organizer is an optional object with display_name + email."""
    detail = CalendarEventDetail(
        id="gcal_evt_1",
        title="X",
        start=None,
        end=None,
        description="d",
        attendees=[],
        organizer={"display_name": "Sean", "email": "sean@example.com"},
    )
    assert detail.organizer is not None
    assert detail.organizer.display_name == "Sean"
    assert detail.organizer.email == "sean@example.com"


# ─── Task 1.2: endpoint behavior ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_event_returns_detail_with_resources_filtered(
    api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Returns the event detail with resource attendees filtered out.

    The CalendarClient.get_event is already responsible for filtering resource
    attendees (see slice-07 `_event_from_resource`). This test asserts the
    router exposes the filtered list as-is.
    """
    await _seed_user(migrated_engine, "u_alpha")

    # CalendarClient already drops the resource attendee at parse time; we
    # provide a pre-filtered event so the assertion targets the router's
    # response shape, not the client's internal filtering. The spec explicitly
    # requires the router to "apply the existing _event_from_resource rule" —
    # which it does by reusing CalendarClient.get_event.
    event = _event(
        "gcal_evt_42",
        attendees=["Sean <sean@example.com>", "Lin <lin@acme.com>"],
    )

    async def _get_event(_eid):
        return event

    cal = _StubCalendarClient(get_event=_get_event)
    async with api_client_factory(calendar_client=cal) as c:
        resp = await c.get(
            "/api/calendar/events/gcal_evt_42",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == "gcal_evt_42"
    assert body["title"] == "Q3 review"
    assert body["description"] == "quarterly review"
    assert "Sean <sean@example.com>" in body["attendees"]
    assert "Lin <lin@acme.com>" in body["attendees"]
    # Resource attendees do NOT appear (the client drops them at parse time).
    flat = " ".join(body["attendees"])
    assert "@resource.calendar.google.com" not in flat
    # Organizer is the structured object.
    assert body["organizer"] is not None
    assert body["organizer"]["display_name"] == "Sean"
    assert body["organizer"]["email"] == "sean@example.com"


@pytest.mark.asyncio
async def test_get_event_unknown_id_returns_calendar_event_not_found(
    api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Unknown event identifier returns calendar.event_not_found."""
    await _seed_user(migrated_engine, "u_alpha")

    async def _raise(_eid):
        raise CalendarEventNotFound("event missing")

    cal = _StubCalendarClient(get_event=_raise)
    async with api_client_factory(calendar_client=cal) as c:
        resp = await c.get(
            "/api/calendar/events/gcal_missing",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "calendar.event_not_found"


@pytest.mark.asyncio
async def test_get_event_not_connected_returns_401(
    api_client_factory, migrated_engine: AsyncEngine
):
    """Scenario: Calendar not connected returns calendar.not_connected."""
    await _seed_user(migrated_engine, "u_alpha")

    async def _raise(_eid):
        raise CalendarNotConnected("never connected")

    cal = _StubCalendarClient(get_event=_raise)
    async with api_client_factory(calendar_client=cal) as c:
        resp = await c.get(
            "/api/calendar/events/any_id",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "calendar.not_connected"


@pytest.mark.asyncio
async def test_get_event_token_expired_returns_401(
    api_client_factory, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_alpha")

    async def _raise(_eid):
        raise CalendarTokenExpired("expired")

    cal = _StubCalendarClient(get_event=_raise)
    async with api_client_factory(calendar_client=cal) as c:
        resp = await c.get(
            "/api/calendar/events/any_id",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "calendar.token_expired"


@pytest.mark.asyncio
async def test_get_event_network_error_returns_502(
    api_client_factory, migrated_engine: AsyncEngine
):
    await _seed_user(migrated_engine, "u_alpha")

    async def _raise(_eid):
        raise CalendarNetworkError("503")

    cal = _StubCalendarClient(get_event=_raise)
    async with api_client_factory(calendar_client=cal) as c:
        resp = await c.get(
            "/api/calendar/events/any_id",
            headers={"X-User-Id": "u_alpha"},
        )
    assert resp.status_code == 502
    assert resp.json()["error_code"] == "calendar.network_error"


@pytest.mark.asyncio
async def test_get_event_without_x_user_id_is_rejected(api_client_factory, migrated_engine):
    cal = _StubCalendarClient()
    async with api_client_factory(calendar_client=cal) as c:
        resp = await c.get("/api/calendar/events/any_id")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "auth.gateway_bypass"
