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
