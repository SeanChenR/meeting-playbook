/**
 * MeetingsList tests — extended for slice ui-overhaul-claude-design task 4.1.
 *
 * Existing slice-7 cases:
 *   - Empty state when backend returns []
 *   - Title ordering preserved
 *
 * Phase-4 additions per task contract:
 *   - (a) cards render inside a grid (auto-fill / minmax 320px)
 *   - (b) hover styles applied (transition + hover:shadow-md class present)
 *   - (c) empty list copy is neutral (no emoji glyphs)
 *   - (d) clicking a card navigates to /meetings/$meetingId via TanStack Link
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
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

import { MeetingsList } from "./list";

const SAMPLE_MEETING = {
  id: "m_one",
  user_id: "u",
  title: "Q4 plan",
  counterparty_display_name: "林經理",
  me_display_name: "Sean",
  status: "scheduled",
  asr_provider: "whisper",
  calendar_event_id: null,
  created_at: "2026-05-07T10:00:00Z",
  started_at: null,
  ended_at: null,
  scheduled_start_at: "2026-05-15T06:30:00Z",
  scheduled_end_at: "2026-05-15T07:30:00Z",
};

describe("MeetingsList route", () => {
  beforeEach(() => {
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("renders empty state when backend returns []", async () => {
    fetchHandler = async () =>
      new Response("[]", {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    await renderWithRouter(<MeetingsList />, { initialEntries: ["/meetings"], path: "/meetings" });

    await waitFor(() => {
      expect(screen.getByText(/尚無 meeting/)).toBeDefined();
    });
  });

  test("renders meetings in newest-first order returned by backend", async () => {
    fetchHandler = async () =>
      new Response(
        JSON.stringify([
          { ...SAMPLE_MEETING, id: "m_newest", title: "Q4 plan" },
          { ...SAMPLE_MEETING, id: "m_older", title: "Q3 review" },
        ]),
        { status: 200, headers: { "content-type": "application/json" } },
      );

    await renderWithRouter(<MeetingsList />, { initialEntries: ["/meetings"], path: "/meetings" });

    await waitFor(() => {
      expect(screen.getByText("Q4 plan")).toBeDefined();
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    const titles = screen.getAllByTestId("meeting-list-item-title").map((el) => el.textContent);
    expect(titles).toEqual(["Q4 plan", "Q3 review"]);
  });

  // ─── Phase 4 additions ────────────────────────────────────────────────

  test("(a) renders cards inside a responsive auto-fill grid", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify([SAMPLE_MEETING]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    await renderWithRouter(<MeetingsList />, { initialEntries: ["/meetings"], path: "/meetings" });

    const grid = await screen.findByTestId("meetings-grid");
    // Inline style declares the auto-fill template — assert the substring.
    expect(grid.getAttribute("style") ?? "").toContain("auto-fill");
    expect(grid.getAttribute("style") ?? "").toContain("320px");
  });

  test("(b) cards apply hover-shadow + transition utility classes", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify([SAMPLE_MEETING]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    await renderWithRouter(<MeetingsList />, { initialEntries: ["/meetings"], path: "/meetings" });

    const card = await screen.findByTestId("meeting-card");
    expect(card.className).toContain("transition-");
    expect(card.className).toContain("hover:shadow-md");
  });

  test("(c) empty state copy contains no emoji glyphs", async () => {
    fetchHandler = async () =>
      new Response("[]", {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    await renderWithRouter(<MeetingsList />, { initialEntries: ["/meetings"], path: "/meetings" });

    const empty = await screen.findByTestId("meetings-empty-state");
    // Strip whitespace, then check no codepoints sit in the common emoji ranges.
    const text = (empty.textContent ?? "").trim();
    // Pictographic / symbol-and-pictographs / emoticons / dingbats blocks.
    const emojiRegex = /[\u{1F300}-\u{1FAFF}\u{2700}-\u{27BF}\u{2600}-\u{26FF}]/u;
    expect(emojiRegex.test(text)).toBe(false);
  });

  test("(d) clicking a card navigates to /meetings/<id>", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify([SAMPLE_MEETING]), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    await renderWithRouter(<MeetingsList />, { initialEntries: ["/meetings"], path: "/meetings" });

    const card = await screen.findByTestId("meeting-card");
    expect(card.tagName).toBe("A");
    expect(card.getAttribute("href")).toBe("/meetings/m_one");
  });
});
