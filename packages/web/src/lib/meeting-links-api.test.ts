/**
 * meeting-links-api — slice-21 task 4.1.
 *
 * Three behaviour-pinning cases per the task contract:
 *   (a) listLinks success → typed array
 *   (b) createLink 409 → throws MeetingLinkApiError with errorCode set
 *   (c) deleteLink 204 → resolves without throwing
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

import { createLink, deleteLink, listLinks, MeetingLinkApiError } from "./meeting-links-api";

const _originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = (() => {
    throw new Error("fetch was not stubbed for this test");
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = _originalFetch;
});

describe("listLinks", () => {
  test("returns a typed array on 200", async () => {
    let capturedUrl = "";
    globalThis.fetch = (async (url: string) => {
      capturedUrl = url;
      return new Response(
        JSON.stringify({
          links: [
            {
              link_id: "11111111-1111-1111-1111-111111111111",
              other_meeting_id: "m_b",
              other_meeting_title: "B",
              other_meeting_scheduled_start_at: "2026-06-15T14:00:00Z",
              link_type: "related",
              created_at: "2026-05-14T00:00:00Z",
            },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    const result = await listLinks("m_a");

    expect(capturedUrl).toBe("/api/meetings/m_a/links");
    expect(result).toHaveLength(1);
    expect(result[0]?.other_meeting_id).toBe("m_b");
    expect(result[0]?.link_type).toBe("related");
  });
});

describe("createLink", () => {
  test("throws MeetingLinkApiError with meeting_link.duplicate code on 409", async () => {
    globalThis.fetch = (async () => {
      return new Response(
        JSON.stringify({
          error_code: "meeting_link.duplicate",
          message: "These meetings are already linked",
        }),
        { status: 409, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    let thrown: unknown = null;
    try {
      await createLink("m_a", "m_b");
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeInstanceOf(MeetingLinkApiError);
    const err = thrown as MeetingLinkApiError;
    expect(err.errorCode).toBe("meeting_link.duplicate");
    expect(err.status).toBe(409);
  });

  test("returns {link_id} on 201", async () => {
    let capturedBody: string | undefined;
    let capturedMethod: string | undefined;
    globalThis.fetch = (async (_url: string, init?: RequestInit) => {
      capturedMethod = init?.method;
      capturedBody = init?.body as string;
      return new Response(JSON.stringify({ link_id: "22222222-2222-2222-2222-222222222222" }), {
        status: 201,
        headers: { "content-type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const result = await createLink("m_a", "m_b");

    expect(capturedMethod).toBe("POST");
    expect(capturedBody).toBe(JSON.stringify({ to_meeting_id: "m_b" }));
    expect(result.link_id).toBe("22222222-2222-2222-2222-222222222222");
  });
});

describe("deleteLink", () => {
  test("resolves without throwing on 204", async () => {
    globalThis.fetch = (async () => {
      return new Response(null, { status: 204 });
    }) as unknown as typeof fetch;

    let thrown: unknown = null;
    try {
      await deleteLink("m_a", "22222222-2222-2222-2222-222222222222");
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeNull();
  });
});
