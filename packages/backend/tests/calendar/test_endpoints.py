"""Calendar REST endpoint tests.

Per spec slice-05-calendar-llm-playbook (calendar-integration):
- GET /api/calendar/upcoming returns events ordered by start asc; default
  hours=24, accepts 1..168
- Unauthenticated → 401 + auth.gateway_bypass
- Not-connected → 401 + calendar.not_connected
- Token expired → 401 + calendar.token_expired
- Persistent network error → 502 + calendar.network_error
- POST /api/meetings/from-calendar creates meeting + persists generated
  playbook; generator timeout leaves meeting and surfaces 504
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
from meeting_playbook.playbook_generation.generator import (
    PlaybookGenerationTimeout,
)
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


# ─── POST /api/meetings/from-calendar ───────────────────────────────────────


@pytest.mark.asyncio
async def test_from_calendar_creates_meeting_and_persists_generated_playbook(
    api_client_factory, migrated_engine
):
    await _seed_user(migrated_engine, "u_import")
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(_sample_event(_eid)))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={"X-User-Id": "u_import"},
            json={"event_id": "gcal_evt_42"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["meeting_id"].startswith("m_")

    # Verify the meeting + playbook persisted with calendar_event_id set.
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT calendar_event_id FROM meeting WHERE id = :mid"),
            {"mid": body["meeting_id"]},
        )
        meeting = rows.first()
        assert meeting is not None
        assert meeting.calendar_event_id == "gcal_evt_42"

        pb_rows = await conn.execute(
            text("SELECT objective, free_form_markdown FROM playbook WHERE meeting_id = :mid"),
            {"mid": body["meeting_id"]},
        )
        pb = pb_rows.first()
        assert pb is not None
        assert pb.objective == "obj"
        assert "Brief" in pb.free_form_markdown


@pytest.mark.asyncio
async def test_from_calendar_generator_timeout_persists_meeting_returns_504(
    api_client_factory, migrated_engine
):
    await _seed_user(migrated_engine, "u_timeout")
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(_sample_event(_eid)))
    gen = _StubPlaybookGenerator(error=PlaybookGenerationTimeout("60s"))
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={"X-User-Id": "u_timeout"},
            json={"event_id": "gcal_evt_timeout"},
        )
    assert resp.status_code == 504
    assert resp.json()["error_code"] == "playbook.generation_timeout"

    # Meeting MUST persist (per spec — recoverable through manual editor).
    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id FROM meeting WHERE calendar_event_id = :ceid AND user_id = :uid"),
            {"ceid": "gcal_evt_timeout", "uid": "u_timeout"},
        )
        assert rows.first() is not None


@pytest.mark.asyncio
async def test_from_calendar_event_lookup_failure_surfaces_calendar_error(
    api_client_factory, migrated_engine
):
    """Cross-user / unknown event id surfaces a Calendar-domain error code."""
    await _seed_user(migrated_engine, "u_other")

    async def _raise(_eid):
        raise CalendarNotConnected("event not visible to this user")

    cal = _StubCalendarClient(get_event=_raise)
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={"X-User-Id": "u_other"},
            json={"event_id": "gcal_evt_someone_elses"},
        )
    assert resp.status_code == 401
    body = resp.json()
    assert body["error_code"] == "calendar.not_connected"
    flat = str(body).lower()
    assert "someone_elses" not in flat


# ─── Slice-05 ingest: display-name derivation from session + attendees ─────


def _multi_attendee_event(event_id: str, attendees, organizer="", title="T") -> CalendarEvent:
    return CalendarEvent(
        id=event_id,
        title=title,
        start=datetime.now(UTC).isoformat(),
        end=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        attendees=list(attendees),
        description="",
        organizer=organizer,
    )


@pytest.mark.asyncio
async def test_from_calendar_picks_other_attendee_as_counterparty(
    api_client_factory, migrated_engine
):
    """Multi-attendee event: counterparty = first attendee whose email != X-User-Email."""
    await _seed_user(migrated_engine, "u_pick")

    event = _multi_attendee_event(
        "gcal_evt_multi",
        attendees=["angus@example.com", "Lin Manager <lin@acme.com>"],
        organizer="ignored",
    )
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(event))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={
                "X-User-Id": "u_pick",
                "X-User-Name": "Angus Chen",
                "X-User-Email": "angus@example.com",
            },
            json={"event_id": "gcal_evt_multi"},
        )
    assert resp.status_code == 201, resp.text
    meeting_id = resp.json()["meeting_id"]

    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT counterparty_display_name, me_display_name FROM meeting WHERE id = :mid"),
            {"mid": meeting_id},
        )
        row = rows.first()
        assert row is not None
        assert row.counterparty_display_name == "Lin Manager"
        # Tested separately below, but confirm it's NOT the literal "Me".
        assert row.me_display_name == "Angus Chen"


@pytest.mark.asyncio
async def test_from_calendar_falls_back_to_organizer_when_no_other_attendee(
    api_client_factory, migrated_engine
):
    await _seed_user(migrated_engine, "u_solo")
    event = _multi_attendee_event(
        "gcal_evt_solo",
        attendees=["solo@example.com"],
        organizer="Sean (work)",
        title="ignored",
    )
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(event))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={
                "X-User-Id": "u_solo",
                "X-User-Name": "Solo User",
                "X-User-Email": "solo@example.com",
            },
            json={"event_id": "gcal_evt_solo"},
        )
    assert resp.status_code == 201
    meeting_id = resp.json()["meeting_id"]

    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT counterparty_display_name FROM meeting WHERE id = :mid"),
            {"mid": meeting_id},
        )
        assert rows.first().counterparty_display_name == "Sean (work)"


@pytest.mark.asyncio
async def test_from_calendar_falls_back_to_title_when_no_organizer_either(
    api_client_factory, migrated_engine
):
    await _seed_user(migrated_engine, "u_title")
    event = _multi_attendee_event(
        "gcal_evt_title",
        attendees=["title@example.com"],
        organizer="",
        title="Live Session 2",
    )
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(event))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={
                "X-User-Id": "u_title",
                "X-User-Name": "Title User",
                "X-User-Email": "title@example.com",
            },
            json={"event_id": "gcal_evt_title"},
        )
    assert resp.status_code == 201
    meeting_id = resp.json()["meeting_id"]

    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT counterparty_display_name FROM meeting WHERE id = :mid"),
            {"mid": meeting_id},
        )
        assert rows.first().counterparty_display_name == "Live Session 2"


@pytest.mark.asyncio
async def test_from_calendar_me_display_name_is_taken_from_x_user_name_not_literal_me(
    api_client_factory, migrated_engine
):
    await _seed_user(migrated_engine, "u_name")
    event = _multi_attendee_event(
        "gcal_evt_name",
        attendees=["someone@x.com"],
        organizer="ignored",
    )
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(event))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={
                "X-User-Id": "u_name",
                "X-User-Name": "Sean Chen",
                "X-User-Email": "name@example.com",
            },
            json={"event_id": "gcal_evt_name"},
        )
    assert resp.status_code == 201
    meeting_id = resp.json()["meeting_id"]

    async with migrated_engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT me_display_name FROM meeting WHERE id = :mid"),
            {"mid": meeting_id},
        )
        row = rows.first()
        assert row is not None
        assert row.me_display_name == "Sean Chen"
        assert row.me_display_name != "Me"


# ─── Round-2 ingest: viewer perspective forwarded into generator ──────────


@pytest.mark.asyncio
async def test_from_calendar_passes_viewer_email_and_name_into_generator(
    api_client_factory, migrated_engine
):
    """Router MUST forward X-User-Email + X-User-Name into the generator."""
    await _seed_user(migrated_engine, "u_viewer")
    event = _multi_attendee_event(
        "gcal_evt_viewer",
        attendees=["viewer@example.com", "Lin <lin@acme.com>"],
        organizer="ignored",
    )
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(event))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={
                "X-User-Id": "u_viewer",
                "X-User-Name": "Viewer Person",
                "X-User-Email": "viewer@example.com",
            },
            json={"event_id": "gcal_evt_viewer"},
        )
    assert resp.status_code == 201, resp.text
    assert len(gen.calls) == 1
    assert gen.calls[0]["viewer_email"] == "viewer@example.com"
    assert gen.calls[0]["viewer_name"] == "Viewer Person"


@pytest.mark.asyncio
async def test_from_calendar_external_viewer_role_imports_successfully(
    api_client_factory, migrated_engine
):
    """Subscribed-calendar event (viewer is neither organizer nor attendee)
    still imports; generator receives the viewer args and produces a draft."""
    await _seed_user(migrated_engine, "u_ext")
    event = CalendarEvent(
        id="gcal_evt_external",
        title="實戰營 Live Session",
        start=datetime.now(UTC).isoformat(),
        end=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        attendees=["instructor@course.com"],
        description="course session",
        organizer="Course Bot",
        organizer_email="bot@course.com",
    )
    cal = _StubCalendarClient(get_event=lambda _eid: _async_return(event))
    gen = _StubPlaybookGenerator()
    async with api_client_factory(calendar_client=cal, playbook_generator=gen) as c:
        resp = await c.post(
            "/api/meetings/from-calendar",
            headers={
                "X-User-Id": "u_ext",
                "X-User-Name": "Subscriber",
                "X-User-Email": "subscriber@x.com",
            },
            json={"event_id": "gcal_evt_external"},
        )
    assert resp.status_code == 201
    assert gen.calls[0]["viewer_email"] == "subscriber@x.com"


# ─── helpers ────────────────────────────────────────────────────────────────


async def _async_return(value):
    return value
