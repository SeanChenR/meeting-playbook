/**
 * MeetingsViewTabs — slice meetings-ux-revamp task 3.1.
 *
 * Asserts the controlled Tabs contract: rendered active state matches
 * the `value` prop, and clicking the inactive trigger fires a router
 * navigate to the corresponding meetings route.
 *
 * Uses an inline 2-route memory router so navigation between
 * /meetings and /meetings/calendar resolves correctly. The shared
 * `renderWithRouter` fixture only registers one synthetic route per
 * call, so we wire both here.
 */

import { afterEach, describe, expect, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MeetingsViewTabs, type MeetingsView } from "./meetings-view-tabs";
import { ThemeProvider } from "../lib/theme-provider";

afterEach(cleanup);

async function _renderTabs(initialValue: MeetingsView) {
  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const listRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings",
    component: () => <MeetingsViewTabs value="kanban" />,
  });
  const calendarRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/calendar",
    component: () => <MeetingsViewTabs value="calendar" />,
  });
  const routeTree = rootRoute.addChildren([listRoute, calendarRoute]);
  const initialEntry = initialValue === "kanban" ? "/meetings" : "/meetings/calendar";
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createRouter({ routeTree, history });
  await router.load();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        <RouterProvider
          router={router as unknown as Parameters<typeof RouterProvider>[0]["router"]}
        />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return router;
}

describe("MeetingsViewTabs", () => {
  test("(3.1a) value='kanban' renders Kanban as active", async () => {
    await _renderTabs("kanban");
    const kanban = screen.getByTestId("meetings-view-tab-kanban");
    const calendar = screen.getByTestId("meetings-view-tab-calendar");
    expect(kanban.getAttribute("data-state")).toBe("active");
    expect(calendar.getAttribute("data-state")).toBe("inactive");
  });

  test("(3.1b) clicking calendar trigger navigates to /meetings/calendar", async () => {
    const user = userEvent.setup();
    const router = await _renderTabs("kanban");
    await user.click(screen.getByTestId("meetings-view-tab-calendar"));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/meetings/calendar");
    });
  });

  test("(3.1c) clicking kanban trigger from calendar navigates to /meetings", async () => {
    const user = userEvent.setup();
    const router = await _renderTabs("calendar");
    await user.click(screen.getByTestId("meetings-view-tab-kanban"));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/meetings");
    });
  });
});
