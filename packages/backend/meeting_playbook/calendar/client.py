"""CalendarClient — wraps Google Calendar API using TokenStore-supplied credentials.

Per slice-05 design (calendar-integration spec):
- get_upcoming_events returns events sorted by start ascending across all
  pagination pages
- on the first 401, calls TokenStore.refresh and retries once
- second 401 raises CalendarTokenExpired
- never-connected user → CalendarNotConnected
- persistent 5xx → CalendarNetworkError
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from meeting_playbook.calendar.token_store import (
    CalendarEventNotFound,
    CalendarNetworkError,
    CalendarNotConnected,
    CalendarTokenExpired,
    TokenStore,
)


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    title: str
    start: str
    end: str
    attendees: list[str]
    description: str
    organizer: str
    organizer_email: str = ""


def _default_build_service(credentials: Credentials) -> Any:
    """Production factory: build a Calendar v3 service with the given credentials."""
    # cache_discovery=False avoids a noisy oauth2client warning under newer libs.
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _http_status_from(exc: BaseException) -> int:
    """Map an HttpError or RefreshError to its effective HTTP status.

    googleapiclient's HttpError carries `.resp.status`. google-auth's
    RefreshError is raised when the library tried to auto-refresh on a 401
    and could not (we only pass `Credentials(token=...)` without refresh
    metadata, so any refresh attempt fails). Treat RefreshError as 401 so
    the surrounding code triggers the gateway-side TokenStore.refresh
    instead of returning a 500.
    """
    if isinstance(exc, RefreshError):
        return 401
    resp = getattr(exc, "resp", None)
    if resp is None:
        return 500
    return getattr(resp, "status", 500)


def _credentials_from_token(access_token: str) -> Credentials:
    return Credentials(token=access_token)


def _format_attendee(a: dict) -> str:
    """Format Google Calendar attendee dict as `'Name <email>'` / `'email'`.

    Both halves are kept so `pick_counterparty` can filter by email AND
    display the human-readable name. When only one half is present, just
    that half is returned.
    """
    email = (a.get("email") or "").strip()
    name = (a.get("displayName") or "").strip()
    if name and email:
        return f"{name} <{email}>"
    return email or name


def _is_resource_attendee(a: dict) -> bool:
    """True for Google Calendar room / equipment resource accounts.

    Slice-7 round-2 fix: Google's `attendees` list mixes humans with resources
    (meeting rooms, equipment). Resources are detected via:
      - explicit `resource: true` flag
      - `resourceEmail` field present
      - email ending with `@resource.calendar.google.com` (Google's resource
        domain — case-insensitive)

    Filtering at the parsing boundary keeps `pick_counterparty` and any
    downstream prompt formatting from accidentally selecting a room name.
    """
    if a.get("resource") is True:
        return True
    if a.get("resourceEmail"):
        return True
    email = (a.get("email") or "").strip().lower()
    return email.endswith("@resource.calendar.google.com")


def _event_from_resource(item: dict) -> CalendarEvent:
    attendees_raw = item.get("attendees") or []
    # Slice-7 round 2: drop resource (room / equipment) accounts before
    # formatting so they never become candidates for counterparty derivation.
    attendees_raw = [a for a in attendees_raw if not _is_resource_attendee(a)]
    attendees = [_format_attendee(a) for a in attendees_raw if a]
    attendees = [s for s in attendees if s]  # drop empty strings
    organizer_raw = item.get("organizer") or {}
    organizer = organizer_raw.get("displayName") or organizer_raw.get("email") or ""
    organizer_email = (organizer_raw.get("email") or "").strip()
    return CalendarEvent(
        id=item["id"],
        title=item.get("summary", ""),
        start=(item.get("start") or {}).get("dateTime", ""),
        end=(item.get("end") or {}).get("dateTime", ""),
        attendees=attendees,
        description=item.get("description", "") or "",
        organizer=organizer,
        organizer_email=organizer_email,
    )


class CalendarClient:
    def __init__(
        self,
        *,
        token_store: TokenStore,
        build_service: Callable[[Credentials], Any] | None = None,
    ) -> None:
        self._token_store = token_store
        self._build_service = build_service or _default_build_service

    async def get_upcoming_events(self, user_id: str, hours: int = 24) -> list[CalendarEvent]:
        """Fetch events in the next `hours` window for the user, ordered by start asc."""
        now = datetime.now(UTC)
        time_min = now.isoformat()
        time_max = (now + timedelta(hours=hours)).isoformat()

        token_payload = await self._token_store.get_access_token(user_id)
        access_token = token_payload["access_token"]

        try:
            return await self._list_events(access_token, time_min, time_max)
        except (HttpError, RefreshError) as exc:
            # RefreshError comes from googleapiclient's internal auto-refresh
            # attempt against a Credentials() that has no refresh_token set —
            # treat it as 401 (token expired) so the gateway-side refresh runs.
            status = _http_status_from(exc)
            if status == 401:
                new_payload = await self._token_store.refresh(user_id)
                new_access_token = new_payload["access_token"]
                try:
                    return await self._list_events(new_access_token, time_min, time_max)
                except (HttpError, RefreshError) as exc2:
                    status2 = _http_status_from(exc2)
                    if status2 == 401:
                        raise CalendarTokenExpired(
                            "Refresh succeeded but Calendar still rejects the token."
                        ) from exc2
                    raise CalendarNetworkError(
                        f"Calendar API returned {status2} after token refresh."
                    ) from exc2
            raise CalendarNetworkError(f"Calendar API returned {status}.") from exc

    async def get_event(self, user_id: str, event_id: str) -> CalendarEvent:
        """Fetch a single event by id (used by the from-calendar import endpoint)."""
        token_payload = await self._token_store.get_access_token(user_id)
        access_token = token_payload["access_token"]

        try:
            return await self._fetch_event(access_token, event_id)
        except (HttpError, RefreshError) as exc:
            status = _http_status_from(exc)
            if status == 401:
                new_payload = await self._token_store.refresh(user_id)
                try:
                    return await self._fetch_event(new_payload["access_token"], event_id)
                except (HttpError, RefreshError) as exc2:
                    status2 = _http_status_from(exc2)
                    if status2 == 401:
                        raise CalendarTokenExpired(
                            "Refresh succeeded but Calendar still rejects the token."
                        ) from exc2
                    raise CalendarNetworkError(
                        f"Calendar API returned {status2} after token refresh."
                    ) from exc2
            if status == 404:
                # Slice-20b: surface a typed 404 so the preview-form GET can
                # show `errors.calendar.event_not_found` instead of the
                # "please connect" CTA. Don't leak whether the event belongs
                # to a different user — single error code covers both
                # "event does not exist" and "event exists under another
                # user's calendar" per spec.
                raise CalendarEventNotFound("Event not visible to this user.") from exc
            raise CalendarNetworkError(f"Calendar API returned {status}.") from exc

    async def _fetch_event(self, access_token: str, event_id: str) -> CalendarEvent:
        service = self._build_service(_credentials_from_token(access_token))
        events_resource = service.events()
        response = await asyncio.to_thread(
            lambda: events_resource.get(calendarId="primary", eventId=event_id).execute()
        )
        return _event_from_resource(response)

    async def _list_events(
        self, access_token: str, time_min: str, time_max: str
    ) -> list[CalendarEvent]:
        service = self._build_service(_credentials_from_token(access_token))
        events_resource = service.events()

        # Iterate every calendar the user has selected (primary + subscribed
        # / shared / course calendars). Querying calendarId="primary" alone
        # misses events from secondary calendars that the user actually sees
        # in the Google Calendar UI.
        calendar_ids = await self._list_selected_calendar_ids(service)
        if not calendar_ids:
            calendar_ids = ["primary"]

        items: list[dict] = []
        for cal_id in calendar_ids:
            page_token: str | None = None
            while True:
                kwargs = {
                    "calendarId": cal_id,
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "singleEvents": True,
                    "orderBy": "startTime",
                    "maxResults": 100,
                }
                if page_token:
                    kwargs["pageToken"] = page_token

                response = await asyncio.to_thread(
                    lambda kw=kwargs: events_resource.list(**kw).execute()
                )
                items.extend(response.get("items", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

        # Merge across calendars and sort by start (ascending). dateTime takes
        # precedence; all-day events use `date`.
        def _start_key(item: dict) -> str:
            start = item.get("start") or {}
            return start.get("dateTime") or start.get("date") or ""

        items.sort(key=_start_key)
        return [_event_from_resource(it) for it in items]

    async def _list_selected_calendar_ids(self, service) -> list[str]:
        """Return calendar ids the user has selected to show in the UI.

        Returns an empty list when the calendarList endpoint is unavailable
        or returns nothing useful — caller falls back to ['primary'].
        """
        try:
            response = await asyncio.to_thread(lambda: service.calendarList().list().execute())
        except Exception:
            return []
        items = response.get("items", []) if isinstance(response, dict) else []
        ids: list[str] = []
        for cal in items:
            if not isinstance(cal, dict):
                continue
            # Only include calendars the user has marked as visible. If the
            # `selected` field is absent (some primary calendars omit it),
            # default to True.
            if cal.get("selected", True) is False:
                continue
            cal_id = cal.get("id")
            if cal_id:
                ids.append(cal_id)
        return ids


__all__ = [
    "CalendarClient",
    "CalendarEvent",
    "CalendarEventNotFound",
    "CalendarNetworkError",
    "CalendarNotConnected",
    "CalendarTokenExpired",
]
