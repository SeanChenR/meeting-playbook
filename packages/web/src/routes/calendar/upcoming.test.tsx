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
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

import { UpcomingEvents } from "./upcoming";

async function renderInRouter() {
  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const calendarRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/calendar/import",
    component: () => <UpcomingEvents />,
  });
  const detailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/$id",
    component: () => <div data-testid="redirected-detail">on detail</div>,
  });
  const newRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/new",
    component: () => <div data-testid="redirected-new">on new</div>,
  });
  const routeTree = rootRoute.addChildren([calendarRoute, detailRoute, newRoute]);
  const history = createMemoryHistory({ initialEntries: ["/calendar/import"] });
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

describe("UpcomingEvents page", () => {
  beforeEach(() => {
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("renders rows for fetched events with title and attendee count", async () => {
    fetchHandler = async () =>
      new Response(
        JSON.stringify([
          {
            id: "e_q3",
            title: "Q3 review with 林經理",
            start: "2026-05-09T10:00:00Z",
            end: "2026-05-09T11:00:00Z",
            attendees: ["lin@acme.com", "sean@example.com"],
            description: "",
            organizer: "Sean",
          },
          {
            id: "e_demo",
            title: "Product demo",
            start: "2026-05-09T14:00:00Z",
            end: "2026-05-09T15:00:00Z",
            attendees: ["a@b.com"],
            description: "",
            organizer: "Sean",
          },
        ]),
        { status: 200, headers: { "content-type": "application/json" } },
      );

    await renderInRouter();

    await waitFor(() => {
      expect(screen.getByText("Q3 review with 林經理")).toBeDefined();
      expect(screen.getByText("Product demo")).toBeDefined();
    });
    // Attendee counts render via the i18n template "{{count}} 人" / "{{count}} attendees"
    const attendeeCells = screen.getAllByTestId("calendar-row-attendees");
    expect(attendeeCells[0]?.textContent ?? "").toContain("2");
    expect(attendeeCells[1]?.textContent ?? "").toContain("1");
  });

  test("renders Connect Calendar CTA when query errors with calendar.not_connected", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify({ error_code: "calendar.not_connected", message: "..." }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });

    await renderInRouter();

    await waitFor(() => {
      expect(screen.getByTestId("calendar-connect-cta")).toBeDefined();
    });
    // zh-TW default: 連結 Google Calendar
    expect(screen.getByText(/連結 Google Calendar/)).toBeDefined();
  });

  // ─── Slice-20b: import button navigates to preview, no POST fired ────

  test("(slice-20b) clicking import navigates to /meetings/new?from_calendar=<id> without firing any POST", async () => {
    const user = userEvent.setup();
    let postCalled = false;
    fetchHandler = async (url, init) => {
      if (init?.method === "POST") {
        postCalled = true;
      }
      if (url.includes("/api/calendar/upcoming")) {
        return new Response(
          JSON.stringify([
            {
              id: "e_x",
              title: "Discovery call",
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
      return new Response("[]", { status: 200 });
    };

    const { router } = await renderInRouter();

    await waitFor(() => {
      expect(screen.getByText("Discovery call")).toBeDefined();
    });

    await user.click(screen.getByRole("button", { name: /^匯入並生成$/ }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/meetings/new");
    });
    // The destination route receives the event id via the from_calendar
    // search param so the preview form can fetch the event detail.
    expect(router.state.location.search).toMatchObject({ from_calendar: "e_x" });
    // Spec: NO POST request is issued during the click handler.
    expect(postCalled).toBe(false);
  });
});
