"""Pydantic schemas for the calendar router."""

from __future__ import annotations

from pydantic import BaseModel


class UpcomingEventRead(BaseModel):
    id: str
    title: str
    start: str
    end: str
    attendees: list[str]
    description: str
    organizer: str


class FromCalendarBody(BaseModel):
    event_id: str


class FromCalendarResponse(BaseModel):
    meeting_id: str


class OrganizerDetail(BaseModel):
    """Structured organizer reference returned by `GET /api/calendar/events/{id}`.

    Slice-20b: the preview form needs both halves so the frontend can match
    the organizer email against the viewer email (for me / counterparty
    derivation) AND show the display name without re-parsing the
    `Name <email>` string format used by `attendees`.
    """

    display_name: str
    email: str


class CalendarEventDetail(BaseModel):
    """Single calendar event response — slice-20b ADDED requirement
    "GET single Calendar event returns the full detail used by the meeting
    preview form".

    All fields are nullable where the underlying Google Calendar payload may
    omit them (all-day events have no start.dateTime, draft events may have
    no description, group invites may have no organizer block, etc.).
    `attendees` reuses the `Name <email>` formatted string list from the
    existing `_event_from_resource` parser so the resource-attendee filter
    flows through unchanged.
    """

    id: str
    title: str
    start: str | None
    end: str | None
    description: str | None
    attendees: list[str]
    organizer: OrganizerDetail | None
