/**
 * Tag filter / view tabs round-trip test — slice-17 task 6.1.
 *
 * Verifies that switching between meetings views (list ↔ calendar) does NOT
 * clobber the `?tag_ids=` URL search param: the filter selection MUST
 * survive the navigate because it lives in URL state (per design decision
 * "用 search param 不用 path").
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderAppRoutes } from "../../test/fixtures/router";
import { routeTree } from "../../route-tree";

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

describe("Tag filter survives view-tab switching", () => {
  beforeEach(() => {
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    cleanup();
  });

  test("clicking the calendar view tab from /meetings?tag_ids=t_a preserves the param", async () => {
    fetchHandler = async () =>
      new Response("[]", { status: 200, headers: { "content-type": "application/json" } });

    const { router } = await renderAppRoutes(routeTree, {
      initialEntries: ["/meetings?tag_ids=t_a"],
    });

    // The shared MeetingsViewTabs renders calendar as a Link; clicking it
    // should keep the filter param in the URL.
    const calendarTab = await screen.findByTestId("meetings-view-tab-calendar");
    const user = userEvent.setup();
    await user.click(calendarTab);

    await waitFor(() => {
      expect(router.history.location.pathname).toBe("/meetings/calendar");
      expect(router.history.location.search).toContain("tag_ids=t_a");
    });
  });
});
