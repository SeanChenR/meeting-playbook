import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider } from "../../lib/theme-provider";

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

async function renderInRouter(initialEntry = "/meetings/new") {
  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const newRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/new",
    component: () => <NewMeeting />,
  });
  const detailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/$id",
    component: () => <div data-testid="redirected-detail">on detail</div>,
  });
  const listRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings",
    component: () => <div data-testid="redirected-list">on list</div>,
  });
  const calendarRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/calendar",
    component: () => <div data-testid="redirected-calendar">on calendar</div>,
  });
  const routeTree = rootRoute.addChildren([newRoute, detailRoute, listRoute, calendarRoute]);
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createRouter({ routeTree, history });
  await router.load();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return { router };
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

    await renderInRouter();
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    expect(postCalled).toBe(false);
  });

  test("submitting valid fields posts and navigates to /meetings/:id", async () => {
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

    const { router } = await renderInRouter();

    await user.type(screen.getByLabelText(/標題/), "Q3");
    await user.type(screen.getByLabelText(/對方顯示名稱/), "林經理");
    await user.type(screen.getByLabelText(/我方顯示名稱/), "Sean");
    // Slice-15: scheduled_start_at is required. Fill the date input.
    const dateInput = screen.getByTestId("meeting-date") as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: "2026-06-15" } });
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/meetings/m_abc");
    });
    expect(posted).not.toBeNull();
    expect(posted!.url).toContain("/api/meetings");
    const postedBody = posted!.body as Record<string, unknown>;
    expect(postedBody.title).toBe("Q3");
    expect(postedBody.counterparty_display_name).toBe("林經理");
    expect(postedBody.me_display_name).toBe("Sean");
    expect(typeof postedBody.scheduled_start_at).toBe("string");
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

    await renderInRouter();

    await user.type(screen.getByLabelText(/標題/), "x");
    await user.type(screen.getByLabelText(/對方顯示名稱/), "C");
    await user.type(screen.getByLabelText(/我方顯示名稱/), "M");
    fireEvent.change(screen.getByTestId("meeting-date") as HTMLInputElement, {
      target: { value: "2026-06-15" },
    });
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    await waitFor(() => {
      expect(screen.getByText("請輸入會議標題")).toBeDefined();
    });
  });

  // ─── Slice meetings-ux-revamp task 4.1 — ?from=calendar redirect ───

  test("(4.1) ?from=calendar → submit redirects to /meetings/calendar", async () => {
    const user = userEvent.setup();
    fetchHandler = async (_url, init) => {
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "m_xyz",
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

    const { router } = await renderInRouter("/meetings/new?from=calendar");

    await user.type(screen.getByLabelText(/標題/), "Q3");
    await user.type(screen.getByLabelText(/對方顯示名稱/), "林經理");
    await user.type(screen.getByLabelText(/我方顯示名稱/), "Sean");
    fireEvent.change(screen.getByTestId("meeting-date") as HTMLInputElement, {
      target: { value: "2026-06-15" },
    });
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/meetings/calendar");
    });
  });

  test("(4.1) ?from=calendar → cancel link points to /meetings/calendar", async () => {
    fetchHandler = async () => new Response("[]", { status: 200 });
    await renderInRouter("/meetings/new?from=calendar");
    const cancelLink = screen.getByRole("link", { name: /取消/ });
    expect(cancelLink.getAttribute("href")).toBe("/meetings/calendar");
  });

  test("(4.1) no from param → cancel link points to /meetings (default)", async () => {
    fetchHandler = async () => new Response("[]", { status: 200 });
    await renderInRouter("/meetings/new");
    const cancelLink = screen.getByRole("link", { name: /取消/ });
    expect(cancelLink.getAttribute("href")).toBe("/meetings");
  });

  test("(4.1) ?from=somewhere-else → submit falls back to /meetings/$id", async () => {
    const user = userEvent.setup();
    fetchHandler = async (_url, init) => {
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "m_fallback",
            user_id: "u",
            title: "X",
            counterparty_display_name: "C",
            me_display_name: "M",
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

    const { router } = await renderInRouter("/meetings/new?from=somewhere-else");
    await user.type(screen.getByLabelText(/標題/), "X");
    await user.type(screen.getByLabelText(/對方顯示名稱/), "C");
    await user.type(screen.getByLabelText(/我方顯示名稱/), "M");
    fireEvent.change(screen.getByTestId("meeting-date") as HTMLInputElement, {
      target: { value: "2026-06-15" },
    });
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/meetings/m_fallback");
    });
  });

  // ─── Slice-15: scheduled_start_at is now required ─────────────────────

  test("(slice-15) new meeting requires scheduled_start_at", async () => {
    const user = userEvent.setup();
    let postCalled = false;
    fetchHandler = async (_, init) => {
      if (init?.method === "POST") {
        postCalled = true;
        return new Response("{}", { status: 201 });
      }
      return new Response("[]", { status: 200 });
    };

    await renderInRouter();

    await user.type(screen.getByLabelText(/標題/), "no date");
    await user.type(screen.getByLabelText(/對方顯示名稱/), "C");
    await user.type(screen.getByLabelText(/我方顯示名稱/), "M");
    // Intentionally omit the date input.
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    // HTML5 `required` on the date input blocks the submit; the form's
    // own onSubmit guard also rejects. Either way, no POST should fire.
    await waitFor(() => {
      expect(postCalled).toBe(false);
    });
  });

  test("(slice-15) new meeting rejects end-before-start", async () => {
    const user = userEvent.setup();
    let postCalled = false;
    fetchHandler = async (_, init) => {
      if (init?.method === "POST") {
        postCalled = true;
        return new Response("{}", { status: 201 });
      }
      return new Response("[]", { status: 200 });
    };

    await renderInRouter();

    await user.type(screen.getByLabelText(/標題/), "bad range");
    await user.type(screen.getByLabelText(/對方顯示名稱/), "C");
    await user.type(screen.getByLabelText(/我方顯示名稱/), "M");
    fireEvent.change(screen.getByTestId("meeting-date") as HTMLInputElement, {
      target: { value: "2026-06-15" },
    });
    fireEvent.change(screen.getByTestId("meeting-time") as HTMLInputElement, {
      target: { value: "14:00" },
    });
    fireEvent.change(screen.getByTestId("meeting-end-time") as HTMLInputElement, {
      target: { value: "13:00" },
    });
    await user.click(screen.getByRole("button", { name: /建立$/ }));

    await waitFor(() => {
      expect(screen.getByText(/結束時間必須晚於開始時間/)).toBeDefined();
    });
    expect(postCalled).toBe(false);
  });
});
