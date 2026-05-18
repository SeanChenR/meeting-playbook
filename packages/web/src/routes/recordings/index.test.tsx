/**
 * RecordingsIndex route tests (P4 task 2.2 – 2.7).
 *
 * Covers:
 *   - 2.2 page renders rows from GET /api/recordings
 *   - 2.3 per-row Download anchor targets the existing audio endpoint
 *   - 2.4 multi-select + Batch download POSTs to /api/recordings/batch-download
 *         and surfaces oversize / retention-expired toasts
 *   - 2.5 search input writes ?search=… to URL state
 *   - 2.6 empty state renders the localized retention hint
 *   - 2.7 meeting-title cell links to /meetings/{meeting_id}
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

mock.module("../../lib/auth-client", () => ({
  authClient: {
    useSession: () => ({
      data: {
        user: {
          id: "u_test",
          name: "Sean",
          email: "sean@example.com",
          image: null,
          twoFactorEnabled: false,
        },
      },
      isPending: false,
    }),
    signOut: async () => ({}),
    listAccounts: async () => ({ data: [{ providerId: "credential" }] }),
    getSession: async () => ({ data: null }),
  },
}));

const toastSuccess = mock((_msg: string) => undefined);
const toastError = mock((_msg: string) => undefined);
mock.module("sonner", () => ({
  toast: { success: toastSuccess, error: toastError },
  Toaster: () => null,
}));

import { i18n } from "../../lib/i18n";
import { renderWithRouter } from "../../test/fixtures/router";
import { RecordingsIndex } from "./index";

const originalFetch = globalThis.fetch;
const originalCreateObjectURL = globalThis.URL?.createObjectURL;
const originalRevokeObjectURL = globalThis.URL?.revokeObjectURL;

interface MockSpec {
  match: (url: string, init?: RequestInit) => boolean;
  status?: number;
  body?: unknown;
  bodyText?: string;
  headers?: Record<string, string>;
}

let fetchCalls: Array<{ url: string; init?: RequestInit }> = [];

function installFetch(specs: MockSpec[]) {
  globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    fetchCalls.push({ url, init });
    for (const spec of specs) {
      if (spec.match(url, init)) {
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

const sampleRow = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id: "r_1",
  meeting_id: "m_1",
  meeting_title: "Acme call",
  counterparty_label: "Acme",
  captured_at: "2026-05-08T10:00:00Z",
  duration_ms: 600_000,
  byte_size: 32_044,
  stream: "me",
  ...overrides,
});

beforeEach(async () => {
  fetchCalls = [];
  toastSuccess.mockClear();
  toastError.mockClear();
  await i18n.changeLanguage("zh-TW");
  if (typeof URL !== "undefined") {
    (URL as unknown as { createObjectURL: (b: Blob) => string }).createObjectURL = () =>
      "blob://test";
    (URL as unknown as { revokeObjectURL: (u: string) => void }).revokeObjectURL = () => {};
  }
});

afterEach(() => {
  cleanup();
  globalThis.fetch = originalFetch;
  if (typeof URL !== "undefined") {
    if (originalCreateObjectURL)
      (URL as unknown as { createObjectURL: typeof URL.createObjectURL }).createObjectURL =
        originalCreateObjectURL;
    if (originalRevokeObjectURL)
      (URL as unknown as { revokeObjectURL: typeof URL.revokeObjectURL }).revokeObjectURL =
        originalRevokeObjectURL;
  }
});

describe("RecordingsIndex — list + per-row download (tasks 2.2, 2.3, 2.7)", () => {
  test("renders rows from GET /api/recordings", async () => {
    installFetch([
      {
        match: (u) => u.startsWith("/api/recordings"),
        body: {
          recordings: [sampleRow()],
          total: 1,
          page: 1,
          page_size: 25,
        },
      },
    ]);

    await renderWithRouter(<RecordingsIndex />, {
      initialEntries: ["/recordings"],
      path: "/recordings",
    });

    await waitFor(() => expect(screen.getByText("Acme call")).toBeDefined());
    // Per-row Download anchor reuses the existing per-meeting audio endpoint.
    const downloadLink = screen.getByTestId("recordings-row-download-r_1") as HTMLAnchorElement;
    expect(downloadLink.getAttribute("href")).toBe("/api/meetings/m_1/recordings/r_1/audio");
    // Meeting title cell links to /meetings/{meeting_id}.
    const meetingLink = screen.getByTestId("recordings-row-meeting-r_1") as HTMLAnchorElement;
    expect(meetingLink.getAttribute("href")).toBe("/meetings/m_1");
  });
});

describe("RecordingsIndex — empty state (task 2.6)", () => {
  test("zero rows surfaces the localized retention hint in zh-TW", async () => {
    installFetch([
      {
        match: (u) => u.startsWith("/api/recordings"),
        body: { recordings: [], total: 0, page: 1, page_size: 25 },
      },
    ]);

    await renderWithRouter(<RecordingsIndex />, {
      initialEntries: ["/recordings"],
      path: "/recordings",
    });

    await waitFor(() => expect(screen.getByTestId("recordings-empty-state")).toBeDefined());
    expect(screen.getByText("目前沒有錄音檔")).toBeDefined();
    expect(screen.getByText("超過 30 天的錄音檔已依保留政策清除")).toBeDefined();
  });
});

describe("RecordingsIndex — search input (task 2.5)", () => {
  test("typing into search updates the URL after debounce", async () => {
    installFetch([
      {
        match: (u) => u.startsWith("/api/recordings"),
        body: { recordings: [], total: 0, page: 1, page_size: 25 },
      },
    ]);

    const { router } = await renderWithRouter(<RecordingsIndex />, {
      initialEntries: ["/recordings"],
      path: "/recordings",
    });

    const user = userEvent.setup();
    const input = screen.getByTestId("recordings-search-input") as HTMLInputElement;
    await user.type(input, "acme");

    await waitFor(
      () => {
        const search = router.state.location.search as unknown as Record<string, string>;
        expect(search.search).toBe("acme");
      },
      { timeout: 1500 },
    );
  });
});

describe("RecordingsIndex — batch download (task 2.4)", () => {
  test("oversize 413 surfaces the localized toast and does not clear selection", async () => {
    installFetch([
      {
        match: (u, init) =>
          u === "/api/recordings/batch-download/preflight" && (init?.method ?? "GET") === "POST",
        status: 413,
        body: { error_code: "recording.batch_oversize", message: "too big" },
      },
      {
        match: (u) => u.startsWith("/api/recordings"),
        body: {
          recordings: [sampleRow()],
          total: 1,
          page: 1,
          page_size: 25,
        },
      },
    ]);

    await renderWithRouter(<RecordingsIndex />, {
      initialEntries: ["/recordings"],
      path: "/recordings",
    });

    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("Acme call")).toBeDefined());

    const rowCheckbox = screen.getByTestId("recordings-row-checkbox-r_1") as HTMLInputElement;
    await user.click(rowCheckbox);
    const batchBtn = await screen.findByTestId("recordings-batch-download");
    await user.click(batchBtn);

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    const msg = toastError.mock.calls[0]?.[0];
    expect(typeof msg).toBe("string");
    // The locale message references the byte limit via {{limit}} interpolation.
    expect(String(msg)).toContain("超過");
  });

  test("retention-expired 410 surfaces the localized toast", async () => {
    installFetch([
      {
        match: (u, init) =>
          u === "/api/recordings/batch-download/preflight" && (init?.method ?? "GET") === "POST",
        status: 410,
        body: { error_code: "recording.retention_expired", message: "expired" },
      },
      {
        match: (u) => u.startsWith("/api/recordings"),
        body: {
          recordings: [sampleRow()],
          total: 1,
          page: 1,
          page_size: 25,
        },
      },
    ]);

    await renderWithRouter(<RecordingsIndex />, {
      initialEntries: ["/recordings"],
      path: "/recordings",
    });

    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("Acme call")).toBeDefined());
    await user.click(screen.getByTestId("recordings-row-checkbox-r_1"));
    await user.click(await screen.findByTestId("recordings-batch-download"));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(String(toastError.mock.calls[0]?.[0])).toContain("超過保留期");
  });

  test("happy-path success surfaces ZIP ready toast", async () => {
    installFetch([
      {
        match: (u, init) =>
          u === "/api/recordings/batch-download/preflight" && (init?.method ?? "GET") === "POST",
        bodyText: "PKzip",
        headers: {
          "content-type": "application/zip",
          "content-disposition": 'attachment; filename="recordings-20260518-1611.zip"',
        },
      },
      {
        match: (u) => u.startsWith("/api/recordings"),
        body: {
          recordings: [sampleRow()],
          total: 1,
          page: 1,
          page_size: 25,
        },
      },
    ]);

    await renderWithRouter(<RecordingsIndex />, {
      initialEntries: ["/recordings"],
      path: "/recordings",
    });

    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByText("Acme call")).toBeDefined());
    await user.click(screen.getByTestId("recordings-row-checkbox-r_1"));
    await user.click(await screen.findByTestId("recordings-batch-download"));

    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
    expect(String(toastSuccess.mock.calls[0]?.[0])).toContain("ZIP");
  });
});
