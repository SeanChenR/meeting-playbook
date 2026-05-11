/**
 * playbookQueryOptions / getPlaybook / upsertPlaybook surface contract.
 *
 * The cache key shape is `["playbook", meetingId]` — used by
 * `useUpsertPlaybookMutation` to invalidate after PUT. Keep it stable so
 * subsequent slices that mount the playbook see fresh data.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  getPlaybook,
  PlaybookApiError,
  playbookQueryOptions,
  upsertPlaybook,
} from "./playbook-api";

const originalFetch = globalThis.fetch;
let fetchCalls: Array<{ url: string; init?: RequestInit }> = [];

function _emptyPlaybook(meetingId: string) {
  return {
    id: "pb_test",
    meeting_id: meetingId,
    free_form_markdown: "",
    objective: "",
    counterparty_profile: "",
    anticipated_topics: "",
    anticipated_objections: "",
    talking_points: "",
    red_lines: "",
    created_at: "2026-05-07T10:00:00Z",
    updated_at: "2026-05-07T10:00:00Z",
  };
}

beforeEach(() => {
  fetchCalls = [];
  globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    fetchCalls.push({ url, init });
    if (init?.method === "PUT") {
      return new Response(JSON.stringify(_emptyPlaybook("m_test")), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("/playbook")) {
      return new Response(JSON.stringify(_emptyPlaybook("m_test")), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not found", { status: 404 });
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("playbookQueryOptions", () => {
  test("queryKey is ['playbook', meetingId]", () => {
    const opts = playbookQueryOptions("m_abc");
    expect(opts.queryKey).toEqual(["playbook", "m_abc"]);
  });

  test("queryFn fetches GET /api/meetings/{id}/playbook", async () => {
    const opts = playbookQueryOptions("m_test");
    const playbook = await (opts.queryFn as () => Promise<{ meeting_id: string }>)();
    expect(playbook.meeting_id).toBe("m_test");
    expect(fetchCalls[0]?.url).toContain("/api/meetings/m_test/playbook");
  });
});

describe("getPlaybook / upsertPlaybook error handling", () => {
  test("getPlaybook raises PlaybookApiError with errorCode on non-2xx", async () => {
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({ error_code: "meeting.not_found", message: "Meeting not found" }),
        { status: 404, headers: { "content-type": "application/json" } },
      )) as unknown as typeof fetch;

    let caught: unknown = null;
    try {
      await getPlaybook("m_x");
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(PlaybookApiError);
    const err = caught as PlaybookApiError;
    expect(err.status).toBe(404);
    expect(err.errorCode).toBe("meeting.not_found");
  });

  test("upsertPlaybook PUTs the JSON body and returns the persisted row", async () => {
    const result = await upsertPlaybook("m_test", {
      free_form_markdown: "# brief",
      objective: "obj",
      counterparty_profile: "",
      anticipated_topics: "",
      anticipated_objections: "",
      talking_points: "",
      red_lines: "",
    });
    expect(result.meeting_id).toBe("m_test");
    const putCall = fetchCalls.find((c) => c.init?.method === "PUT");
    expect(putCall).toBeDefined();
    expect(putCall!.url).toContain("/api/meetings/m_test/playbook");
    const body = JSON.parse(String(putCall!.init?.body));
    expect(body.free_form_markdown).toBe("# brief");
    expect(body.objective).toBe("obj");
  });
});
