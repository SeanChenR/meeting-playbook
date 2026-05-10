"""Calendar REST router — upcoming events + import-from-calendar.

Per slice-05 design (calendar-integration spec):
- GET /api/calendar/upcoming gates on X-User-Id; surfaces calendar.* error codes
- POST /api/meetings/from-calendar fetches event, creates meeting + playbook
- Generator failure does NOT roll back the meeting (recoverable through editor)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.calendar.client import (
    CalendarClient,
    CalendarNetworkError,
    CalendarNotConnected,
    CalendarTokenExpired,
)
from meeting_playbook.calendar.dependencies import (
    get_calendar_client_dependency,
    get_playbook_generator_dependency,
)
from meeting_playbook.calendar.identity import pick_counterparty
from meeting_playbook.calendar.schemas import (
    FromCalendarBody,
    FromCalendarResponse,
    UpcomingEventRead,
)
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_email_dependency,
    get_user_id_dependency,
    get_user_name_dependency,
)
from meeting_playbook.meetings.repository import MeetingRepository
from meeting_playbook.playbook_generation.generator import (
    PlaybookGenerationFailed,
    PlaybookGenerationTimeout,
    PlaybookGenerator,
)
from meeting_playbook.playbooks.repository import PlaybookRepository

router = APIRouter(tags=["calendar"])


def _calendar_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, CalendarNotConnected):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "calendar.not_connected",
                "message": "User has not granted Google Calendar scope.",
            },
        )
    if isinstance(exc, CalendarTokenExpired):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "calendar.token_expired",
                "message": "Stored Calendar token is no longer valid.",
            },
        )
    if isinstance(exc, CalendarNetworkError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "calendar.network_error",
                "message": "Could not reach the Google Calendar API.",
            },
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "common.internal_error",
            "message": "Unexpected calendar-domain error.",
        },
    )


def _generator_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, PlaybookGenerationTimeout):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error_code": "playbook.generation_timeout",
                "message": "Playbook generation exceeded the deadline.",
            },
        )
    if isinstance(exc, PlaybookGenerationFailed):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "playbook.generation_failed",
                "message": "Playbook generation produced an invalid response.",
            },
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={
            "error_code": "common.internal_error",
            "message": "Unexpected generator error.",
        },
    )


@router.get("/api/calendar/upcoming", response_model=list[UpcomingEventRead])
async def get_upcoming(
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    calendar: Annotated[CalendarClient, Depends(get_calendar_client_dependency)],
    hours: int = 24,
) -> list[UpcomingEventRead]:
    if hours < 1 or hours > 168:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "common.validation_error",
                "message": "hours must be between 1 and 168 inclusive.",
            },
        )
    try:
        events = await calendar.get_upcoming_events(user_id, hours=hours)
    except (CalendarNotConnected, CalendarTokenExpired, CalendarNetworkError) as exc:
        raise _calendar_error_to_http(exc) from exc

    return [
        UpcomingEventRead(
            id=e.id,
            title=e.title,
            start=e.start,
            end=e.end,
            attendees=list(e.attendees),
            description=e.description,
            organizer=e.organizer,
        )
        for e in events
    ]


@router.post(
    "/api/meetings/from-calendar",
    status_code=status.HTTP_201_CREATED,
    response_model=FromCalendarResponse,
)
async def import_from_calendar(
    body: FromCalendarBody,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    user_name: Annotated[str, Depends(get_user_name_dependency)],
    user_email: Annotated[str, Depends(get_user_email_dependency)],
    calendar: Annotated[CalendarClient, Depends(get_calendar_client_dependency)],
    generator: Annotated[PlaybookGenerator, Depends(get_playbook_generator_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> FromCalendarResponse:
    try:
        event = await calendar.get_event(user_id, body.event_id)
    except (CalendarNotConnected, CalendarTokenExpired, CalendarNetworkError) as exc:
        raise _calendar_error_to_http(exc) from exc

    # Slice 5 ingest: derive both display names from session identity instead
    # of hardcoded fallbacks (see calendar-integration spec, scenario rows).
    counterparty = pick_counterparty(event, user_email)
    me_display = user_name or (user_email.split("@", 1)[0] if "@" in user_email else "") or "Me"

    meeting = await MeetingRepository(session).create(
        user_id=user_id,
        title=event.title or "(untitled)",
        counterparty_display_name=counterparty,
        me_display_name=me_display,
    )

    # Set calendar_event_id directly — MeetingRepository.create does not yet
    # accept it as a kwarg (slice-03 deferred that). UPDATE is safe within the
    # same session.
    from sqlalchemy import text

    await session.execute(
        text("UPDATE meeting SET calendar_event_id = :ceid WHERE id = :mid"),
        {"ceid": event.id, "mid": meeting.id},
    )
    await session.commit()

    try:
        draft = await generator.generate(
            event,
            viewer_email=user_email,
            viewer_name=user_name,
        )
    except (PlaybookGenerationTimeout, PlaybookGenerationFailed) as exc:
        # Spec: meeting persists; surface generator error code.
        raise _generator_error_to_http(exc) from exc

    await PlaybookRepository(session).upsert_for_meeting(meeting.id, draft)

    return FromCalendarResponse(meeting_id=meeting.id)
