/**
 * meetingsListQueryOptions / meetingQueryOptions surface contract.
 *
 * Slices that consume these options pass them straight to `useQuery`. The
 * queryKey shape determines cache invalidation across pages — keep it
 * stable: `["meetings"]` for the list, `["meetings", id]` for a single row.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { meetingQueryOptions, meetingsListQueryOptions } from "./meetings-api";

const originalFetch = globalThis.fetch;
let fetchCalls: Array<{ url: string; init?: RequestInit }> = [];

beforeEach(() => {
  fetchCalls = [];
  globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    fetchCalls.push({ url, init });
    if (url.endsWith("/api/meetings")) {
      return new Response("[]", {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("/api/meetings/")) {
      return new Response(
        JSON.stringify({
          id: "m_test",
          user_id: "u",
          title: "T",
          counterparty_display_name: "C",
          me_display_name: "M",
          status: "scheduled",
          asr_provider: "whisper",
          calendar_event_id: null,
          created_at: "2026-05-07T10:00:00Z",
          started_at: null,
          ended_at: null,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    return new Response("not found", { status: 404 });
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("meetingsListQueryOptions", () => {
  test("queryKey is the bare ['meetings'] tuple", () => {
    const opts = meetingsListQueryOptions();
    expect(opts.queryKey).toEqual(["meetings"]);
  });

  test("queryFn fetches GET /api/meetings and returns the list", async () => {
    const opts = meetingsListQueryOptions();
    const result = await (opts.queryFn as () => Promise<unknown[]>)();
    expect(result).toEqual([]);
    expect(fetchCalls[0]?.url).toContain("/api/meetings");
  });
});

describe("meetingQueryOptions", () => {
  test("queryKey is ['meetings', id]", () => {
    const opts = meetingQueryOptions("m_abc");
    expect(opts.queryKey).toEqual(["meetings", "m_abc"]);
  });

  test("queryFn fetches GET /api/meetings/{id}", async () => {
    const opts = meetingQueryOptions("m_test");
    type ReadShape = { id: string; title: string };
    const result = await (opts.queryFn as () => Promise<ReadShape>)();
    expect(result.id).toBe("m_test");
    expect(fetchCalls[0]?.url).toContain("/api/meetings/m_test");
  });
});
