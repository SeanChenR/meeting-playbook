"""CalendarClient — wraps Google Calendar API using TokenStore-supplied credentials.

Per spec slice-05-calendar-llm-playbook (calendar-integration):
- get_upcoming_events returns events sorted by start ascending
- handles pagination (follows pageToken)
- empty user calendar → empty list
- 401 from Google triggers TokenStore.refresh and one retry
- second 401 raises CalendarTokenExpired
- never-connected user raises CalendarNotConnected
- persistent 5xx raises CalendarNetworkError
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from meeting_playbook.calendar.client import (
    CalendarClient,
    CalendarEvent,
    CalendarNetworkError,
    CalendarNotConnected,
    CalendarTokenExpired,
)
from meeting_playbook.calendar.token_store import TokenStore


def _make_event_resource(event_id: str, summary: str, start_iso: str, attendees=None):
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": start_iso},
        "attendees": attendees or [],
        "description": "",
        "organizer": {"displayName": "Sean"},
    }


def _make_token_store(
    access_token="at_existing",
    scope="openid email profile https://www.googleapis.com/auth/calendar.events.readonly",
):
    """Build a TokenStore stub that returns a known token without hitting HTTP."""
    store = MagicMock(spec=TokenStore)

    async def _get(_user_id):
        return {"access_token": access_token, "scope": scope}

    async def _refresh(_user_id):
        return {"access_token": "at_refreshed", "scope": scope}

    store.get_access_token.side_effect = _get
    store.refresh.side_effect = _refresh
    return store


class _FakeEventsResource:
    """Mimics googleapiclient.discovery.build('calendar').events()."""

    def __init__(self, pages):
        # `pages` is a list of (items, nextPageToken | None) tuples.
        self._pages = pages
        self._call_index = 0

    def list(self, **_kwargs):
        return self  # `list().execute()` is the call shape we mock.

    def execute(self):
        if self._call_index >= len(self._pages):
            return {"items": [], "nextPageToken": None}
        items, next_token = self._pages[self._call_index]
        self._call_index += 1
        return {"items": items, "nextPageToken": next_token}


def _make_service(pages):
    """Stand in for googleapiclient.discovery.build(...) result."""
    events_resource = _FakeEventsResource(pages)
    service = MagicMock()
    service.events.return_value = events_resource
    return service


def _build_service_factory(pages):
    """A callable matching CalendarClient's `build_service` injection point."""

    def factory(_credentials):
        return _make_service(pages)

    return factory


@pytest.mark.asyncio
async def test_get_upcoming_events_returns_events_ordered_by_start():
    now = datetime.now(UTC)
    e1 = _make_event_resource("evt_1", "earlier", (now + timedelta(hours=1)).isoformat())
    e2 = _make_event_resource("evt_2", "later", (now + timedelta(hours=3)).isoformat())
    pages = [([e1, e2], None)]

    client = CalendarClient(
        token_store=_make_token_store(),
        build_service=_build_service_factory(pages),
    )

    events = await client.get_upcoming_events("u_alpha", hours=24)
    assert [e.id for e in events] == ["evt_1", "evt_2"]
    assert all(isinstance(e, CalendarEvent) for e in events)


@pytest.mark.asyncio
async def test_get_upcoming_events_follows_pagination_until_done():
    now = datetime.now(UTC)
    page1 = [
        _make_event_resource("evt_1", "p1a", (now + timedelta(hours=1)).isoformat()),
        _make_event_resource("evt_2", "p1b", (now + timedelta(hours=2)).isoformat()),
    ]
    page2 = [
        _make_event_resource("evt_3", "p2a", (now + timedelta(hours=3)).isoformat()),
        _make_event_resource("evt_4", "p2b", (now + timedelta(hours=4)).isoformat()),
    ]
    pages = [(page1, "page2_token"), (page2, None)]

    client = CalendarClient(
        token_store=_make_token_store(),
        build_service=_build_service_factory(pages),
    )

    events = await client.get_upcoming_events("u_alpha", hours=24)
    assert [e.id for e in events] == ["evt_1", "evt_2", "evt_3", "evt_4"]


