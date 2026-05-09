/**
 * Calendar query options + error mapping contract.
 *
 * - upcomingEventsQueryOptions(hours) keys as ['calendar', 'upcoming', hours]
 * - getUpcomingEvents / importFromCalendar raise CalendarApiError on non-2xx
 * - errorCode of "calendar.not_connected" / "calendar.token_expired" /
 *   "calendar.network_error" surfaces as CalendarApiError.errorCode
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  CalendarApiError,
  getUpcomingEvents,
  importFromCalendar,
  upcomingEventsQueryOptions,
} from "./calendar-api";

const originalFetch = globalThis.fetch;
let fetchCalls: Array<{ url: string; init?: RequestInit }> = [];

beforeEach(() => {
  fetchCalls = [];
  globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    fetchCalls.push({ url, init });
    if (init?.method === "POST" && url.includes("/api/meetings/from-calendar")) {
      return new Response(JSON.stringify({ meeting_id: "m_imported" }), {
        status: 201,
        headers: { "content-type": "application/json" },
      });
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
      )) as typeof fetch;

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
      })) as typeof fetch;
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
      })) as typeof fetch;
    let caught: unknown = null;
    try {
      await getUpcomingEvents(24);
    } catch (e) {
      caught = e;
    }
    expect((caught as CalendarApiError).errorCode).toBe("calendar.network_error");
  });
});

describe("importFromCalendar", () => {
  test("POSTs the event_id and returns the new meeting id", async () => {
    const result = await importFromCalendar("gcal_evt_42");
    expect(result).toEqual({ meeting_id: "m_imported" });
    const post = fetchCalls.find((c) => c.init?.method === "POST");
    expect(post).toBeDefined();
    expect(post!.url).toContain("/api/meetings/from-calendar");
    expect(JSON.parse(String(post!.init?.body))).toEqual({ event_id: "gcal_evt_42" });
  });

  test("raises CalendarApiError when the upstream returns playbook.generation_timeout", async () => {
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          error_code: "playbook.generation_timeout",
          message: "Generation exceeded 60s.",
        }),
        { status: 504, headers: { "content-type": "application/json" } },
      )) as typeof fetch;
    let caught: unknown = null;
    try {
      await importFromCalendar("gcal_evt_x");
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(CalendarApiError);
    expect((caught as CalendarApiError).errorCode).toBe("playbook.generation_timeout");
  });
});
