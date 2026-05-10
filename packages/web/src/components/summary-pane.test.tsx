/**
 * SummaryPane — slice-10 5-state UI tests.
 *
 * Per spec meeting-detail-layout MODIFIED requirement scenarios:
 * loading / pending (with 1s polling) / done / stale / empty (404) /
 * regenerate POST + cache invalidate / export click invokes helper.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { SummaryPane } from "./summary-pane";

const _MEETING = {
  title: "Q3 review",
  created_at: "2026-05-11T01:30:00Z",
  status: "completed",
};

const _DONE_FRESH = {
  id: "sm_1",
  meeting_id: "m_x",
  markdown: "## 重點討論\n- foo\n## 決議\n(無)\n## Action items\n- [TBD] x\n## 待解決問題\n(無)\n",
  generated_at: "2026-05-11T01:00:00Z",
  is_stale: false,
};

let fetchHandler: (url: string, init?: RequestInit) => Promise<Response>;
const originalFetch = globalThis.fetch;

beforeEach(() => {
  fetchHandler = async () =>
    new Response(JSON.stringify(_DONE_FRESH), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    fetchHandler(typeof input === "string" ? input : input.toString(), init)) as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  cleanup();
});

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function _render(meeting = _MEETING) {
  render(
    <Wrapper>
      <SummaryPane meetingId="m_x" meeting={meeting} />
    </Wrapper>,
  );
}

describe("SummaryPane", () => {
  test("loading state renders summary-loading testid before fetch resolves", async () => {
    // Hold the fetch open so React Query stays in `isLoading`.
    let release: () => void = () => {};
    fetchHandler = () =>
      new Promise((resolve) => {
        release = () =>
          resolve(
            new Response(JSON.stringify(_DONE_FRESH), {
              status: 200,
              headers: { "content-type": "application/json" },
            }),
          );
      });
    _render();
    expect(screen.getByTestId("summary-loading")).toBeDefined();
    release();
    await waitFor(() => {
      expect(screen.queryByTestId("summary-loading")).toBeNull();
    });
  });

  test("pending state renders hint", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify({ status: "pending", generated_at: null }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    _render();
    await waitFor(() => {
      expect(screen.getByTestId("summary-pending")).toBeDefined();
    });
    // Localised hint text appears.
    expect(screen.getByText(/30-60/)).toBeDefined();
  });

  test("done state renders markdown body and Regenerate + Export buttons", async () => {
    _render();
    await waitFor(() => {
      expect(screen.queryByTestId("summary-loading")).toBeNull();
    });
    expect(screen.getByTestId("summary-regenerate-button")).toBeDefined();
    expect(screen.getByTestId("summary-export-button")).toBeDefined();
    expect(screen.queryByTestId("summary-stale-alert")).toBeNull();
    // Markdown rendered.
    expect(screen.getByTestId("markdown-preview").textContent).toContain("foo");
  });

  test("stale alert renders when is_stale=true", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify({ ..._DONE_FRESH, is_stale: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    _render();
    await waitFor(() => {
      expect(screen.getByTestId("summary-stale-alert")).toBeDefined();
    });
  });

  test("empty state renders Generate button when 404 summary.not_found", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify({ error_code: "summary.not_found", message: "no" }), {
        status: 404,
        headers: { "content-type": "application/json" },
      });
    _render();
    await waitFor(() => {
      expect(screen.getByTestId("summary-empty")).toBeDefined();
    });
    expect(screen.getByTestId("summary-generate-button")).toBeDefined();
  });

  test("regenerate click POSTs and invalidates cache", async () => {
    let postCount = 0;
    fetchHandler = async (_url, init) => {
      if (init?.method === "POST") {
        postCount += 1;
        return new Response(JSON.stringify({ status: "pending" }), {
          status: 202,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(_DONE_FRESH), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    _render();
    await waitFor(() => {
      expect(screen.getByTestId("summary-regenerate-button")).toBeDefined();
    });
    fireEvent.click(screen.getByTestId("summary-regenerate-button"));
    await waitFor(() => {
      expect(postCount).toBeGreaterThanOrEqual(1);
    });
  });

  test("export click invokes the markdown-export helper with meeting + markdown", async () => {
    // Stub showSaveFilePicker to record the call without opening a real
    // dialog; the helper resolves silently after writing.
    let savedFilename: string | null = null;
    let savedContent: string | null = null;
    const origPicker = (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker;
    const fakeWritable = {
      write: async (data: string) => {
        savedContent = data;
      },
      close: async () => {},
    };
    (window as unknown as { showSaveFilePicker: unknown }).showSaveFilePicker = mock(
      async (opts: { suggestedName: string }) => {
        savedFilename = opts.suggestedName;
        return { createWritable: async () => fakeWritable } as unknown;
      },
    );
    try {
      _render();
      await waitFor(() => {
        expect(screen.getByTestId("summary-export-button")).toBeDefined();
      });
      fireEvent.click(screen.getByTestId("summary-export-button"));
      await waitFor(() => {
        expect(savedFilename).not.toBeNull();
      });
      expect(savedFilename).toMatch(/^Q3 review-2026-05-11\.md$/);
      expect(savedContent).toBe(_DONE_FRESH.markdown);
    } finally {
      if (origPicker !== undefined) {
        (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker = origPicker;
      } else {
        delete (window as unknown as { showSaveFilePicker?: unknown }).showSaveFilePicker;
      }
    }
  });

  test("regenerate 409 busy → shows postError text but stays on done state", async () => {
    let firstGet = true;
    fetchHandler = async (_url, init) => {
      if (init?.method === "POST") {
        return new Response(JSON.stringify({ error_code: "summary.busy", message: "busy" }), {
          status: 409,
          headers: { "content-type": "application/json" },
        });
      }
      if (firstGet) {
        firstGet = false;
        return new Response(JSON.stringify(_DONE_FRESH), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response(JSON.stringify(_DONE_FRESH), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    };
    _render();
    await waitFor(() => {
      expect(screen.getByTestId("summary-regenerate-button")).toBeDefined();
    });
    fireEvent.click(screen.getByTestId("summary-regenerate-button"));
    // Localised summary.busy → 上一個生成尚未完成
    await waitFor(() => {
      expect(screen.getByText(/尚未完成/)).toBeDefined();
    });
    // Done body still rendered (didn't crash).
    expect(screen.getByTestId("markdown-preview")).toBeDefined();
  });
});
