/**
 * MeetingLinksSection — slice-21 task 4.2.
 *
 * Five scenarios from `meeting-detail-layout/spec.md`:
 *   (a) Empty state renders heading + empty hint + add button
 *   (b) Linked meetings render as navigation links with delete affordance
 *   (c) Collapse triggers when link count exceeds ten
 *   (d) Add button opens the MeetingLinkPicker modal
 *   (e) Delete icon removes the link inline
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

import { MeetingLinksSection } from "./meeting-links-section";
import { ThemeProvider } from "../lib/theme-provider";
import { meetingLinksQueryOptions, type MeetingLinkView } from "../lib/meeting-links-api";
import { meetingsListQueryOptions, type Meeting } from "../lib/meetings-api";

afterEach(cleanup);

const _originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = (async (_url: string, init?: RequestInit) => {
    // Default: every DELETE returns 204; no other fetch should be issued
    // during these tests (queries are pre-seeded into React Query cache).
    if (init?.method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    return new Response(JSON.stringify({ links: [] }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = _originalFetch;
});

function _link(overrides: Partial<MeetingLinkView>): MeetingLinkView {
  return {
    link_id: "link-1",
    other_meeting_id: "m_other",
    other_meeting_title: "Other meeting",
    other_meeting_scheduled_start_at: "2026-05-10T14:00:00Z",
    link_type: "related",
    created_at: "2026-05-09T00:00:00Z",
    ...overrides,
  };
}

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

async function _renderSection(meetingId: string, links: MeetingLinkView[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  });
  queryClient.setQueryData(meetingLinksQueryOptions(meetingId).queryKey, links);
  // Seed an empty meetings list so the picker's cacheMiss branch does NOT
  // fire when the add button opens the modal.
  queryClient.setQueryData(meetingsListQueryOptions().queryKey, [
    _meeting({ id: meetingId, title: "Current" }),
    _meeting({ id: "m_pick", title: "Pick me" }),
  ]);

  const rootRoute = createRootRoute({ component: () => <Outlet /> });
  const detailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings/$id",
    component: () => <MeetingLinksSection meetingId={meetingId} />,
  });
  const otherRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/meetings",
    component: () => <div data-testid="on-list">on list</div>,
  });
  const routeTree = rootRoute.addChildren([detailRoute, otherRoute]);
  const history = createMemoryHistory({ initialEntries: [`/meetings/${meetingId}`] });
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

describe("MeetingLinksSection", () => {
  test("(a) empty state renders heading, empty hint and add button", async () => {
    await _renderSection("m_a", []);
    const section = screen.getByTestId("meeting-links-section");
    expect(section).toBeDefined();
    expect(screen.getByTestId("meeting-links-empty")).toBeDefined();
    expect(screen.getByTestId("meeting-links-add-button")).toBeDefined();
  });

  test("(b) linked meetings render as navigation links + delete buttons", async () => {
    const links = [
      _link({ link_id: "L1", other_meeting_id: "m_b", other_meeting_title: "B" }),
      _link({ link_id: "L2", other_meeting_id: "m_c", other_meeting_title: "C" }),
    ];
    await _renderSection("m_a", links);

    const row1 = screen.getByTestId("meeting-link-row-L1") as HTMLAnchorElement;
    const row2 = screen.getByTestId("meeting-link-row-L2") as HTMLAnchorElement;
    expect(row1.getAttribute("href")).toBe("/meetings/m_b");
    expect(row2.getAttribute("href")).toBe("/meetings/m_c");
    expect(screen.getByTestId("meeting-link-delete-L1")).toBeDefined();
    expect(screen.getByTestId("meeting-link-delete-L2")).toBeDefined();
  });

  test("(c) collapse activates when count exceeds ten", async () => {
    const links = Array.from({ length: 15 }, (_, i) =>
      _link({
        link_id: `L${i}`,
        other_meeting_id: `m_${i}`,
        other_meeting_title: `T${i}`,
      }),
    );
    await _renderSection("m_a", links);

    const section = screen.getByTestId("meeting-links-section");

    // Default collapsed → exactly 10 rows visible.
    expect(
      section.querySelectorAll<HTMLElement>('[data-testid^="meeting-link-row-L"]').length,
    ).toBe(10);
    const toggle = screen.getByTestId("meeting-links-toggle");
    expect(toggle.textContent).toContain("展開更多");

    // Toggle → all 15 visible, label flips.
    await userEvent.click(toggle);
    await waitFor(() => {
      expect(
        section.querySelectorAll<HTMLElement>('[data-testid^="meeting-link-row-L"]').length,
      ).toBe(15);
    });
    expect(toggle.textContent).toContain("收合");
  });

  test("(d) add button opens the MeetingLinkPicker modal", async () => {
    await _renderSection("m_a", []);
    const addBtn = screen.getByTestId("meeting-links-add-button");
    await userEvent.click(addBtn);
    await waitFor(() => {
      expect(screen.getByTestId("meeting-link-picker")).toBeDefined();
    });
  });

  test("(e) delete icon click triggers a DELETE request for that link", async () => {
    const calls: Array<{ url: string; method: string }> = [];
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ url, method });
      // DELETE returns 204; GET returns an empty list so the post-invalidation
      // refetch resolves without error.
      if (method === "DELETE") return new Response(null, { status: 204 });
      return new Response(JSON.stringify({ links: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const links = [_link({ link_id: "L_del", other_meeting_id: "m_b", other_meeting_title: "B" })];
    await _renderSection("m_a", links);

    const deleteBtn = screen.getByTestId("meeting-link-delete-L_del");
    await userEvent.click(deleteBtn);

    await waitFor(() => {
      const del = calls.find((c) => c.method === "DELETE");
      expect(del).toBeDefined();
      expect(del?.url).toBe("/api/meetings/m_a/links/L_del");
    });
  });
});
