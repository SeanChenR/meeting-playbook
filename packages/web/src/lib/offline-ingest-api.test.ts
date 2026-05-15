/**
 * Unit tests for the offline-ingest progress API client (slice-14 task 5.2).
 *
 * Verifies the two API behaviours the dialog depends on:
 * - 200 → returns the parsed `OfflineIngestProgress` shape
 * - non-2xx with `{error_code, message}` envelope → throws
 *   `OfflineIngestApiError` carrying `errorCode`
 */

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

import { OfflineIngestApiError, getOfflineIngestProgress } from "./offline-ingest-api";

const _originalFetch = globalThis.fetch;

beforeEach(() => {
  // Defensive: each test installs its own fetch stub.
  globalThis.fetch = (() => {
    throw new Error("fetch was not stubbed for this test");
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = _originalFetch;
});

describe("getOfflineIngestProgress", () => {
  test("returns the parsed progress envelope on 200", async () => {
    globalThis.fetch = (async (_url: string) => {
      return new Response(
        JSON.stringify({
          state: "asr_running",
          chunks_processed: 4,
          chunks_total: 10,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    const result = await getOfflineIngestProgress("m_x");
    expect(result.state).toBe("asr_running");
    expect(result.chunks_processed).toBe(4);
    expect(result.chunks_total).toBe(10);
  });

  test("throws OfflineIngestApiError carrying errorCode on 4xx envelope", async () => {
    globalThis.fetch = (async (_url: string) => {
      return new Response(
        JSON.stringify({
          detail: {
            error_code: "offline_ingest.not_found",
            message: "Meeting 'm_missing' not found.",
          },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      );
    }) as unknown as typeof fetch;

    let thrown: unknown = null;
    try {
      await getOfflineIngestProgress("m_missing");
    } catch (err) {
      thrown = err;
    }
    expect(thrown).toBeInstanceOf(OfflineIngestApiError);
    const apiError = thrown as OfflineIngestApiError;
    expect(apiError.errorCode).toBe("offline_ingest.not_found");
    expect(apiError.statusCode).toBe(404);
  });
});
