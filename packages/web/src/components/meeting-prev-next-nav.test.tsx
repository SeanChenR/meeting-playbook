/**
 * MeetingPrevNextNav — slice meetings-ux-revamp task 5.1.
 *
 * Covers the spec scenarios:
 *   (a) cache hit + middle position → both arrows enabled, hrefs
 *       point to the correct neighbours
 *   (b) cache miss → both arrows disabled
 *   (c) edge position (first / last) → corresponding arrow disabled
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
import { cleanup, render, screen } from "@testing-library/react";

import { MeetingPrevNextNav } from "./meeting-prev-next-nav";
import { ThemeProvider } from "../lib/theme-provider";
import { type Meeting, meetingsListQueryOptions } from "../lib/meetings-api";

afterEach(cleanup);

function _meeting(overrides: Partial<Meeting>): Meeting {
  return {
    id: "id",
    user_id: "u",
    title: "T",
    counterparty_display_name: "林",
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

// Three meetings sorted by scheduled_start_at ASC: a (earliest), b, c.
const A = _meeting({ id: "a", scheduled_start_at: "2026-05-10T10:00:00Z" });
const B = _meeting({ id: "b", scheduled_start_at: "2026-05-15T10:00:00Z" });
const C = _meeting({ id: "c", scheduled_start_at: "2026-05-20T10:00:00Z" });

async function _renderNav(currentId: string, seedCache: Meeting[] | null) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  if (seedCache !== null) {
    queryClient.setQueryData(meetingsListQueryOptions().queryKey, seedCache);
  }
  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const detailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/$id",
    component: () => <MeetingPrevNextNav currentId={currentId} />,
  });
  const listRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings",
    component: () => <div data-testid="on-list">on list</div>,
  });
  const routeTree = rootRoute.addChildren([detailRoute, listRoute]);
  const history = createMemoryHistory({ initialEntries: [`/meetings/${currentId}`] });
  const router = createRouter({ routeTree, history });
  await router.load();
  render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        <RouterProvider
          router={router as unknown as Parameters<typeof RouterProvider>[0]["router"]}
        />
      </QueryClientProvider>
    </ThemeProvider>,
  );
}

describe("MeetingPrevNextNav", () => {
  test("(5.1a) cache hit + middle position: both arrows enabled with right hrefs", async () => {
    await _renderNav("b", [A, B, C]);
    const prev = screen.getByTestId("meeting-prev-link") as HTMLAnchorElement;
    const next = screen.getByTestId("meeting-next-link") as HTMLAnchorElement;
    expect(prev.getAttribute("href")).toBe("/meetings/a");
    expect(next.getAttribute("href")).toBe("/meetings/c");
  });

  test("(5.1b) cache miss: both arrows render disabled", async () => {
    await _renderNav("b", null);
    expect(screen.queryByTestId("meeting-prev-link")).toBeNull();
    expect(screen.queryByTestId("meeting-next-link")).toBeNull();
    const prev = screen.getByTestId("meeting-prev-disabled") as HTMLButtonElement;
    const next = screen.getByTestId("meeting-next-disabled") as HTMLButtonElement;
    expect(prev.disabled).toBe(true);
    expect(next.disabled).toBe(true);
  });

  test("(5.1c) first meeting: prev disabled, next enabled", async () => {
    await _renderNav("a", [A, B, C]);
    expect(screen.getByTestId("meeting-prev-disabled")).toBeDefined();
    expect(screen.getByTestId("meeting-next-link").getAttribute("href")).toBe("/meetings/b");
  });

  test("(5.1c) last meeting: next disabled, prev enabled", async () => {
    await _renderNav("c", [A, B, C]);
    expect(screen.getByTestId("meeting-prev-link").getAttribute("href")).toBe("/meetings/b");
    expect(screen.getByTestId("meeting-next-disabled")).toBeDefined();
  });

  test("BackLink to /meetings always renders alongside the arrows", async () => {
    await _renderNav("b", [A, B, C]);
    const backLink = screen.getByTestId("back-link") as HTMLAnchorElement;
    expect(backLink.getAttribute("href")).toBe("/meetings");
  });
});
