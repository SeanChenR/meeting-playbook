/**
 * Unit tests for the export API helper (slice-22-export-bundle 4.2).
 *
 * Verifies:
 *  - exportMeeting() issues a GET to `/api/meetings/{id}/export`.
 *  - On HTTP 200 it reads the Blob, creates an object URL, programmatically
 *    clicks a hidden `<a download>`, and revokes the object URL afterwards.
 *  - On 4xx envelope it throws a `MeetingApiError` carrying `errorCode`.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

import { MeetingApiError } from "./meetings-api";
import { exportMeeting } from "./export-api";

const _originalFetch = globalThis.fetch;

interface _MockUrlState {
  created: string[];
  revoked: string[];
}

let _urlState: _MockUrlState;
let _originalCreateObjectURL: typeof URL.createObjectURL;
let _originalRevokeObjectURL: typeof URL.revokeObjectURL;
let _clickedAnchors: HTMLAnchorElement[];
let _originalCreateElement: typeof document.createElement;

beforeEach(() => {
  _urlState = { created: [], revoked: [] };
  _originalCreateObjectURL = URL.createObjectURL;
  _originalRevokeObjectURL = URL.revokeObjectURL;
  _originalCreateElement = document.createElement.bind(document);
  URL.createObjectURL = ((_blob: Blob) => {
    const url = `blob:mock-${_urlState.created.length}`;
    _urlState.created.push(url);
    return url;
  }) as typeof URL.createObjectURL;
  URL.revokeObjectURL = ((url: string) => {
    _urlState.revoked.push(url);
  }) as typeof URL.revokeObjectURL;
  _clickedAnchors = [];
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
  URL.createObjectURL = _originalCreateObjectURL;
  URL.revokeObjectURL = _originalRevokeObjectURL;
  document.createElement = _originalCreateElement;
});

describe("exportMeeting", () => {
  test("issues GET to the export endpoint and triggers a download anchor", async () => {
    let capturedUrl = "";
    let capturedInit: RequestInit | undefined;
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      capturedUrl = url;
      capturedInit = init;
      const body = new Blob([new Uint8Array([1, 2, 3])], { type: "application/zip" });
      return new Response(body, {
        status: 200,
        headers: {
          "content-type": "application/zip",
          "content-disposition":
            "attachment; filename=\"meeting__2026-05-15.zip\"; filename*=UTF-8''meeting__2026-05-15.zip",
        },
      });
    }) as unknown as typeof fetch;

    await exportMeeting("m_abc", "meeting__2026-05-15.zip");

    expect(capturedUrl).toBe("/api/meetings/m_abc/export");
    expect(capturedInit?.method ?? "GET").toBe("GET");
    expect(_urlState.created.length).toBe(1);
    expect(_clickedAnchors.length).toBe(1);
    expect(_clickedAnchors[0]?.getAttribute("download")).toBe("meeting__2026-05-15.zip");
    expect(_urlState.revoked).toEqual(_urlState.created);
  });

  test("throws MeetingApiError carrying errorCode on 404", async () => {
    globalThis.fetch = (async () => {
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
    // Failure path MUST NOT create or leak an object URL.
    expect(_urlState.created).toEqual([]);
    expect(_clickedAnchors).toEqual([]);
  });
});
