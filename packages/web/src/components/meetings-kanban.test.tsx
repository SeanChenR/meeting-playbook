/**
 * MeetingsKanban — slice-15 task 7.5 rewrite.
 *
 * Asserts the new structural contract: 3-column lifecycle-bucketed
 * Kanban with columns `needs_recording` / `upcoming` / `completed`.
 *
 * Date fixtures stay relative to `new Date()` so the assertion holds
 * regardless of when the suite runs:
 *   - in_progress / completed meetings always land in `completed`
 *   - scheduled meetings with `_tomorrow` start always `upcoming`
 *   - scheduled meetings with `_twoMonthsAgo` start always `needs_recording`
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
    scheduled_start_at: "2026-06-15T14:00:00Z",
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
  // a: in_progress with past scheduled → completed
  _meeting({ id: "a", status: "in_progress", scheduled_start_at: _twoMonthsAgo.toISOString() }),
  // b: scheduled tomorrow → upcoming
  _meeting({ id: "b", status: "scheduled", scheduled_start_at: _tomorrow.toISOString() }),
  // c: scheduled far future → upcoming
  _meeting({ id: "c", status: "scheduled", scheduled_start_at: _farFuture.toISOString() }),
  // d: scheduled but past → needs_recording (overdue)
  _meeting({ id: "d", status: "scheduled", scheduled_start_at: _twoMonthsAgo.toISOString() }),
  // e: completed → completed
  _meeting({ id: "e", status: "completed", scheduled_start_at: _twoMonthsAgo.toISOString() }),
];

describe("MeetingsKanban", () => {
  test("(7.5a) Three-bucket distribution per new slice-15 spec scenario", async () => {
    await renderWithRouter(<MeetingsKanban meetings={SAMPLE} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    // a+e in completed, b+c in upcoming, d alone in needs_recording.
    expect(screen.getByTestId("kanban-count-needs_recording").textContent).toBe("1");
    expect(screen.getByTestId("kanban-count-upcoming").textContent).toBe("2");
    expect(screen.getByTestId("kanban-count-completed").textContent).toBe("2");
  });

  test("(7.5b) empty bucket renders the localized hint in each column", async () => {
    await renderWithRouter(<MeetingsKanban meetings={[]} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    expect(screen.getByTestId("kanban-empty-needs_recording")).toBeDefined();
    expect(screen.getByTestId("kanban-empty-upcoming")).toBeDefined();
    expect(screen.getByTestId("kanban-empty-completed")).toBeDefined();
  });

  test("(7.5c) root grid uses 3 minmax(280px, 1fr) columns", async () => {
    await renderWithRouter(<MeetingsKanban meetings={SAMPLE} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const root = screen.getByTestId("meetings-kanban");
    expect(root.style.gridTemplateColumns).toContain("minmax(280px");
  });

  test("(7.5d) each card mounts inside its bucket column", async () => {
    await renderWithRouter(<MeetingsKanban meetings={SAMPLE} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const upcomingBody = screen.getByTestId("kanban-body-upcoming");
    const upcomingCards = within(upcomingBody).getAllByTestId("meeting-card");
    expect(upcomingCards.length).toBe(2);
    expect(upcomingCards.map((c) => c.getAttribute("href"))).toEqual(
      expect.arrayContaining(["/meetings/b", "/meetings/c"]),
    );

    const completedBody = screen.getByTestId("kanban-body-completed");
    expect(within(completedBody).getAllByTestId("meeting-card").length).toBe(2);

    const needsRecordingBody = screen.getByTestId("kanban-body-needs_recording");
    const needsCards = within(needsRecordingBody).getAllByTestId("meeting-card");
    expect(needsCards.length).toBe(1);
    expect(needsCards[0]?.getAttribute("href")).toBe("/meetings/d");
  });

  test("(8.5a) needs_recording empty column shows custom CTA", async () => {
    await renderWithRouter(<MeetingsKanban meetings={[]} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const empty = screen.getByTestId("kanban-empty-needs_recording");
    expect(empty.textContent ?? "").toContain("待補錄");
    expect(empty.textContent ?? "").not.toBe("此區段暫無會議");
  });

  test("(8.5b) needs_recording cards carry the upload shortcut", async () => {
    const past = new Date();
    past.setDate(past.getDate() - 10);
    const meetings: Meeting[] = [
      _meeting({ id: "needs", status: "scheduled", scheduled_start_at: past.toISOString() }),
    ];
    await renderWithRouter(<MeetingsKanban meetings={meetings} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const body = screen.getByTestId("kanban-body-needs_recording");
    expect(within(body).getByTestId("meeting-card-upload-shortcut")).toBeDefined();
  });

  test("(7.5e) completed column sorts by scheduled_start_at DESC", async () => {
    // Two completed meetings, A more recent than B. The component
    // sorts the `completed` bucket by scheduled_start_at DESC so A
    // floats above B in the rendered list.
    const recent = new Date();
    recent.setDate(recent.getDate() - 1);
    const older = new Date();
    older.setDate(older.getDate() - 30);
    const meetings: Meeting[] = [
      _meeting({ id: "older", status: "completed", scheduled_start_at: older.toISOString() }),
      _meeting({ id: "recent", status: "completed", scheduled_start_at: recent.toISOString() }),
    ];

    await renderWithRouter(<MeetingsKanban meetings={meetings} />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });
    const completedBody = screen.getByTestId("kanban-body-completed");
    const cards = within(completedBody).getAllByTestId("meeting-card");
    expect(cards.map((c) => c.getAttribute("href"))).toEqual([
      "/meetings/recent",
      "/meetings/older",
    ]);
  });
});
