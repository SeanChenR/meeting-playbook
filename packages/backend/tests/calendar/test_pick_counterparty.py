"""Pure-function tests for `pick_counterparty(event, user_email) -> str`.

Per spec slice-05 ingest (calendar-integration MODIFIED requirement
"POST from-calendar derives display names from session identity and
attendee filtering"):

- Filter attendees whose email == user_email (case-insensitive, trimmed)
- Pick first remaining attendee; display = displayName OR email-local-part
- Fallback chain: organizer → title → "Calendar event"
"""

from __future__ import annotations

import pytest

from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.calendar.identity import pick_counterparty


def _event(
    attendees: list[str] | None = None,
    organizer: str = "",
    title: str = "",
) -> CalendarEvent:
    return CalendarEvent(
        id="evt_x",
        title=title,
        start="2026-05-09T10:00:00Z",
        end="2026-05-09T11:00:00Z",
        attendees=attendees or [],
        description="",
        organizer=organizer,
    )


@pytest.mark.parametrize(
    "attendees,user_email,organizer,title,expected",
    [
        # Empty attendees → organizer fallback
        ([], "me@x.com", "Sean", "Briefing", "Sean"),
        # Empty attendees + empty organizer → title fallback
        ([], "me@x.com", "", "Solo prep", "Solo prep"),
        # Empty attendees + empty organizer + empty title → literal
        ([], "me@x.com", "", "", "Calendar event"),
        # Only self → organizer fallback
        (["me@x.com"], "me@x.com", "Sean", "T", "Sean"),
        # Multi-attendee, self first → second is picked
        (
            ["me@x.com", "Lin Manager <lin@acme.com>"],
            "me@x.com",
            "ignored",
            "ignored",
            "Lin Manager",
        ),
        # Case-insensitive email match: ME@X.COM == me@x.com → skip self, pick other
        (
            ["ME@X.COM", "Lin Manager <lin@acme.com>"],
            "me@x.com",
            "ignored",
            "ignored",
            "Lin Manager",
        ),
        # Whitespace in user_email + email-only attendee → bare-email picked, local-part used
        (
            ["lin@acme.com"],
            "  me@x.com  ",
            "ignored",
            "ignored",
            "lin",
        ),
        # Attendee email-only (no displayName) → uses local-part as display
        (
            ["lin@acme.com", "me@x.com"],
            "me@x.com",
            "ignored",
            "ignored",
            "lin",
        ),
        # Attendee displayName + email format → uses display name
        (
            ['"Sean Chen" <sean.chen@masterconcept.ai>'],
            "angus@gmail.com",
            "ignored",
            "ignored",
            "Sean Chen",
        ),
    ],
)
def test_pick_counterparty(attendees, user_email, organizer, title, expected):
    result = pick_counterparty(_event(attendees, organizer, title), user_email)
    assert result == expected


def test_pick_counterparty_skips_room_after_upstream_filter():
    """Slice-7 round 2 regression guard: when `_event_from_resource` has already
    dropped resource attendees, `pick_counterparty` sees only humans and returns
    the right one. The bug was the room name landing here before the filter."""
    # Post-filter state: room is gone, only Sean (viewer) and 林經理 remain.
    attendees = ['"Sean" <sean@x>', '"林經理" <lin@x>']
    result = pick_counterparty(
        _event(attendees, organizer="Sean", title="Q3 review"),
        user_email="sean@x",
    )
    assert result == "林經理"
    assert "龍貓" not in result
    assert "MCTW" not in result
