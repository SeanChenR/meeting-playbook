/**
 * TagFilter tests — slice-17 task 5.3.
 *
 * Mocks `GET /api/tags` and verifies:
 *   (c) toggling tags writes the selection to the URL `?tag_ids=` param
 *   (d) the dropdown trigger label includes the selected count
 */

import { afterEach, describe, expect, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Tag } from "../../lib/tags-api";
import { renderWithRouter } from "../../test/fixtures/router";
import { TagFilter } from "./tag-filter";

const ORIGINAL_FETCH = globalThis.fetch;

function _installFetch(list: Tag[]) {
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.startsWith("/api/tags")) {
      return new Response(JSON.stringify(list), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not mocked", { status: 500 });
  }) as typeof fetch;
}

afterEach(() => {
  cleanup();
  globalThis.fetch = ORIGINAL_FETCH;
});

describe("TagFilter", () => {
  const sampleTags: Tag[] = [
    {
      id: "ta",
      user_id: "u_a",
      name: "客戶X",
      color: "#DDD6FE",
      created_at: "2026-05-10T00:00:00Z",
    },
    {
      id: "tb",
      user_id: "u_a",
      name: "面試",
      color: "#FEF3C7",
      created_at: "2026-05-11T00:00:00Z",
    },
  ];

  test("toggling tags updates the URL search param", async () => {
    _installFetch(sampleTags);
    const user = userEvent.setup();
    const { router } = await renderWithRouter(<TagFilter />, {
      initialEntries: ["/meetings"],
      path: "/meetings",
    });

    await user.click(screen.getByTestId("tag-filter-trigger"));
    const optA = await screen.findByTestId("tag-filter-option-ta");
    await user.click(optA);
    const optB = await screen.findByTestId("tag-filter-option-tb");
    await user.click(optB);

    await waitFor(() => {
      const search = router.history.location.search;
      expect(search).toContain("tag_ids=");
      expect(search).toContain("ta");
      expect(search).toContain("tb");
    });
  });

  test("trigger label includes the selected count", async () => {
    _installFetch(sampleTags);
    const user = userEvent.setup();
    await renderWithRouter(<TagFilter />, {
      initialEntries: ["/meetings?tag_ids=ta,tb"],
      path: "/meetings",
    });

    await waitFor(() => {
      const trigger = screen.getByTestId("tag-filter-trigger");
      expect(trigger.textContent ?? "").toMatch(/\(2\)/);
    });
    // Sanity — confirm option list mounts under the trigger.
    await user.click(screen.getByTestId("tag-filter-trigger"));
    const optA = await screen.findByTestId("tag-filter-option-ta");
    expect(optA.getAttribute("data-selected")).toBe("true");
  });
});
