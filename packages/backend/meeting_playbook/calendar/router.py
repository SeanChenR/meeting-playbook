"""Calendar REST router — upcoming events list + single-event detail.

Slice-20b updates (per design.md `Endpoint 拆分` + spec deltas):
- GET /api/calendar/upcoming gates on X-User-Id; surfaces calendar.* error codes
- GET /api/calendar/events/{event_id} returns the single-event detail used
  by the meeting preview form (slice-20b ADDED requirement)
- POST /api/meetings/from-calendar is REMOVED — the route now returns
  HTTP 410 Gone with `calendar.import_endpoint_removed`. The replacement
  flow lives in `meeting-management` (`POST /api/meetings` with
  `calendar_event_id` + `attachments[]`).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from meeting_playbook.calendar.client import (
    CalendarClient,
    CalendarEventNotFound,
    CalendarNetworkError,
    CalendarNotConnected,
    CalendarTokenExpired,
)
from meeting_playbook.calendar.dependencies import get_calendar_client_dependency
from meeting_playbook.calendar.schemas import (
    CalendarEventDetail,
    OrganizerDetail,
    UpcomingEventRead,
)
from meeting_playbook.meetings.dependencies import get_user_id_dependency

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
    if isinstance(exc, CalendarEventNotFound):
        # Slice-20b: typed 404 for the preview-form GET. Per spec the body
        # MUST NOT distinguish missing-vs-other-user, so the message stays
        # generic.
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "calendar.event_not_found",
                "message": "Calendar event not found.",
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


@router.get(
    "/api/calendar/events/{event_id}",
    response_model=CalendarEventDetail,
)
async def get_calendar_event(
    event_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    calendar: Annotated[CalendarClient, Depends(get_calendar_client_dependency)],
) -> CalendarEventDetail:
    """Slice-20b ADDED requirement: single-event detail for the preview form.

    Reuses `CalendarClient.get_event` (slice-05) so the resource-attendee
    filter and OAuth refresh-once-on-401 dance flow through unchanged. The
    only contract delta vs the legacy `POST /api/meetings/from-calendar`
    path is the 404 mapping: this endpoint surfaces `calendar.event_not_found`
    instead of the conflated `calendar.not_connected` used by the legacy
    path (which is being removed in task 3.1).
    """
    try:
        event = await calendar.get_event(user_id, event_id)
    except (
        CalendarNotConnected,
        CalendarTokenExpired,
        CalendarEventNotFound,
        CalendarNetworkError,
    ) as exc:
        raise _calendar_error_to_http(exc) from exc

    organizer: OrganizerDetail | None = None
    if event.organizer or event.organizer_email:
        organizer = OrganizerDetail(
            display_name=event.organizer or "",
            email=event.organizer_email or "",
        )

    return CalendarEventDetail(
        id=event.id,
        title=event.title,
        # The existing CalendarEvent dataclass uses "" sentinel for missing
        # dateTime fields; the preview form needs a real nullable so the
        # frontend can decide whether to pre-fill the schedule inputs.
        start=event.start or None,
        end=event.end or None,
        description=event.description or None,
        attendees=list(event.attendees),
        organizer=organizer,
    )


@router.post("/api/meetings/from-calendar")
async def import_from_calendar() -> None:
    """Slice-20b REMOVED Requirement: `POST /api/meetings/from-calendar`.

    The fire-and-forget contract (slice-05 + slice-07) is replaced by the
    preview-and-confirm flow: callers navigate to
    `/meetings/new?from_calendar=<event_id>` and submit through
    `POST /api/meetings` carrying `calendar_event_id` + `attachments[]`.

    The route is retained only to surface a deterministic 410 + typed
    error_code so old clients (and old service-worker caches) get a
    clear signal to upgrade. Every request — regardless of body or auth
    state — returns the same envelope; no body is read, no DB row is
    written, and no Playbook generator is invoked. The route also
    declares NO request dependencies (no body model, no session) so the
    handler runs before any auth gating, matching the spec scenario
    "any client sends `POST /api/meetings/from-calendar` for any event
    id" → 410 with zero side effects.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "error_code": "calendar.import_endpoint_removed",
            "message": (
                "Calendar import now uses the preview flow: navigate to "
                "/meetings/new?from_calendar=<event_id> and confirm to create "
                "the meeting + generate the playbook."
            ),
        },
    )
