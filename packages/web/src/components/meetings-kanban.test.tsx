/**
 * MeetingsKanban — slice meetings-ux-revamp task 2.2.
 *
 * Asserts the structural contract from the spec scenario
 * "Three-bucket distribution": 5 meetings get sorted into 3 columns
 * by `getMeetingDateBucket(m, now)` running with the real `new Date()`.
 *
 * The test relies on dates that stay correctly bucketed regardless of
 * when the suite runs:
 *   - in_progress meetings are always upcoming
 *   - far-past completed meetings are always past
 *   - far-future scheduled meetings are always future
 *   - null-scheduled status=scheduled meetings are always future
 *
 * The "scheduled tomorrow" case from the spec scenario uses an offset
 * relative to `new Date()` so the assertion holds at any wall-clock time.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, screen, within } from "@testing-library/react";

import { MeetingsKanban } from "./meetings-kanban";
import type { Meeting } from "../lib/meetings-api";
import { renderWithRouter } from "../test/fixtures/router";

afterEach(cleanup);

function _meeting(overrides: Partial<Meeting>): Meeting {
  return {
    id: "id",
    user_id: "u",
    title: "Title",
    counterparty_display_name: "林經理",
    me_display_name: "Sean",
    status: "scheduled",
    asr_provider: "whisper",
    calendar_event_id: null,
    created_at: "2026-01-01T00:00:00Z",
    started_at: null,
    ended_at: null,
    scheduled_start_at: null,
    scheduled_end_at: null,
    ...overrides,
  };
}

const _tomorrow = new Date();
_tomorrow.setDate(_tomorrow.getDate() + 1);
_tomorrow.setHours(15, 0, 0, 0);

const _twoMonthsAgo = new Date();
_twoMonthsAgo.setDate(_twoMonthsAgo.getDate() - 60);

const _farFuture = new Date();
_farFuture.setDate(_farFuture.getDate() + 30);

const SAMPLE: Meeting[] = [
  _meeting({ id: "a", status: "in_progress", scheduled_start_at: _twoMonthsAgo.toISOString() }),
  _meeting({ id: "b", status: "scheduled", scheduled_start_at: _tomorrow.toISOString() }),
  _meeting({ id: "c", status: "scheduled", scheduled_start_at: _farFuture.toISOString() }),
  _meeting({ id: "d", status: "scheduled", scheduled_start_at: null }),
  _meeting({ id: "e", status: "completed", scheduled_start_at: _twoMonthsAgo.toISOString() }),
];

describe("MeetingsKanban", () => {
  test("(2.2a) Three-bucket distribution per spec scenario", async () => {
    await renderWithRouter(<MeetingsKanban meetings={SAMPLE} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    // Counts match the spec table: a+b in upcoming, c+d in future, e in past.
    expect(screen.getByTestId("kanban-count-upcoming").textContent).toBe("2");
    expect(screen.getByTestId("kanban-count-future").textContent).toBe("2");
    expect(screen.getByTestId("kanban-count-past").textContent).toBe("1");
  });

  test("(2.2b) empty bucket renders the localized hint", async () => {
    await renderWithRouter(<MeetingsKanban meetings={[]} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    expect(screen.getByTestId("kanban-empty-upcoming")).toBeDefined();
    expect(screen.getByTestId("kanban-empty-future")).toBeDefined();
    expect(screen.getByTestId("kanban-empty-past")).toBeDefined();
  });

  test("(2.2c) root grid uses 3 minmax(280px, 1fr) columns", async () => {
    await renderWithRouter(<MeetingsKanban meetings={SAMPLE} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const root = screen.getByTestId("meetings-kanban");
    expect(root.style.gridTemplateColumns).toContain("minmax(280px");
  });

  test("each card mounts inside its bucket column", async () => {
    await renderWithRouter(<MeetingsKanban meetings={SAMPLE} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const upcomingBody = screen.getByTestId("kanban-body-upcoming");
    const upcomingCards = within(upcomingBody).getAllByTestId("meeting-card");
    expect(upcomingCards.length).toBe(2);
    expect(upcomingCards.map((c) => c.getAttribute("href"))).toEqual(
      expect.arrayContaining(["/meetings/a", "/meetings/b"]),
    );

    const pastBody = screen.getByTestId("kanban-body-past");
    expect(within(pastBody).getAllByTestId("meeting-card").length).toBe(1);
  });
});
