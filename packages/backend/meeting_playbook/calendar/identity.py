"""Display-name derivation for calendar imports.

Per slice-05 ingest (calendar-integration spec): the import endpoint must
pick `counterparty_display_name` by filtering attendees against the
authenticated user's email, falling back through organizer → title → a
literal sentinel.

Round 2 ingest also adds `classify_viewer_role` so the LLM prompt can be
written from the signed-in viewer's point of view (organizer / attendee /
external).

Kept as a standalone module so it can be unit-tested without the FastAPI
router stack.
"""

from __future__ import annotations

from typing import Literal

from meeting_playbook.calendar.client import CalendarEvent

_FALLBACK_LITERAL = "Calendar event"

ViewerRole = Literal["organizer", "attendee", "external"]


def _parse_attendee(raw: str) -> tuple[str, str]:
    """Parse a single attendee string into `(email, display_name)`.

    Accepts the formats produced by `_event_from_resource`:
    - `"Display Name <email@x>"` — RFC-style; displayName + email both present
    - `"email@x"` — bare email, no displayName
    - `"Display Name"` — no email at all (rare; e.g., resource accounts)
    """
    text = raw.strip()
    if not text:
        return ("", "")
    if "<" in text and text.endswith(">"):
        idx = text.rindex("<")
        name = text[:idx].strip().strip('"')
        email = text[idx + 1 : -1].strip()
        return (email, name or (email.split("@")[0] if "@" in email else email))
    if "@" in text:
        return (text, text.split("@")[0])
    return ("", text)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def pick_counterparty(event: CalendarEvent, user_email: str) -> str:
    """Return the display name for the counterparty side of `event`.

    Rules:
    1. First attendee whose email != `user_email` (case-insensitive, trimmed)
    2. If no other-party attendee: event organizer
    3. If no organizer: event title
    4. Last resort: the literal "Calendar event"

    The display string is the parsed display name, falling back to the
    email's local-part when the attendee carried only an email.
    """
    user_email_norm = _normalize_email(user_email)

    for raw in event.attendees:
        email, display = _parse_attendee(raw)
        if not email and not display:
            continue
        if email and _normalize_email(email) == user_email_norm:
            continue
        if display:
            return display
        if email:
            return email
    if event.organizer:
        return event.organizer
    if event.title:
        return event.title
    return _FALLBACK_LITERAL


def classify_viewer_role(event: CalendarEvent, viewer_email: str) -> ViewerRole:
    """Classify the viewer's role for `event`.

    Returns one of:
      - "organizer": viewer_email matches event.organizer_email (case-insensitive)
      - "attendee": viewer_email matches an attendee email AND is not the organizer
      - "external": viewer_email matches neither (or viewer_email is empty)

    Organizer wins when the viewer is both organizer and attendee (self-invite).
    Empty `event.organizer_email` cannot resolve to "organizer" — without an
    organizer email to compare against, we fall through to attendee / external.
    """
    viewer_norm = _normalize_email(viewer_email)
    if not viewer_norm:
        return "external"

    organizer_norm = _normalize_email(event.organizer_email)
    if organizer_norm and viewer_norm == organizer_norm:
        return "organizer"

    for raw in event.attendees:
        email, _display = _parse_attendee(raw)
        if email and _normalize_email(email) == viewer_norm:
            return "attendee"

    return "external"


__all__ = ["ViewerRole", "classify_viewer_role", "pick_counterparty"]
