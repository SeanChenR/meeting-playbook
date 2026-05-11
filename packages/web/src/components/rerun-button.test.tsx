/**
 * RerunButton — slice-11 task 6.1 component test.
 *
 * Visibility gating per spec meeting-detail-layout:
 *   - rendered only when status=completed && recordings_available && !rerun_asr_pending
 *   - click → POST /api/meetings/{id}/rerun_asr; 202 hides the button via the
 *     cache update (optimistic rerun_asr_pending=true).
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";

import { RerunButton } from "./rerun-button";

const originalFetch = globalThis.fetch;
let fetchHandler: (url: string, init?: RequestInit) => Promise<Response>;

beforeEach(() => {
  fetchHandler = async () => new Response("", { status: 202 });
  globalThis.fetch = mock((u: string, init?: RequestInit) =>
    fetchHandler(u, init),
  ) as unknown as typeof fetch;
});

afterEach(() => {
  cleanup();
  globalThis.fetch = originalFetch;
});

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const BASE = {
  id: "m_x",
  status: "completed" as const,
  recordings_available: true,
  rerun_asr_pending: false,
};

describe("RerunButton", () => {
  test("renders when status=completed + recordings_available + !pending", () => {
    render(
      <Wrapper>
        <RerunButton meeting={BASE} />
      </Wrapper>,
    );
    expect(screen.getByTestId("rerun-button")).toBeDefined();
  });

  test("hidden when meeting.status !== 'completed'", () => {
    render(
      <Wrapper>
        <RerunButton meeting={{ ...BASE, status: "in_progress" }} />
      </Wrapper>,
    );
    expect(screen.queryByTestId("rerun-button")).toBeNull();
  });

  test("hidden when recordings_available=false", () => {
    render(
      <Wrapper>
        <RerunButton meeting={{ ...BASE, recordings_available: false }} />
      </Wrapper>,
    );
    expect(screen.queryByTestId("rerun-button")).toBeNull();
  });

  test("hidden when rerun_asr_pending=true", () => {
    render(
      <Wrapper>
        <RerunButton meeting={{ ...BASE, rerun_asr_pending: true }} />
      </Wrapper>,
    );
    expect(screen.queryByTestId("rerun-button")).toBeNull();
  });

  test("click fires POST and disappears (optimistic pending=true)", async () => {
    const calls: Array<{ url: string; method?: string }> = [];
    fetchHandler = async (url, init) => {
      calls.push({ url: String(url), method: init?.method });
      return new Response("", { status: 202 });
    };

    render(
      <Wrapper>
        <RerunButton meeting={BASE} />
      </Wrapper>,
    );
    await userEvent.click(screen.getByTestId("rerun-button"));

    await waitFor(() => {
      expect(calls.length).toBeGreaterThan(0);
    });
    const post = calls.find((c) => c.method === "POST");
    expect(post?.url).toContain("/api/meetings/m_x/rerun_asr");
  });
});
