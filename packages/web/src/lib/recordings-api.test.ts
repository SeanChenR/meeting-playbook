/**
 * recordings-api — query options + mutation contract tests (P4 task 2.1).
 *
 * Asserts:
 *   - queryKey shape (`["recordings", "list", since|null, until|null, search|null, page]`)
 *   - GET URL composition with filter / pagination params
 *   - Happy-path JSON decoding into `RecordingListResponse`
 *   - Backend `{error_code, message}` envelope is surfaced via `RecordingApiError`
 *     for 410 / 413 / 422 / 403 batch-download failure modes (POST /preflight)
 *   - Happy-path batch download routes through POST /preflight + anchor-click
 *     GET so the browser streams to disk (gemini PR #48 HIGH + MEDIUM)
 *   - `recordingAudioUrl` mirrors the existing per-meeting audio endpoint path
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import {
  batchDownloadRecordings,
  listRecordings,
  recordingAudioUrl,
  RecordingApiError,
  recordingsListQueryOptions,
} from "./recordings-api";

const originalFetch = globalThis.fetch;

let fetchCalls: Array<{ url: string; init?: RequestInit }> = [];

interface MockSpec {
  url: string | ((u: string) => boolean);
  status?: number;
  body?: unknown;
  bodyText?: string;
  headers?: Record<string, string>;
}

function installFetch(specs: MockSpec[]): void {
  globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    fetchCalls.push({ url, init });
    for (const spec of specs) {
      const matches = typeof spec.url === "string" ? url === spec.url : spec.url(url);
      if (matches) {
        const headers: Record<string, string> = spec.headers ?? {
          "content-type": "application/json",
        };
        const payload = spec.body !== undefined ? JSON.stringify(spec.body) : (spec.bodyText ?? "");
        return new Response(payload, { status: spec.status ?? 200, headers });
      }
    }
    return new Response("unexpected url: " + url, { status: 599 });
  }) as unknown as typeof fetch;
}

beforeEach(() => {
  fetchCalls = [];
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("recordingsListQueryOptions", () => {
  test("queryKey is stable and parameter-derived", () => {
    const opts = recordingsListQueryOptions({
      since: "2026-05-01",
      until: "2026-05-10",
      search: "acme",
      page: 2,
    });
    expect(opts.queryKey).toEqual(["recordings", "list", "2026-05-01", "2026-05-10", "acme", 2]);
  });

  test("queryKey defaults missing fields to null / 1", () => {
    const opts = recordingsListQueryOptions({});
    expect(opts.queryKey).toEqual(["recordings", "list", null, null, null, 1]);
  });
});

describe("listRecordings", () => {
  test("composes query string from non-empty params and decodes JSON envelope", async () => {
    installFetch([
      {
        url: (u) => u.startsWith("/api/recordings"),
        body: {
          recordings: [
            {
              id: "r_1",
              meeting_id: "m_1",
              meeting_title: "Acme call",
              counterparty_label: "Acme",
              captured_at: "2026-05-08T10:00:00Z",
              duration_ms: 1000,
              byte_size: 32_044,
              stream: "me",
            },
          ],
          total: 1,
          page: 2,
          page_size: 25,
        },
      },
    ]);

    const out = await listRecordings({
      since: "2026-05-01",
      until: "2026-05-10",
      search: "Acme",
      page: 2,
    });

    expect(out.total).toBe(1);
    expect(out.recordings[0]?.id).toBe("r_1");
    expect(fetchCalls[0]?.url).toContain("/api/recordings?");
    expect(fetchCalls[0]?.url).toContain("since=2026-05-01");
    expect(fetchCalls[0]?.url).toContain("until=2026-05-10");
    expect(fetchCalls[0]?.url).toContain("search=Acme");
    expect(fetchCalls[0]?.url).toContain("page=2");
  });

  test("omits query string when no params supplied", async () => {
    installFetch([
      {
        url: "/api/recordings",
        body: { recordings: [], total: 0, page: 1, page_size: 25 },
      },
    ]);

    await listRecordings({});
    expect(fetchCalls[0]?.url).toBe("/api/recordings");
  });

  test("surfaces backend error_code via RecordingApiError on non-2xx", async () => {
    installFetch([
      {
        url: (u) => u.startsWith("/api/recordings"),
        status: 401,
        body: { error_code: "auth.gateway_bypass", message: "missing" },
      },
    ]);

    try {
      await listRecordings({});
      throw new Error("expected listRecordings to throw");
    } catch (e) {
      expect(e).toBeInstanceOf(RecordingApiError);
      expect((e as RecordingApiError).status).toBe(401);
      expect((e as RecordingApiError).errorCode).toBe("auth.gateway_bypass");
    }
  });
});

describe("recordingAudioUrl", () => {
  test("matches the existing per-meeting audio endpoint path", () => {
    expect(recordingAudioUrl("m_a", "r_b")).toBe("/api/meetings/m_a/recordings/r_b/audio");
  });
});

describe("batchDownloadRecordings preflight error mapping", () => {
  // The frontend POSTs to /preflight first so 4xx envelopes surface as JS
  // exceptions before the browser ever navigates to the streaming GET URL.
  test("410 recording.retention_expired surfaces in RecordingApiError", async () => {
    installFetch([
      {
        url: "/api/recordings/batch-download/preflight",
        status: 410,
        body: { error_code: "recording.retention_expired", message: "expired" },
      },
    ]);
    try {
      await batchDownloadRecordings({ recording_ids: ["r_x"] });
      throw new Error("expected throw");
    } catch (e) {
      expect((e as RecordingApiError).status).toBe(410);
      expect((e as RecordingApiError).errorCode).toBe("recording.retention_expired");
    }
  });

  test("413 recording.batch_oversize surfaces in RecordingApiError", async () => {
    installFetch([
      {
        url: "/api/recordings/batch-download/preflight",
        status: 413,
        body: { error_code: "recording.batch_oversize", message: "too big" },
      },
    ]);
    try {
      await batchDownloadRecordings({ recording_ids: ["r_x"] });
      throw new Error("expected throw");
    } catch (e) {
      expect((e as RecordingApiError).errorCode).toBe("recording.batch_oversize");
    }
  });

  test("422 recording.invalid_stream surfaces in RecordingApiError", async () => {
    installFetch([
      {
        url: "/api/recordings/batch-download/preflight",
        status: 422,
        body: { error_code: "recording.invalid_stream", message: "bad stream" },
      },
    ]);
    try {
      await batchDownloadRecordings({ recording_ids: ["r_x"] });
      throw new Error("expected throw");
    } catch (e) {
      expect((e as RecordingApiError).errorCode).toBe("recording.invalid_stream");
    }
  });

  test("403 recording.forbidden surfaces in RecordingApiError", async () => {
    installFetch([
      {
        url: "/api/recordings/batch-download/preflight",
        status: 403,
        body: { error_code: "recording.forbidden", message: "nope" },
      },
    ]);
    try {
      await batchDownloadRecordings({ recording_ids: ["r_x"] });
      throw new Error("expected throw");
    } catch (e) {
      expect((e as RecordingApiError).errorCode).toBe("recording.forbidden");
    }
  });

  test("happy path posts to /preflight then anchor-clicks the streaming GET URL", async () => {
    installFetch([
      {
        url: "/api/recordings/batch-download/preflight",
        status: 200,
        body: { ok: true, archive_name: "recordings-20260518-1601.zip", entry_count: 2 },
      },
    ]);

    // Capture the synthesized anchor so we can assert on its href + click.
    const originalCreateElement = document.createElement.bind(document);
    const created: HTMLAnchorElement[] = [];
    let clickCount = 0;
    document.createElement = ((tag: string) => {
      if (tag === "a") {
        const fake = originalCreateElement("a") as HTMLAnchorElement;
        const realClick = fake.click.bind(fake);
        fake.click = () => {
          clickCount += 1;
          realClick();
        };
        created.push(fake);
        return fake;
      }
      return originalCreateElement(tag);
    }) as typeof document.createElement;

    await batchDownloadRecordings({ recording_ids: ["r_a", "r_b"] });

    expect(fetchCalls[0]?.url).toBe("/api/recordings/batch-download/preflight");
    expect(fetchCalls[0]?.init?.method).toBe("POST");
    expect(clickCount).toBe(1);
    expect(created[0]?.getAttribute("href")).toBe("/api/recordings/batch-download?ids=r_a%2Cr_b");

    document.createElement = originalCreateElement;
  });
});
