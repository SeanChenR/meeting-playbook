import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router";

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

import { NewMeeting } from "./new";

function renderInRouter(initialEntries: string[] = ["/meetings/new"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/meetings/new" element={<NewMeeting />} />
        <Route
          path="/meetings/:id"
          element={<div data-testid="redirected-detail">on detail</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("NewMeeting form", () => {
  beforeEach(() => {
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("client-side blocks submit when required fields are empty", async () => {
    const user = userEvent.setup();
    let postCalled = false;
    fetchHandler = async (_, init) => {
      if (init?.method === "POST") postCalled = true;
      return new Response("[]", { status: 201 });
    };

    renderInRouter();

    // Submit immediately without filling anything.
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    // The browser's required attribute should prevent the POST.
    expect(postCalled).toBe(false);
  });

  test("submitting valid fields posts and redirects to /meetings/:id", async () => {
    const user = userEvent.setup();
    let posted: { url: string; body: unknown } | null = null;

    fetchHandler = async (url, init) => {
      if (init?.method === "POST") {
        posted = { url, body: JSON.parse(String(init.body)) };
        return new Response(
          JSON.stringify({
            id: "m_abc",
            user_id: "u",
            title: "Q3",
            counterparty_display_name: "林經理",
            me_display_name: "Sean",
            status: "scheduled",
            asr_provider: "whisper",
            calendar_event_id: null,
            created_at: "2026-05-07T10:00:00Z",
            started_at: null,
            ended_at: null,
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        );
      }
      return new Response("[]", { status: 200 });
    };

    renderInRouter();

    await user.type(screen.getByLabelText(/標題/), "Q3");
    await user.type(screen.getByLabelText(/對方顯示名稱/), "林經理");
    await user.type(screen.getByLabelText(/我方顯示名稱/), "Sean");
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    await waitFor(() => {
      expect(screen.getByTestId("redirected-detail")).toBeDefined();
    });
    expect(posted).not.toBeNull();
    expect(posted!.url).toContain("/api/meetings");
    expect(posted!.body).toEqual({
      title: "Q3",
      counterparty_display_name: "林經理",
      me_display_name: "Sean",
    });
  });

  test("backend error_code is rendered as localized message", async () => {
    const user = userEvent.setup();
    fetchHandler = async (_, init) => {
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify({
            error_code: "meeting.title.required",
            message: "Title is required",
          }),
          { status: 422, headers: { "content-type": "application/json" } },
        );
      }
      return new Response("[]", { status: 200 });
    };

    renderInRouter();

    await user.type(screen.getByLabelText(/標題/), "x");
    await user.type(screen.getByLabelText(/對方顯示名稱/), "C");
    await user.type(screen.getByLabelText(/我方顯示名稱/), "M");
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    await waitFor(() => {
      // zh-TW: errors.meeting.title.required → "請輸入會議標題"
      expect(screen.getByText("請輸入會議標題")).toBeDefined();
    });
  });
});
