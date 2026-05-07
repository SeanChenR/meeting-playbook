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

    // i18n key meetings.list.empty (zh-TW)
    await waitFor(() => {
      expect(screen.getByText(/尚無 meeting/)).toBeDefined();
    });
  });

  test("renders meetings in newest-first order returned by backend", async () => {
    fetchHandler = async () =>
      new Response(
        JSON.stringify([
          {
            id: "m_newest",
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
          },
          {
            id: "m_older",
            user_id: "u",
            title: "Q3 review",
            counterparty_display_name: "王董",
            me_display_name: "Sean",
            status: "scheduled",
            asr_provider: "whisper",
            calendar_event_id: null,
            created_at: "2026-05-06T10:00:00Z",
            started_at: null,
            ended_at: null,
          },
        ]),
        { status: 200, headers: { "content-type": "application/json" } },
      );

    await renderWithRouter(<MeetingsList />, { initialEntries: ["/meetings"], path: "/meetings" });

    // Wait for both titles to appear, then check DOM ordering matches list order.
    await waitFor(() => {
      expect(screen.getByText("Q4 plan")).toBeDefined();
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    const titles = screen.getAllByTestId("meeting-list-item-title").map((el) => el.textContent);
    expect(titles).toEqual(["Q4 plan", "Q3 review"]);
  });
});
