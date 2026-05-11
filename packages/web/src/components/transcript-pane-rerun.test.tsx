/**
 * TranscriptPane re-run overlay — slice-11 task 6.2 component test.
 *
 * Per spec meeting-detail-layout scenarios:
 *   - overlay visible during pending re-run with "(processed/total chunks)" text
 *   - overlay hidden when status transitions to idle; pending=false omits overlay
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { TranscriptPane } from "./transcript-pane";

const originalFetch = globalThis.fetch;
let fetchHandler: (url: string, init?: RequestInit) => Promise<Response>;

beforeEach(() => {
  fetchHandler = async () =>
    new Response(JSON.stringify({ status: "idle", chunks_processed: 0, chunks_total: 0 }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
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

describe("TranscriptPane re-run overlay", () => {
  test("rerunPending=true shows overlay with progress text after status fetch", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify({ status: "pending", chunks_processed: 12, chunks_total: 45 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    render(
      <Wrapper>
        <TranscriptPane
          chunks={[]}
          meDisplayName="Sean"
          counterpartyDisplayName="林經理"
          meetingId="m_overlay"
          rerunPending
        />
      </Wrapper>,
    );

    const overlay = await screen.findByTestId("transcript-rerun-overlay");
    expect(overlay).toBeDefined();
    await waitFor(() => {
      expect(overlay.textContent).toContain("(12/45 chunks)");
    });
  });

  test("rerunPending=true with chunks_total=0 shows '(...)' placeholder", async () => {
    fetchHandler = async () =>
      new Response(JSON.stringify({ status: "pending", chunks_processed: 0, chunks_total: 0 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });

    render(
      <Wrapper>
        <TranscriptPane
          chunks={[]}
          meDisplayName="Sean"
          counterpartyDisplayName="林經理"
          meetingId="m_overlay"
          rerunPending
        />
      </Wrapper>,
    );

    const overlay = await screen.findByTestId("transcript-rerun-overlay");
    expect(overlay.textContent).toContain("(...)");
  });

  test("rerunPending=false omits overlay", () => {
    render(
      <Wrapper>
        <TranscriptPane
          chunks={[]}
          meDisplayName="Sean"
          counterpartyDisplayName="林經理"
          meetingId="m_overlay"
          rerunPending={false}
        />
      </Wrapper>,
    );
    expect(screen.queryByTestId("transcript-rerun-overlay")).toBeNull();
  });

  test("no meetingId omits overlay (pre-slice-11 callers still work)", () => {
    render(
      <Wrapper>
        <TranscriptPane chunks={[]} meDisplayName="Sean" counterpartyDisplayName="林經理" />
      </Wrapper>,
    );
    expect(screen.queryByTestId("transcript-rerun-overlay")).toBeNull();
  });
});
