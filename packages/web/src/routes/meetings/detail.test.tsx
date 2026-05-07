import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

mock.module("../../lib/auth-client", () => ({
  authClient: {
    useSession: () => ({
      data: { user: { name: "Sean", email: "sean@example.com" } },
      isPending: false,
    }),
  },
}));

let fetchHandler: (url: string, init?: RequestInit) => Promise<Response> = async () =>
  new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
const originalFetch = globalThis.fetch;

import { MeetingDetail } from "./detail";

const SAMPLE_MEETING = {
  id: "m_abc",
  user_id: "u",
  title: "Q3 review",
  counterparty_display_name: "林經理",
  me_display_name: "Sean",
  status: "scheduled",
  asr_provider: "whisper",
  calendar_event_id: null,
  created_at: "2026-05-07T10:00:00Z",
  started_at: null,
  ended_at: null,
};

function renderInRouter(initialEntry = "/meetings/m_abc") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/meetings/:id" element={<MeetingDetail />} />
        <Route path="/meetings" element={<div data-testid="redirected-list">on list</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("MeetingDetail route", () => {
  beforeEach(() => {
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("renders title, display names, and status", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    renderInRouter();

    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });
    expect(screen.getByText(/林經理/)).toBeDefined();
    expect(screen.getByText(/Sean/)).toBeDefined();
    // zh-TW: meetings.status.scheduled → "已排程"
    expect(screen.getByText(/已排程/)).toBeDefined();
  });

  test("delete confirmation flow: open dialog → confirm → DELETE → redirect to list", async () => {
    const user = userEvent.setup();
    let deleted = false;
    fetchHandler = async (url, init) => {
      if (init?.method === "DELETE") {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    renderInRouter();

    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: /^刪除 Meeting$/ }));

    // Dialog open: title + confirm button visible.
    expect(screen.getByText(/確定要刪除這個 Meeting？/)).toBeDefined();
    await user.click(screen.getByRole("button", { name: /^確定刪除$/ }));

    await waitFor(() => {
      expect(screen.getByTestId("redirected-list")).toBeDefined();
    });
    expect(deleted).toBe(true);
  });

  test("delete dialog cancel keeps the meeting visible", async () => {
    const user = userEvent.setup();
    let deleted = false;
    fetchHandler = async (_, init) => {
      if (init?.method === "DELETE") {
        deleted = true;
        return new Response(null, { status: 204 });
      }
      return new Response(JSON.stringify(SAMPLE_MEETING), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };

    renderInRouter();

    await waitFor(() => {
      expect(screen.getByText("Q3 review")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: /^刪除 Meeting$/ }));
    await user.click(screen.getByRole("button", { name: /^取消$/ }));

    // Cancel must close the dialog and NOT issue DELETE.
    expect(deleted).toBe(false);
    expect(screen.getByText("Q3 review")).toBeDefined();
  });
});