@pytest.mark.asyncio
async def test_get_upcoming_events_returns_empty_when_calendar_is_empty():
    client = CalendarClient(
        token_store=_make_token_store(),
        build_service=_build_service_factory([([], None)]),
    )
    events = await client.get_upcoming_events("u_alpha", hours=24)
    assert events == []


@pytest.mark.asyncio
async def test_first_401_triggers_refresh_and_retries_once_successfully():
    """When the first events.list raises HttpError 401, the client refreshes the
    token via TokenStore.refresh, builds a new service with the new credentials,
    and retries once. The second attempt succeeds and returns events."""
    from googleapiclient.errors import HttpError

    now = datetime.now(UTC)
    success_pages = [
        (
            [
                _make_event_resource(
                    "evt_after_refresh", "ok", (now + timedelta(hours=1)).isoformat()
                )
            ],
            None,
        )
    ]

    token_store = _make_token_store()

    call_count = {"n": 0}

    def factory(_credentials):
        # First call: events.list → raises 401.
        # Second call: events.list → succeeds.
        if call_count["n"] == 0:
            call_count["n"] += 1
            service = MagicMock()
            resp = MagicMock(status=401, reason="Unauthorized")
            service.events().list.return_value.execute.side_effect = HttpError(
                resp=resp, content=b'{"error":"unauthorized"}'
            )
            return service
        return _make_service(success_pages)

    client = CalendarClient(token_store=token_store, build_service=factory)

    events = await client.get_upcoming_events("u_alpha", hours=24)
    assert [e.id for e in events] == ["evt_after_refresh"]
    token_store.refresh.assert_awaited_once_with("u_alpha")


@pytest.mark.asyncio
async def test_second_401_raises_calendar_token_expired():
    from googleapiclient.errors import HttpError

    token_store = _make_token_store()

    def factory(_credentials):
        service = MagicMock()
        resp = MagicMock(status=401, reason="Unauthorized")
        service.events().list.return_value.execute.side_effect = HttpError(
            resp=resp, content=b'{"error":"unauthorized"}'
        )
        return service

    client = CalendarClient(token_store=token_store, build_service=factory)

    with pytest.raises(CalendarTokenExpired):
        await client.get_upcoming_events("u_alpha", hours=24)


@pytest.mark.asyncio
async def test_never_connected_user_raises_calendar_not_connected():
    """TokenStore.get_access_token raising CalendarNotConnected propagates."""
    store = MagicMock(spec=TokenStore)

    async def _get(_user_id):
        raise CalendarNotConnected("never connected")

    store.get_access_token.side_effect = _get

    client = CalendarClient(token_store=store, build_service=lambda _c: _make_service([([], None)]))

    with pytest.raises(CalendarNotConnected):
        await client.get_upcoming_events("u_alpha", hours=24)


@pytest.mark.asyncio
async def test_persistent_5xx_raises_calendar_network_error():
    from googleapiclient.errors import HttpError

    token_store = _make_token_store()

    def factory(_credentials):
        service = MagicMock()
        resp = MagicMock(status=503, reason="Service Unavailable")
        service.events().list.return_value.execute.side_effect = HttpError(
            resp=resp, content=b'{"error":"unavailable"}'
        )
        return service

    client = CalendarClient(token_store=token_store, build_service=factory)

    with pytest.raises(CalendarNetworkError):
        await client.get_upcoming_events("u_alpha", hours=24)


# ─── Round-2 ingest: organizer_email field on CalendarEvent ────────────────


@pytest.mark.asyncio
async def test_event_from_resource_populates_organizer_email():
    """When Google returns organizer.email, CalendarEvent.organizer_email is set."""
    now = datetime.now(UTC)
    raw_event = {
        "id": "evt_org_email",
        "summary": "Demo",
        "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
        "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
        "attendees": [],
        "description": "",
        "organizer": {"email": "host@x.com", "displayName": "Host"},
    }

    client = CalendarClient(
        token_store=_make_token_store(),
        build_service=_build_service_factory([([raw_event], None)]),
    )
    events = await client.get_upcoming_events("u_alpha", hours=24)
    assert len(events) == 1
    assert events[0].organizer_email == "host@x.com"
    assert events[0].organizer == "Host"  # display unchanged


