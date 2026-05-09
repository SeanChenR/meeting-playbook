"""Pure-function tests for `classify_viewer_role(event, viewer_email)`.

Per spec slice-05 ingest round 2 (playbook-generation ADDED requirement
"Generator output is written from the signed-in viewer's point of view"):

- "organizer" → viewer_email == event.organizer_email (case-insensitive, trimmed)
- "attendee"  → viewer_email matches an attendee email AND is not the organizer
- "external"  → viewer_email matches neither
- empty viewer_email → "external"
- empty organizer_email + viewer matches an attendee → "attendee"
- empty organizer_email + viewer matches no one → "external"
"""

from __future__ import annotations

import pytest

from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.calendar.identity import classify_viewer_role


def _event(
    attendees: list[str] | None = None,
    organizer: str = "",
    organizer_email: str = "",
) -> CalendarEvent:
    return CalendarEvent(
        id="evt_x",
        title="T",
        start="2026-05-09T10:00:00Z",
        end="2026-05-09T11:00:00Z",
        attendees=attendees or [],
        description="",
        organizer=organizer,
        organizer_email=organizer_email,
    )


@pytest.mark.parametrize(
    "attendees,organizer_email,viewer_email,expected",
    [
        # (a) viewer matches organizer_email exactly → organizer
        ([], "host@x.com", "host@x.com", "organizer"),
        # (b) case + whitespace differences still match organizer
        ([], "host@x.com", "  HOST@X.COM  ", "organizer"),
        # (c) viewer in attendees but not organizer → attendee
        (["me@x.com", "other@x.com"], "host@x.com", "me@x.com", "attendee"),
        # (d) viewer matches both organizer and attendee (organizer self-invited)
        #     → organizer wins (per design: organizer beats attendee)
        (["host@x.com", "other@x.com"], "host@x.com", "host@x.com", "organizer"),
        # (e) viewer in neither → external
        (["a@x.com", "b@x.com"], "host@x.com", "stranger@x.com", "external"),
        # (f) empty viewer_email → external (degrades safely)
        (["a@x.com"], "host@x.com", "", "external"),
        # (g) empty organizer_email + viewer matches an attendee → attendee
        (["me@x.com"], "", "me@x.com", "attendee"),
        # (h) empty organizer_email + viewer matches no one → external
        ([], "", "lonely@x.com", "external"),
    ],
)
def test_classify_viewer_role(attendees, organizer_email, viewer_email, expected):
    result = classify_viewer_role(
        _event(attendees=attendees, organizer_email=organizer_email),
        viewer_email,
    )
    assert result == expected
