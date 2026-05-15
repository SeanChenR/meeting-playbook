/**
 * /settings/tags route tests — slice-17 task 6.2.
 *
 * Covers:
 *   (a) delete dialog description contains the meeting_count value
 *   (b) inline rename on 422 surfaces the localized error and keeps the
 *       input editable
 *   (c) the recolor swatch picker contains exactly the palette colors
 *   (d) after a successful delete, the row disappears from the list
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithRouter } from "../../test/fixtures/router";
import { SettingsTags } from "./tags";
import { TAG_PALETTE } from "../../lib/tag-palette";

mock.module("../../lib/auth-client", () => ({
  authClient: {
    useSession: () => ({
      data: { user: { name: "Sean", email: "sean@example.com" } },
      isPending: false,
    }),
  },
}));

const ORIGINAL_FETCH = globalThis.fetch;

interface Setup {
  initialTags: Array<{ id: string; name: string; color: string; meeting_count?: number }>;
  patchHandler?: (
    tagId: string,
    body: { name?: string; color?: string },
  ) => Response | Promise<Response>;
}

interface FetchCallSummary {
  url: string;
  method: string;
  body: unknown;
}

function _installFetch(setup: Setup): FetchCallSummary[] {
  const calls: FetchCallSummary[] = [];
  let tags = [...setup.initialTags];

  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    calls.push({ url, method, body });

    if (method === "GET" && url.startsWith("/api/tags")) {
      return new Response(JSON.stringify(tags), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    const patchMatch = url.match(/^\/api\/tags\/([^/]+)$/);
    if (method === "PATCH" && patchMatch) {
      const tagId = patchMatch[1] as string;
      if (setup.patchHandler) {
        return setup.patchHandler(tagId, body as { name?: string; color?: string });
      }
      const idx = tags.findIndex((tag) => tag.id === tagId);
      if (idx >= 0 && tags[idx]) {
        const existing = tags[idx];
        const merged = {
          id: existing.id,
          name: (body as { name?: string }).name ?? existing.name,
          color: (body as { color?: string }).color ?? existing.color,
          meeting_count: existing.meeting_count,
        };
        tags[idx] = merged;
        return new Response(JSON.stringify(merged), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ error_code: "tag.not_found" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });
    }
    if (method === "DELETE" && patchMatch) {
      const tagId = patchMatch[1] as string;
      tags = tags.filter((tag) => tag.id !== tagId);
      return new Response(null, { status: 204 });
    }
    return new Response("not mocked", { status: 500 });
  }) as typeof fetch;
  return calls;
}

afterEach(() => {
  cleanup();
  globalThis.fetch = ORIGINAL_FETCH;
});

describe("SettingsTags route", () => {
  beforeEach(() => {
    // each test installs its own fetch
  });

  test("(a) delete dialog description shows the meeting_count from the list", async () => {
    _installFetch({
      initialTags: [{ id: "tag_a", name: "客戶X", color: "#DDD6FE", meeting_count: 5 }],
    });
    const user = userEvent.setup();
    await renderWithRouter(<SettingsTags />, {
      initialEntries: ["/settings/tags"],
      path: "/settings/tags",
    });

    const row = await screen.findByTestId("settings-tags-row-tag_a");
    await user.click(within(row).getByTestId("settings-tags-delete-button"));

    const description = await screen.findByTestId("settings-tags-delete-description");
    expect(description.textContent ?? "").toContain("5");
  });

  test("(b) rename 422 surfaces localized error and keeps input editable", async () => {
    _installFetch({
      initialTags: [
        { id: "tag_a", name: "客戶X", color: "#DDD6FE", meeting_count: 0 },
        { id: "tag_b", name: "客戶Y", color: "#FEF3C7", meeting_count: 0 },
      ],
      patchHandler: () =>
        new Response(
          JSON.stringify({
            error_code: "tag.name_taken",
            message: "Tag name already exists",
          }),
          { status: 422, headers: { "content-type": "application/json" } },
        ),
    });
    const user = userEvent.setup();
    await renderWithRouter(<SettingsTags />, {
      initialEntries: ["/settings/tags"],
      path: "/settings/tags",
    });

    const row = await screen.findByTestId("settings-tags-row-tag_b");
    await user.click(within(row).getByTestId("settings-tags-rename-button"));

    const input = await within(row).findByTestId("settings-tags-rename-input");
    await user.clear(input);
    await user.type(input, "客戶x");
    await user.click(within(row).getByTestId("settings-tags-rename-submit"));

    const errorEl = await within(row).findByTestId("settings-tags-rename-error");
    expect(errorEl.textContent ?? "").not.toHaveLength(0);
    // Input remains and is focused / editable.
    const inputStill = within(row).getByTestId("settings-tags-rename-input");
    expect((inputStill as HTMLInputElement).disabled).toBe(false);
  });

  test("(c) recolor swatch shows only palette colors, no free-form input", async () => {
    _installFetch({
      initialTags: [{ id: "tag_a", name: "客戶X", color: "#DDD6FE", meeting_count: 0 }],
    });
    const user = userEvent.setup();
    await renderWithRouter(<SettingsTags />, {
      initialEntries: ["/settings/tags"],
      path: "/settings/tags",
    });

    const row = await screen.findByTestId("settings-tags-row-tag_a");
    await user.click(within(row).getByTestId("settings-tags-recolor-button"));
    const swatchContainer = await within(row).findByTestId("settings-tags-recolor-swatches");
    const swatches = within(swatchContainer).getAllByRole("button");
    expect(swatches.length).toBe(TAG_PALETTE.length);
    // No free-form input field.
    const freeFormInputs = swatchContainer.querySelectorAll(
      "input[type='text'], input[type='color']",
    );
    expect(freeFormInputs.length).toBe(0);
  });

  test("(d) successful delete removes the row", async () => {
    _installFetch({
      initialTags: [
        { id: "tag_a", name: "客戶X", color: "#DDD6FE", meeting_count: 3 },
        { id: "tag_b", name: "面試", color: "#FEF3C7", meeting_count: 0 },
      ],
    });
    const user = userEvent.setup();
    await renderWithRouter(<SettingsTags />, {
      initialEntries: ["/settings/tags"],
      path: "/settings/tags",
    });

    const row = await screen.findByTestId("settings-tags-row-tag_a");
    await user.click(within(row).getByTestId("settings-tags-delete-button"));
    await user.click(await screen.findByTestId("settings-tags-delete-confirm"));

    await waitFor(() => {
      expect(screen.queryByTestId("settings-tags-row-tag_a")).toBeNull();
    });
    expect(screen.getByTestId("settings-tags-row-tag_b")).toBeDefined();
  });
});
