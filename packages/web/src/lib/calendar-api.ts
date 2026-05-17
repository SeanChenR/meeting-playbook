/**
 * Calendar REST client — slice-20b shape.
 *
 * Wraps `fetch` against:
 *   GET  /api/calendar/upcoming               — list of upcoming events
 *   GET  /api/calendar/events/{event_id}      — single-event detail used by
 *                                                the meeting preview form
 *
 * Slice-20b: `importFromCalendar` mutation REMOVED. The calendar import
 * flow now navigates to `/meetings/new?from_calendar=<event_id>`; the
 * preview form fetches event detail via `getCalendarEvent` and creates the
 * meeting through `POST /api/meetings` (with `calendar_event_id` +
 * `attachments[]`).
 *
 * Errors are normalized to `CalendarApiError` so UI code can resolve
 * `errorCode` through `localizedErrorMessage(t)`.
 */

export interface UpcomingEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  attendees: string[];
  description: string;
  organizer: string;
}

/** Slice-20b: structured organizer reference returned alongside event detail. */
export interface OrganizerDetail {
  display_name: string;
  email: string;
}

/**
 * Slice-20b: single-event detail returned by
 * `GET /api/calendar/events/{event_id}`. Nullable fields mirror the
 * backend `CalendarEventDetail` Pydantic schema — Google Calendar payloads
 * may omit `start.dateTime` (all-day events), `description`, or the
 * `organizer` block entirely.
 */
export interface CalendarEventDetail {
  id: string;
  title: string;
  start: string | null;
  end: string | null;
  description: string | null;
  attendees: string[];
  organizer: OrganizerDetail | null;
}

export class CalendarApiError extends Error {
  status: number;
  errorCode: string | undefined;

  constructor(status: number, errorCode: string | undefined, message: string) {
    super(message);
    this.status = status;
    this.errorCode = errorCode;
  }
}

async function _envelopeError(resp: Response): Promise<CalendarApiError> {
  let body: { error_code?: string; message?: string } = {};
  try {
    body = (await resp.json()) as typeof body;
  } catch {
    // ignore
  }
  return new CalendarApiError(resp.status, body.error_code, body.message ?? `HTTP ${resp.status}`);
}

export async function getUpcomingEvents(hours = 24): Promise<UpcomingEvent[]> {
  const resp = await fetch(`/api/calendar/upcoming?hours=${encodeURIComponent(hours)}`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as UpcomingEvent[];
}

/**
 * Slice-20b: fetch a single calendar event's detail for the meeting
 * preview form. Same calendar-domain error codes as
 * `getUpcomingEvents`, plus `calendar.event_not_found` (404) when the
 * event id is unknown under the authenticated user's calendar.
 */
export async function getCalendarEvent(eventId: string): Promise<CalendarEventDetail> {
  const resp = await fetch(`/api/calendar/events/${encodeURIComponent(eventId)}`);
  if (!resp.ok) throw await _envelopeError(resp);
  return (await resp.json()) as CalendarEventDetail;
}

export function upcomingEventsQueryOptions(hours = 24) {
  return {
    queryKey: ["calendar", "upcoming", hours] as const,
    queryFn: () => getUpcomingEvents(hours),
  };
}

export function calendarEventQueryOptions(eventId: string) {
  return {
    queryKey: ["calendar", "event", eventId] as const,
    queryFn: () => getCalendarEvent(eventId),
    // The detail is fetched on form mount; do not retry on a calendar-domain
    // failure since the form needs to surface the error immediately so the
    // user can fall back to manual create.
    retry: false,
  };
}
