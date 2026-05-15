/**
 * Slice-07: meetings-calendar-utils tests.
 */

import { describe, expect, test } from "bun:test";

import type { Meeting } from "./meetings-api";
import { meetingToCalendarEvent, statusToEventClassName } from "./meetings-calendar-utils";

const _meeting = (overrides: Partial<Meeting> = {}): Meeting => ({
  id: "m_t",
  user_id: "u_t",
  title: "Q3 review",
  counterparty_display_name: "林經理",
  me_display_name: "Sean",
  status: "scheduled",
  asr_provider: "whisper",
  calendar_event_id: null,
  created_at: "2026-05-10T00:00:00Z",
  started_at: null,
  ended_at: null,
  scheduled_start_at: "2026-06-15T14:00:00Z",
  scheduled_end_at: "2026-06-15T15:00:00Z",
  ...overrides,
});

describe("meetingToCalendarEvent", () => {
  test("returns CalendarEvent for any meeting (slice-15: start always present)", () => {
    const ev = meetingToCalendarEvent(_meeting());
    expect(ev.id).toBe("m_t");
    expect(ev.title).toBe("Q3 review");
    expect(ev.start.toISOString()).toBe("2026-06-15T14:00:00.000Z");
    expect(ev.end.toISOString()).toBe("2026-06-15T15:00:00.000Z");
  });

  test("defaults end to start + 30min when scheduled_end_at is null", () => {
    const ev = meetingToCalendarEvent(_meeting({ scheduled_end_at: null }));
    expect(ev.end.getTime() - ev.start.getTime()).toBe(30 * 60_000);
  });
});

describe("statusToEventClassName", () => {
  test("scheduled returns blue accent class", () => {
    expect(statusToEventClassName("scheduled")).toContain("blue");
  });

  test("in_progress returns green accent class", () => {
    expect(statusToEventClassName("in_progress")).toContain("emerald");
  });

  test("completed returns muted accent class", () => {
    expect(statusToEventClassName("completed")).toContain("muted");
  });

  test("each status produces a distinct class string", () => {
    const cls = new Set([
      statusToEventClassName("scheduled"),
      statusToEventClassName("in_progress"),
      statusToEventClassName("completed"),
    ]);
    expect(cls.size).toBe(3);
  });
});
