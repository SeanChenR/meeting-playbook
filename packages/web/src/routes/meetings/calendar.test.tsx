/**
 * MeetingsCalendar smoke test — slice ui-overhaul-claude-design task 4.3.
 *
 * Covers the rewrite contract:
 *   (a) Page header renders title + meta (year-month + ISO week)
 *   (b) Tabs (月/週) render and `週` activates week view
 *   (c) Meetings with a `scheduled_start_at` show up as events on the grid
 *   (d) Meetings without `scheduled_start_at` show in the 未排程 sidebar
 *   (e) Clicking "排定" navigates to /meetings/$id
 *
 * react-big-calendar emits events as `.rbc-event` DOM nodes; we assert
 * presence via `document.querySelectorAll(".rbc-event")` instead of by
 * label text, because event titles can be truncated in the rendered cells.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithRouter } from "../../test/fixtures/router";

mock.module("../../lib/auth-client", () => ({
  authClient: {
    useSession: () => ({
      data: { user: { name: "Sean", email: "sean@example.com" } },
      isPending: false,
    }),
  },
}));

let fetchHandler: (url: string, init?: RequestInit) => Promise<Response> = async () =>
  new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
const originalFetch = globalThis.fetch;

import { MeetingsCalendar } from "./calendar";

const TODAY = new Date();
const tomorrow = new Date(TODAY);
tomorrow.setDate(tomorrow.getDate() + 1);
tomorrow.setHours(10, 0, 0, 0);
const tomorrowEnd = new Date(tomorrow);
tomorrowEnd.setHours(11, 0, 0, 0);

const SCHEDULED = {
  id: "m_scheduled",
  user_id: "u",
  title: "Q4 plan",
  counterparty_display_name: "林經理",
  me_display_name: "Sean",
  status: "scheduled",
  asr_provider: "whisper",
  calendar_event_id: null,
  created_at: TODAY.toISOString(),
  started_at: null,
  ended_at: null,
  scheduled_start_at: tomorrow.toISOString(),
  scheduled_end_at: tomorrowEnd.toISOString(),
};

const UNSCHEDULED = {
  id: "m_unscheduled",
  user_id: "u",
  title: "Floating idea",
  counterparty_display_name: "王董",
  me_display_name: "Sean",
  status: "scheduled",
  asr_provider: "whisper",
  calendar_event_id: null,
  created_at: TODAY.toISOString(),
  started_at: null,
  ended_at: null,
  scheduled_start_at: null,
  scheduled_end_at: null,
};

describe("MeetingsCalendar route", () => {
  beforeEach(() => {
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("(a) renders header title and ISO-week meta", async () => {
    fetchHandler = async () =>
      new Response("[]", { status: 200, headers: { "content-type": "application/json" } });

    await renderWithRouter(<MeetingsCalendar />, {
      initialEntries: ["/meetings/calendar"],
      path: "/meetings/calendar",
    });

    const header = await screen.findByTestId("calendar-header");
    expect(header.textContent ?? "").toMatch(/(日曆視圖|Calendar)/);
    expect(header.textContent ?? "").toMatch(/(週|Week)/);
  });

  test("(b) clicking 月 tab activates month view", async () => {
    fetchHandler = async () =>
      new Response("[]", { status: 200, headers: { "content-type": "application/json" } });

    const user = userEvent.setup();
    await renderWithRouter(<MeetingsCalendar />, {
      initialEntries: ["/meetings/calendar"],
      path: "/meetings/calendar",
    });

    const monthTab = await screen.findByTestId("calendar-tab-month");
    await user.click(monthTab);

    await waitFor(() => {
      expect(monthTab.getAttribute("data-state")).toBe("active");
    });
  });

  test("(c) scheduled meeting renders as an event on the grid", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify([SCHEDULED]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    await renderWithRouter(<MeetingsCalendar />, {
      initialEntries: ["/meetings/calendar"],
      path: "/meetings/calendar",
    });

    await waitFor(() => {
      const events = document.querySelectorAll(".rbc-event");
      expect(events.length).toBeGreaterThan(0);
    });
  });

  test("(d) unscheduled meeting shows in the 未排程 sidebar", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify([UNSCHEDULED]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    await renderWithRouter(<MeetingsCalendar />, {
      initialEntries: ["/meetings/calendar"],
      path: "/meetings/calendar",
    });

    const row = await screen.findByTestId("unscheduled-row-m_unscheduled");
    expect(row.textContent ?? "").toContain("Floating idea");
  });

  test("(e) sidebar 排定 link points to /meetings/<id>", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify([UNSCHEDULED]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    await renderWithRouter(<MeetingsCalendar />, {
      initialEntries: ["/meetings/calendar"],
      path: "/meetings/calendar",
    });

    const row = await screen.findByTestId("unscheduled-row-m_unscheduled");
    const link = row.querySelector("a");
    expect(link?.getAttribute("href")).toBe("/meetings/m_unscheduled");
  });
});