@pytest.mark.asyncio
async def test_event_from_resource_organizer_email_defaults_to_empty_when_absent():
    """Subscribed-calendar events sometimes omit organizer.email."""
    now = datetime.now(UTC)
    raw_event = {
        "id": "evt_no_org_email",
        "summary": "Subscribed",
        "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
        "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
        "attendees": [],
        "description": "",
        "organizer": {"displayName": "Course Bot"},  # no email key
    }

    client = CalendarClient(
        token_store=_make_token_store(),
        build_service=_build_service_factory([([raw_event], None)]),
    )
    events = await client.get_upcoming_events("u_alpha", hours=24)
    assert events[0].organizer_email == ""
    assert events[0].organizer == "Course Bot"


# ─── Slice 7 round 2: resource attendee filter ─────────────────────


@pytest.mark.asyncio
async def test_event_from_resource_drops_room_accounts():
    """Slice-7 round 2: meeting room attendees (resource: True) are filtered out."""
    now = datetime.now(UTC)
    raw_event = {
        "id": "evt_with_room",
        "summary": "Q3 review",
        "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
        "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
        "attendees": [
            {"email": "sean@x", "displayName": "Sean"},
            {
                "email": "c_xx@resource.calendar.google.com",
                "displayName": "MCTW - 6/F-6-龍貓 (3)",
                "resource": True,
            },
            {"email": "lin@x", "displayName": "林經理"},
        ],
        "description": "",
        "organizer": {"email": "sean@x", "displayName": "Sean"},
    }

    client = CalendarClient(
        token_store=_make_token_store(),
        build_service=_build_service_factory([([raw_event], None)]),
    )
    events = await client.get_upcoming_events("u_alpha", hours=24)

    assert len(events) == 1
    attendees = events[0].attendees
    assert len(attendees) == 2, f"expected 2 human attendees, got {attendees}"
    joined = " | ".join(attendees)
    assert "Sean" in joined
    assert "林經理" in joined
    assert "龍貓" not in joined
    assert "MCTW" not in joined


@pytest.mark.asyncio
async def test_event_from_resource_drops_attendees_via_email_suffix():
    """Slice-7 round 2: resource detected via @resource.calendar.google.com when no explicit flag."""
    now = datetime.now(UTC)
    raw_event = {
        "id": "evt_room_no_flag",
        "summary": "Standup",
        "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
        "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
        "attendees": [
            {"email": "sean@x", "displayName": "Sean"},
            {"email": "c_abc@resource.calendar.google.com", "displayName": "Some Room"},
        ],
        "description": "",
        "organizer": {"email": "sean@x", "displayName": "Sean"},
    }

    client = CalendarClient(
        token_store=_make_token_store(),
        build_service=_build_service_factory([([raw_event], None)]),
    )
    events = await client.get_upcoming_events("u_alpha", hours=24)
    attendees = events[0].attendees
    assert len(attendees) == 1
    assert "Sean" in attendees[0]
    assert "Some Room" not in " | ".join(attendees)


@pytest.mark.asyncio
async def test_event_from_resource_drops_attendees_via_resource_email_field():
    """Slice-7 round 2: resourceEmail field alone marks the entry as a resource."""
    now = datetime.now(UTC)
    raw_event = {
        "id": "evt_resource_email",
        "summary": "Demo",
        "start": {"dateTime": (now + timedelta(hours=1)).isoformat()},
        "end": {"dateTime": (now + timedelta(hours=2)).isoformat()},
        "attendees": [
            {"email": "lin@x", "displayName": "林經理"},
            {
                "email": "demo-room@x.com",
                "displayName": "Demo Room",
                "resourceEmail": "demo-room@x.com",
            },
        ],
        "description": "",
        "organizer": {"email": "sean@x", "displayName": "Sean"},
    }
    client = CalendarClient(
        token_store=_make_token_store(),
        build_service=_build_service_factory([([raw_event], None)]),
    )
    events = await client.get_upcoming_events("u_alpha", hours=24)
    attendees = events[0].attendees
    assert len(attendees) == 1
    assert "林經理" in attendees[0]
    assert "Demo Room" not in " | ".join(attendees)
