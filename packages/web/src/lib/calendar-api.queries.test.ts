/**
 * Calendar query options + error mapping contract.
 *
 * Slice-20b shape:
 * - upcomingEventsQueryOptions(hours) keys as ['calendar', 'upcoming', hours]
 * - calendarEventQueryOptions(eventId) keys as ['calendar', 'event', eventId]
 * - getUpcomingEvents / getCalendarEvent raise CalendarApiError on non-2xx
 * - errorCode of "calendar.not_connected" / "calendar.token_expired" /
 *   "calendar.network_error" / "calendar.event_not_found" surfaces as
 *   CalendarApiError.errorCode
 *
 * Slice-20b also REMOVES the `importFromCalendar` mutation (the calendar
 * import flow now navigates to /meetings/new?from_calendar=...).
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  CalendarApiError,
  calendarEventQueryOptions,
  getCalendarEvent,
  getUpcomingEvents,
  upcomingEventsQueryOptions,
} from "./calendar-api";

const originalFetch = globalThis.fetch;
let fetchCalls: Array<{ url: string; init?: RequestInit }> = [];

beforeEach(() => {
  fetchCalls = [];
  globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    fetchCalls.push({ url, init });
    if (url.includes("/api/calendar/events/")) {
      return new Response(
        JSON.stringify({
          id: "gcal_evt_42",
          title: "Q3 review",
          start: "2026-05-09T10:00:00Z",
          end: "2026-05-09T11:00:00Z",
          description: "quarterly review",
          attendees: ["Sean <sean@example.com>", "Lin <lin@acme.com>"],
          organizer: { display_name: "Sean", email: "sean@example.com" },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    if (url.includes("/api/calendar/upcoming")) {
      return new Response(
        JSON.stringify([
          {
            id: "e1",
            title: "first",
            start: "2026-05-09T10:00:00Z",
            end: "2026-05-09T11:00:00Z",
            attendees: ["a@b.com"],
            description: "",
            organizer: "Sean",
          },
        ]),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    return new Response("not found", { status: 404 });
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("upcomingEventsQueryOptions", () => {
  test("queryKey is ['calendar', 'upcoming', hours]", () => {
    const opts = upcomingEventsQueryOptions(48);
    expect(opts.queryKey).toEqual(["calendar", "upcoming", 48]);
  });

  test("queryFn fetches GET /api/calendar/upcoming with the configured hours", async () => {
    const opts = upcomingEventsQueryOptions(24);
    const result = await (opts.queryFn as () => Promise<unknown[]>)();
    expect(Array.isArray(result)).toBe(true);
    expect(fetchCalls[0]?.url).toContain("/api/calendar/upcoming?hours=24");
  });
});

describe("getUpcomingEvents error envelope handling", () => {
  test("raises CalendarApiError with errorCode 'calendar.not_connected' on 401", async () => {
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          error_code: "calendar.not_connected",
          message: "User has not granted Calendar scope.",
        }),
        { status: 401, headers: { "content-type": "application/json" } },
      )) as unknown as typeof fetch;

    let caught: unknown = null;
    try {
      await getUpcomingEvents(24);
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(CalendarApiError);
    const err = caught as CalendarApiError;
    expect(err.status).toBe(401);
    expect(err.errorCode).toBe("calendar.not_connected");
  });

  test("raises CalendarApiError with errorCode 'calendar.token_expired' on 401", async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ error_code: "calendar.token_expired", message: "..." }), {
        status: 401,
        headers: { "content-type": "application/json" },
      })) as unknown as typeof fetch;
    let caught: unknown = null;
    try {
      await getUpcomingEvents(24);
    } catch (e) {
      caught = e;
    }
    expect((caught as CalendarApiError).errorCode).toBe("calendar.token_expired");
  });

  test("raises CalendarApiError with errorCode 'calendar.network_error' on 502", async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ error_code: "calendar.network_error", message: "..." }), {
        status: 502,
        headers: { "content-type": "application/json" },
      })) as unknown as typeof fetch;
    let caught: unknown = null;
    try {
      await getUpcomingEvents(24);
    } catch (e) {
      caught = e;
    }
    expect((caught as CalendarApiError).errorCode).toBe("calendar.network_error");
  });
});

// ─── Slice-20b: getCalendarEvent + calendarEventQueryOptions ──────────────

describe("calendarEventQueryOptions", () => {
  test("queryKey is ['calendar', 'event', eventId]", () => {
    const opts = calendarEventQueryOptions("gcal_evt_42");
    expect(opts.queryKey).toEqual(["calendar", "event", "gcal_evt_42"]);
  });

  test("queryFn fetches GET /api/calendar/events/{eventId} and returns the typed detail", async () => {
    const opts = calendarEventQueryOptions("gcal_evt_42");
    const result = (await (opts.queryFn as () => Promise<unknown>)()) as {
      id: string;
      title: string;
      organizer: { email: string } | null;
    };
    expect(result.id).toBe("gcal_evt_42");
    expect(result.title).toBe("Q3 review");
    expect(result.organizer?.email).toBe("sean@example.com");
    expect(fetchCalls[0]?.url).toContain("/api/calendar/events/gcal_evt_42");
  });
});

describe("getCalendarEvent error envelope handling", () => {
  test("raises CalendarApiError with errorCode 'calendar.event_not_found' on 404", async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ error_code: "calendar.event_not_found", message: "..." }), {
        status: 404,
        headers: { "content-type": "application/json" },
      })) as unknown as typeof fetch;
    let caught: unknown = null;
    try {
      await getCalendarEvent("gcal_missing");
    } catch (e) {
      caught = e;
    }
    expect((caught as CalendarApiError).errorCode).toBe("calendar.event_not_found");
    expect((caught as CalendarApiError).status).toBe(404);
  });

  test("raises CalendarApiError with errorCode 'calendar.not_connected' on 401", async () => {
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ error_code: "calendar.not_connected", message: "..." }), {
        status: 401,
        headers: { "content-type": "application/json" },
      })) as unknown as typeof fetch;
    let caught: unknown = null;
    try {
      await getCalendarEvent("gcal_evt_42");
    } catch (e) {
      caught = e;
    }
    expect((caught as CalendarApiError).errorCode).toBe("calendar.not_connected");
  });
});
