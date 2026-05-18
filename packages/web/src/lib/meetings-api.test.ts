/**
 * Unit tests for the meetings API client — slice-15 task 3.2 adds
 * `patchMeeting` coverage to the previously untested helpers.
 *
 * - `patchMeeting_sends_PATCH`: verifies method / path / JSON body shape
 *   so the frontend cannot accidentally regress to POST.
 * - `patchMeeting_throws_with_error_code_on_422`: confirms the project
 *   `{error_code, message}` envelope is decoded into a thrown Error
 *   whose `errorCode` property the dialog reads.
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

import { mixedAudioUrl, patchMeeting, recordingAudioUrl } from "./meetings-api";

const _originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = (() => {
    throw new Error("fetch was not stubbed for this test");
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = _originalFetch;
});

describe("patchMeeting", () => {
  test("sends PATCH with JSON body to the right path", async () => {
    let capturedUrl = "";
    let capturedInit: RequestInit | undefined;
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      capturedUrl = url;
      capturedInit = init;
      return new Response(
        JSON.stringify({
          id: "m_abc",
          user_id: "u",
          title: "after",
          counterparty_display_name: "C",
          me_display_name: "M",
          status: "scheduled",
          asr_provider: "qwen3",
          calendar_event_id: null,
          created_at: "2026-05-15T00:00:00Z",
          started_at: null,
          ended_at: null,
          scheduled_start_at: "2026-06-15T14:00:00Z",
          scheduled_end_at: null,
          recordings_available: false,
          rerun_asr_pending: false,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    const result = await patchMeeting("m_abc", { title: "after" });

    expect(capturedUrl).toBe("/api/meetings/m_abc");
    expect(capturedInit?.method).toBe("PATCH");
    expect(capturedInit?.headers).toMatchObject({
      "content-type": "application/json",
    });
    expect(capturedInit?.body).toBe(JSON.stringify({ title: "after" }));
    expect(result.title).toBe("after");
  });

  test("throws with errorCode on 422 envelope", async () => {
    globalThis.fetch = (async () => {
      return new Response(
        JSON.stringify({
          error_code: "meeting.invalid_time_range",
          message: "End time must be at or after the start time",
        }),
        { status: 422, headers: { "content-type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    let thrown: unknown = null;
    try {
      await patchMeeting("m_abc", { scheduled_end_at: "2025-01-01T00:00:00Z" });
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeTruthy();
    const err = thrown as { errorCode?: string };
    expect(err.errorCode).toBe("meeting.invalid_time_range");
  });
});

// ─── slice-25 task 3.1 — audio URL helpers ────────────────────────────

describe("mixedAudioUrl + recordingAudioUrl", () => {
  test("mixedAudioUrl returns base url without query when no params", () => {
    expect(mixedAudioUrl("m_abc")).toBe("/api/meetings/m_abc/recordings/mixed/audio");
  });

  test("mixedAudioUrl encodes meeting id and includes start + end", () => {
    expect(mixedAudioUrl("m abc/with weird chars", { start: 1.5, end: 12.75 })).toBe(
      "/api/meetings/m%20abc%2Fwith%20weird%20chars/recordings/mixed/audio?start=1.5&end=12.75",
    );
  });

  test("recordingAudioUrl returns the per-recording endpoint", () => {
    expect(recordingAudioUrl("m_x", "r_y")).toBe("/api/meetings/m_x/recordings/r_y/audio");
  });

  test("recordingAudioUrl appends start + end query params", () => {
    expect(recordingAudioUrl("m_x", "r_y", { start: 0, end: 60 })).toBe(
      "/api/meetings/m_x/recordings/r_y/audio?start=0&end=60",
    );
  });
});
