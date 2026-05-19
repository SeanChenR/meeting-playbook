/**
 * MeetingsViewTabs — refactor-meetings-tabs-unified task 1.1.
 *
 * Asserts the controlled Tabs contract: rendered active state matches the
 * `value` prop, and clicking the inactive trigger updates the `?view`
 * search parameter on `/meetings` (pathname never changes; the legacy
 * `/meetings/calendar` route does not exist).
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
  // Single /meetings route — view is derived from ?view search param.
  const listRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings",
    component: () => <MeetingsViewTabs value={initialValue} />,
  });
  const routeTree = rootRoute.addChildren([listRoute]);
  const initialEntry = initialValue === "kanban" ? "/meetings" : "/meetings?view=calendar";
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
  test("(1.1a) value='kanban' renders Kanban as active", async () => {
    await _renderTabs("kanban");
    const kanban = screen.getByTestId("meetings-view-tab-kanban");
    const calendar = screen.getByTestId("meetings-view-tab-calendar");
    expect(kanban.getAttribute("data-state")).toBe("active");
    expect(calendar.getAttribute("data-state")).toBe("inactive");
  });

  test("(1.1b) clicking calendar trigger sets ?view=calendar; pathname stays /meetings", async () => {
    const user = userEvent.setup();
    const router = await _renderTabs("kanban");
    await user.click(screen.getByTestId("meetings-view-tab-calendar"));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/meetings");
      const search = router.state.location.search as { view?: string };
      expect(search.view).toBe("calendar");
    });
  });

  test("(1.1c) clicking kanban trigger from calendar removes ?view; pathname stays /meetings", async () => {
    const user = userEvent.setup();
    const router = await _renderTabs("calendar");
    await user.click(screen.getByTestId("meetings-view-tab-kanban"));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/meetings");
      const search = router.state.location.search as { view?: string };
      expect(search.view).toBeUndefined();
    });
  });
});
