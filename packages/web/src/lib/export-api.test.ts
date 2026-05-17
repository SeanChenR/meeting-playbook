/**
 * Unit tests for the export API helper (slice-22-export-bundle 4.2).
 *
 * Verifies:
 *  - exportMeeting() preflights with HEAD on `/api/meetings/{id}/export`,
 *    then on 2xx clicks a hidden `<a download>` pointing at the same URL
 *    (no Blob — the browser streams the ZIP directly to disk per Gemini
 *    PR #38 review #3).
 *  - On HEAD non-2xx the helper re-fetches via GET to read the envelope
 *    and throws a `MeetingApiError` carrying the `error_code`, and
 *    SHALL NOT click any anchor in that case.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

import { MeetingApiError } from "./meetings-api";
import { exportMeeting } from "./export-api";

const _originalFetch = globalThis.fetch;
let _originalCreateElement: typeof document.createElement;
let _clickedAnchors: HTMLAnchorElement[];

beforeEach(() => {
  _clickedAnchors = [];
  _originalCreateElement = document.createElement.bind(document);
  document.createElement = ((tag: string) => {
    const el = _originalCreateElement(tag);
    if (tag.toLowerCase() === "a") {
      const anchor = el as HTMLAnchorElement;
      const origClick = anchor.click.bind(anchor);
      anchor.click = () => {
        _clickedAnchors.push(anchor);
        try {
          origClick();
        } catch {
          // jsdom can refuse navigation — we only care about the call.
        }
      };
    }
    return el;
  }) as typeof document.createElement;
  globalThis.fetch = (() => {
    throw new Error("fetch was not stubbed for this test");
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = _originalFetch;
  document.createElement = _originalCreateElement;
});

describe("exportMeeting", () => {
  test("HEAD preflight 200 then clicks an anchor at the export URL", async () => {
    const calls: Array<{ url: string; method: string }> = [];
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? "GET" });
      // Only HEAD should happen on the happy path.
      return new Response(null, {
        status: 200,
        headers: { "content-type": "application/zip" },
      });
    }) as unknown as typeof fetch;

    await exportMeeting("m_abc", "meeting__2026-05-15.zip");

    expect(calls).toEqual([{ url: "/api/meetings/m_abc/export", method: "HEAD" }]);
    expect(_clickedAnchors.length).toBe(1);
    const anchor = _clickedAnchors[0]!;
    expect(anchor.getAttribute("download")).toBe("meeting__2026-05-15.zip");
    // href ends with the same URL (jsdom resolves it to absolute).
    expect(anchor.href.endsWith("/api/meetings/m_abc/export")).toBe(true);
  });

  test("HEAD 404 → GET to read envelope → throws MeetingApiError with errorCode", async () => {
    const calls: Array<{ url: string; method: string }> = [];
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method ?? "GET" });
      if (init?.method === "HEAD") {
        return new Response(null, { status: 404 });
      }
      return new Response(
        JSON.stringify({ error_code: "meeting.not_found", message: "Meeting not found" }),
        { status: 404, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    let thrown: unknown = null;
    try {
      await exportMeeting("m_xyz", "x.zip");
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeInstanceOf(MeetingApiError);
    expect((thrown as MeetingApiError).errorCode).toBe("meeting.not_found");
    // Both calls hit the same URL: HEAD for preflight, GET for envelope.
    expect(calls).toEqual([
      { url: "/api/meetings/m_xyz/export", method: "HEAD" },
      { url: "/api/meetings/m_xyz/export", method: "GET" },
    ]);
    // Failure path MUST NOT click any anchor.
    expect(_clickedAnchors).toEqual([]);
  });
});
