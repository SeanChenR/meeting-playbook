/**
 * summary-api — slice-10 React Query options + POST helper tests.
 *
 * Per spec meeting-summary ADDED requirement scenarios for the GET 3-shape
 * response and the POST 409 busy / 404 not_found paths.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  SummaryApiError,
  fetchSummary,
  isPendingSummary,
  regenerateSummary,
  summaryQueryOptions,
} from "./summary-api";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = mock(
    async () =>
      new Response("null", {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  ) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("fetchSummary", () => {
  test("parses 200 + Summary", async () => {
    const sample = {
      id: "sm_1",
      meeting_id: "m_x",
      markdown: "## 重點討論\n",
      generated_at: "2026-05-11T01:00:00Z",
      is_stale: false,
    };
    globalThis.fetch = mock(
      async () =>
        new Response(JSON.stringify(sample), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    ) as unknown as typeof fetch;

    const out = await fetchSummary("m_x");
    expect(out).toEqual(sample);
  });

  test("parses 200 + SummaryPending", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(JSON.stringify({ status: "pending", generated_at: null }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    ) as unknown as typeof fetch;

    const out = await fetchSummary("m_x");
    expect(out).toEqual({ status: "pending", generated_at: null });
    expect(isPendingSummary(out)).toBe(true);
  });

  test("returns null on 404 summary.not_found (treated as 'no row yet')", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(JSON.stringify({ error_code: "summary.not_found", message: "no" }), {
          status: 404,
          headers: { "content-type": "application/json" },
        }),
    ) as unknown as typeof fetch;

    const out = await fetchSummary("m_x");
    expect(out).toBeNull();
  });

  test("throws SummaryApiError on 5xx", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(JSON.stringify({ error_code: "internal_error", message: "boom" }), {
          status: 500,
          headers: { "content-type": "application/json" },
        }),
    ) as unknown as typeof fetch;

    let caught: unknown = null;
    try {
      await fetchSummary("m_x");
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeInstanceOf(SummaryApiError);
    expect((caught as SummaryApiError).status).toBe(500);
  });
});

describe("regenerateSummary", () => {
  test("POST 202 resolves silently", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(JSON.stringify({ status: "pending" }), {
          status: 202,
          headers: { "content-type": "application/json" },
        }),
    ) as unknown as typeof fetch;
    await regenerateSummary("m_x"); // does not throw
  });

  test("POST 409 throws SummaryApiError summary.busy", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(
          JSON.stringify({
            error_code: "summary.busy",
            message: "already running",
          }),
          { status: 409, headers: { "content-type": "application/json" } },
        ),
    ) as unknown as typeof fetch;

    let caught: unknown = null;
    try {
      await regenerateSummary("m_x");
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeInstanceOf(SummaryApiError);
    expect((caught as SummaryApiError).status).toBe(409);
    expect((caught as SummaryApiError).errorCode).toBe("summary.busy");
  });

  test("POST 404 throws SummaryApiError meeting.not_found", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(JSON.stringify({ error_code: "meeting.not_found", message: "no" }), {
          status: 404,
          headers: { "content-type": "application/json" },
        }),
    ) as unknown as typeof fetch;

    let caught: unknown = null;
    try {
      await regenerateSummary("m_x");
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeInstanceOf(SummaryApiError);
    expect((caught as SummaryApiError).errorCode).toBe("meeting.not_found");
  });
});

describe("summaryQueryOptions", () => {
  test("queryKey is ['summary', meetingId] and forwards enabled / refetchInterval", () => {
    const opts = summaryQueryOptions("m_x", { enabled: true, refetchInterval: 1000 });
    expect(opts.queryKey).toEqual(["summary", "m_x"]);
    expect(opts.enabled).toBe(true);
    expect(opts.refetchInterval).toBe(1000);
  });
});
