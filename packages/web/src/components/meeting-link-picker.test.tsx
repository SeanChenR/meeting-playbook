/**
 * MeetingLinkPicker — slice-21 task 5.1.
 *
 * Four scenarios from spec:
 *   (a) Picker excludes the current meeting and already-linked meetings
 *   (b) Cache miss surfaces hint instead of empty list
 *   (c) Successful link creation closes modal + invalidates query
 *   (d) Duplicate link rejection keeps modal open + shows localized error
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
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

import { MeetingLinkPicker } from "./meeting-link-picker";
import { ThemeProvider } from "../lib/theme-provider";
import type { MeetingLinkView } from "../lib/meeting-links-api";
import { meetingsListQueryOptions, type Meeting } from "../lib/meetings-api";

afterEach(cleanup);

const _originalFetch = globalThis.fetch;
beforeEach(() => {
  globalThis.fetch = (async () => {
    throw new Error("fetch was not stubbed for this test");
  }) as unknown as typeof fetch;
});
afterEach(() => {
  globalThis.fetch = _originalFetch;
});

function _meeting(overrides: Partial<Meeting>): Meeting {
  return {
    id: "id",
    user_id: "u",
    title: "T",
    counterparty_display_name: "C",
    me_display_name: "Me",
    status: "scheduled",
    asr_provider: "qwen3",
    calendar_event_id: null,
    created_at: "2026-01-01T00:00:00Z",
    started_at: null,
    ended_at: null,
    scheduled_start_at: "2026-06-15T14:00:00Z",
    scheduled_end_at: null,
    ...overrides,
  };
}

function _link(overrides: Partial<MeetingLinkView>): MeetingLinkView {
  return {
    link_id: "link-1",
    other_meeting_id: "m_x",
    other_meeting_title: "X",
    other_meeting_scheduled_start_at: "2026-05-10T14:00:00Z",
    link_type: "related",
    created_at: "2026-05-09T00:00:00Z",
    ...overrides,
  };
}

async function _renderPicker(opts: {
  currentMeetingId: string;
  existingLinks: MeetingLinkView[];
  cachedMeetings: Meeting[] | undefined;
  onClose?: () => void;
}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
  if (opts.cachedMeetings !== undefined) {
    queryClient.setQueryData(meetingsListQueryOptions().queryKey, opts.cachedMeetings);
  }

  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const childRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/$id",
    component: () => (
      <MeetingLinkPicker
        currentMeetingId={opts.currentMeetingId}
        existingLinks={opts.existingLinks}
        onClose={opts.onClose ?? (() => {})}
      />
    ),
  });
  const listRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings",
    component: () => <div data-testid="on-list">on list</div>,
  });
  const routeTree = rootRoute.addChildren([childRoute, listRoute]);
  const history = createMemoryHistory({
    initialEntries: [`/meetings/${opts.currentMeetingId}`],
  });
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
  return { queryClient };
}

describe("MeetingLinkPicker", () => {
  test("(a) candidates exclude current meeting and already-linked meetings", async () => {
    // Spec example row 2: cached A,B,C,D; current = A; existing link A↔C → candidates = B, D.
    await _renderPicker({
      currentMeetingId: "A",
      existingLinks: [_link({ link_id: "L_ac", other_meeting_id: "C" })],
      cachedMeetings: [
        _meeting({ id: "A", title: "A" }),
        _meeting({ id: "B", title: "B" }),
        _meeting({ id: "C", title: "C" }),
        _meeting({ id: "D", title: "D" }),
      ],
    });

    expect(screen.getByTestId("meeting-link-picker-row-B")).toBeDefined();
    expect(screen.getByTestId("meeting-link-picker-row-D")).toBeDefined();
    expect(screen.queryByTestId("meeting-link-picker-row-A")).toBeNull();
    expect(screen.queryByTestId("meeting-link-picker-row-C")).toBeNull();
  });

  test("(b) cache miss renders the hint + a link to /meetings, no fetch", async () => {
    let fetchCalled = false;
    globalThis.fetch = (async () => {
      fetchCalled = true;
      return new Response(null, { status: 200 });
    }) as unknown as typeof fetch;

    await _renderPicker({
      currentMeetingId: "A",
      existingLinks: [],
      cachedMeetings: undefined,
    });

    expect(screen.getByTestId("meeting-link-picker-cache-miss")).toBeDefined();
    const hintLink = screen.getByTestId("meeting-link-picker-cache-miss-link") as HTMLAnchorElement;
    expect(hintLink.getAttribute("href")).toBe("/meetings");
    // The picker MUST NOT issue any backfill fetch.
    expect(fetchCalled).toBe(false);
  });

  test("(c) successful create closes the modal and invalidates the links query", async () => {
    let onCloseCalls = 0;
    let createUrl = "";
    let createBody = "";
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      createUrl = url;
      createBody = init?.body as string;
      return new Response(JSON.stringify({ link_id: "new-link-uuid" }), {
        status: 201,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    await _renderPicker({
      currentMeetingId: "A",
      existingLinks: [],
      cachedMeetings: [_meeting({ id: "A", title: "A" }), _meeting({ id: "B", title: "B" })],
      onClose: () => {
        onCloseCalls += 1;
      },
    });

    await userEvent.click(screen.getByTestId("meeting-link-picker-row-B"));
    await userEvent.click(screen.getByTestId("meeting-link-picker-confirm"));

    await waitFor(() => {
      expect(onCloseCalls).toBe(1);
    });
    expect(createUrl).toBe("/api/meetings/A/links");
    expect(createBody).toBe(JSON.stringify({ to_meeting_id: "B" }));
  });

  test("(d) 409 duplicate keeps modal open and renders localized error", async () => {
    let onCloseCalls = 0;
    globalThis.fetch = (async () => {
      return new Response(
        JSON.stringify({
          error_code: "meeting_link.duplicate",
          message: "Already linked",
        }),
        { status: 409, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    await _renderPicker({
      currentMeetingId: "A",
      existingLinks: [],
      cachedMeetings: [_meeting({ id: "A", title: "A" }), _meeting({ id: "B", title: "B" })],
      onClose: () => {
        onCloseCalls += 1;
      },
    });

    await userEvent.click(screen.getByTestId("meeting-link-picker-row-B"));
    await userEvent.click(screen.getByTestId("meeting-link-picker-confirm"));

    await waitFor(() => {
      const err = screen.getByTestId("meeting-link-picker-error");
      expect(err.textContent).toBe("這兩個會議已經連結了");
    });
    // Modal stays open — onClose was never called.
    expect(onCloseCalls).toBe(0);
  });
});
