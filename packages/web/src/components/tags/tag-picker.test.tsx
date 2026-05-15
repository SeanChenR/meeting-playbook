/**
 * TagPicker tests — slice-17 task 5.3.
 *
 * Mocks the tag REST endpoints and verifies:
 *   (a) inline-create chains `POST /api/tags` → `POST /api/meetings/{id}/tags`
 *   (b) clicking an already-attached tag triggers `DELETE /api/meetings/{id}/tags/{tag_id}`
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Tag } from "../../lib/tags-api";
import { renderWithRouter } from "../../test/fixtures/router";
import { TagPicker } from "./tag-picker";

const ORIGINAL_FETCH = globalThis.fetch;

interface MockResponses {
  list: Tag[];
  createNew?: Tag;
}

type FetchCall = { url: string; method: string; body: unknown };

function _installFetch(responses: MockResponses): FetchCall[] {
  const calls: FetchCall[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    calls.push({ url, method, body });

    if (method === "GET" && url.startsWith("/api/tags")) {
      return new Response(JSON.stringify(responses.list), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (method === "POST" && url === "/api/tags") {
      const created: Tag = responses.createNew ?? {
        id: "tag_new",
        user_id: "u_a",
        name: (body as { name: string }).name,
        color: (body as { color: string }).color,
        created_at: "2026-05-15T00:00:00Z",
      };
      return new Response(JSON.stringify(created), {
        status: 201,
        headers: { "content-type": "application/json" },
      });
    }
    if (method === "POST" && /\/api\/meetings\/.+\/tags$/.test(url)) {
      return new Response(
        JSON.stringify({
          meeting_id: "m_x",
          tag_id: (body as { tag_id: string }).tag_id,
          attached_at: "2026-05-15T00:00:01Z",
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      );
    }
    if (method === "DELETE" && /\/api\/meetings\/.+\/tags\/.+$/.test(url)) {
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

describe("TagPicker", () => {
  test("inline-create chains create + attach", async () => {
    const calls = _installFetch({ list: [] });
    const user = userEvent.setup();
    await renderWithRouter(<TagPicker meetingId="m_x" currentTags={[]} />, {
      initialEntries: ["/meetings/m_x"],
      path: "/meetings/$id",
    });

    await user.click(screen.getByTestId("tag-picker-trigger"));
    const input = await screen.findByTestId("tag-picker-search");
    await user.type(input, "客戶Y");

    const createRow = await screen.findByTestId("tag-picker-create-row");
    await user.click(createRow);

    await waitFor(() => {
      const create = calls.find((c) => c.method === "POST" && c.url === "/api/tags");
      const attach = calls.find((c) => c.method === "POST" && c.url === "/api/meetings/m_x/tags");
      expect(create).toBeDefined();
      expect(attach).toBeDefined();
      expect((create?.body as { name: string }).name).toBe("客戶Y");
    });
  });

  test("clicking an attached tag fires detach", async () => {
    const attached: Tag = {
      id: "tag_attached",
      user_id: "u_a",
      name: "面試",
      color: "#FEF3C7",
      created_at: "2026-05-10T00:00:00Z",
    };
    const calls = _installFetch({ list: [attached] });
    const user = userEvent.setup();
    await renderWithRouter(<TagPicker meetingId="m_x" currentTags={[attached]} />, {
      initialEntries: ["/meetings/m_x"],
      path: "/meetings/$id",
    });

    await user.click(screen.getByTestId("tag-picker-trigger"));
    const row = await screen.findByTestId("tag-picker-row-tag_attached");
    await user.click(row);

    await waitFor(() => {
      const detach = calls.find(
        (c) => c.method === "DELETE" && c.url === "/api/meetings/m_x/tags/tag_attached",
      );
      expect(detach).toBeDefined();
    });
  });
});
