/**
 * playbook-api — slice-23 tests for discard_previous / restore_previous client.
 *
 * Per slice-23 task 3.2 verification:
 * - 200 + Playbook body → parsed Playbook returned
 * - 404 + envelope → PlaybookApiError thrown carrying error_code
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { PlaybookApiError, discardPreviousPlaybook, restorePreviousPlaybook } from "./playbook-api";

const originalFetch = globalThis.fetch;

const SAMPLE = (
  overrides: Partial<{
    previous_free_form_markdown: string | null;
    has_previous_version: boolean;
    free_form_markdown: string;
  }> = {},
) => ({
  id: "pb_test",
  meeting_id: "m_test",
  free_form_markdown: "v2",
  objective: "",
  counterparty_profile: "",
  anticipated_topics: "",
  anticipated_objections: "",
  talking_points: "",
  red_lines: "",
  created_at: "2026-05-17T10:00:00Z",
  updated_at: "2026-05-17T10:00:00Z",
  is_stale: false,
  previous_free_form_markdown: null,
  previous_updated_at: null,
  has_previous_version: false,
  ...overrides,
});

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

describe("discardPreviousPlaybook", () => {
  test("POSTs to /playbook/discard_previous and parses 200 response", async () => {
    let calledUrl = "";
    let calledMethod = "";
    const body = SAMPLE({ has_previous_version: false, previous_free_form_markdown: null });
    globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
      calledUrl = typeof input === "string" ? input : input.toString();
      calledMethod = init?.method ?? "GET";
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const out = await discardPreviousPlaybook("m_test");
    expect(out).toEqual(body);
    expect(calledUrl).toBe("/api/meetings/m_test/playbook/discard_previous");
    expect(calledMethod).toBe("POST");
  });

  test("throws PlaybookApiError on 404 no_previous_version", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(
          JSON.stringify({
            error_code: "playbook.no_previous_version",
            message: "no previous",
          }),
          {
            status: 404,
            headers: { "content-type": "application/json" },
          },
        ),
    ) as unknown as typeof fetch;

    let caught: unknown = null;
    try {
      await discardPreviousPlaybook("m_test");
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(PlaybookApiError);
    expect((caught as PlaybookApiError).status).toBe(404);
    expect((caught as PlaybookApiError).errorCode).toBe("playbook.no_previous_version");
  });
});

describe("restorePreviousPlaybook", () => {
  test("POSTs to /playbook/restore_previous and parses 200 response", async () => {
    let calledUrl = "";
    let calledMethod = "";
    const body = SAMPLE({
      free_form_markdown: "v1",
      previous_free_form_markdown: null,
      has_previous_version: false,
    });
    globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
      calledUrl = typeof input === "string" ? input : input.toString();
      calledMethod = init?.method ?? "GET";
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const out = await restorePreviousPlaybook("m_test");
    expect(out.free_form_markdown).toBe("v1");
    expect(calledUrl).toBe("/api/meetings/m_test/playbook/restore_previous");
    expect(calledMethod).toBe("POST");
  });

  test("throws PlaybookApiError on 404 no_previous_version", async () => {
    globalThis.fetch = mock(
      async () =>
        new Response(
          JSON.stringify({
            error_code: "playbook.no_previous_version",
            message: "no previous",
          }),
          {
            status: 404,
            headers: { "content-type": "application/json" },
          },
        ),
    ) as unknown as typeof fetch;

    let caught: unknown = null;
    try {
      await restorePreviousPlaybook("m_test");
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeInstanceOf(PlaybookApiError);
    expect((caught as PlaybookApiError).errorCode).toBe("playbook.no_previous_version");
  });
});
