/**
 * AsrProviderSelector — slice-11 task 6.1 component test.
 *
 * Per spec meeting-detail-layout scenarios:
 *   - dropdown reflects current meeting.asr_provider value
 *   - changing selection PATCHes the meeting + the switch hint stays visible
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";

import { AsrProviderSelector } from "./asr-provider-selector";

const originalFetch = globalThis.fetch;
let fetchHandler: (url: string, init?: RequestInit) => Promise<Response>;

beforeEach(() => {
  fetchHandler = async () =>
    new Response(
      JSON.stringify({
        id: "m_x",
        user_id: "u",
        title: "t",
        counterparty_display_name: "C",
        me_display_name: "M",
        status: "scheduled",
        asr_provider: "whisper",
        calendar_event_id: null,
        created_at: "2026-05-11T00:00:00Z",
        started_at: null,
        ended_at: null,
        scheduled_start_at: "2026-06-15T14:00:00Z",
        scheduled_end_at: null,
        recordings_available: false,
        rerun_asr_pending: false,
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
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

describe("AsrProviderSelector", () => {
  test("dropdown reflects current meeting.asr_provider", () => {
    render(
      <Wrapper>
        <AsrProviderSelector meeting={{ id: "m_x", asr_provider: "qwen3" }} />
      </Wrapper>,
    );
    const select = screen.getByTestId("asr-provider-selector") as HTMLSelectElement;
    expect(select.value).toBe("qwen3");
  });

  test("switch hint is always visible", () => {
    render(
      <Wrapper>
        <AsrProviderSelector meeting={{ id: "m_x", asr_provider: "qwen3" }} />
      </Wrapper>,
    );
    // zh-TW default
    expect(screen.getByText(/切換下一場會議生效/)).toBeDefined();
  });

  test("changing selection fires PATCH /api/meetings/{id}", async () => {
    const calls: Array<{ url: string; method?: string; body?: unknown }> = [];
    fetchHandler = async (url, init) => {
      calls.push({
        url: String(url),
        method: init?.method,
        body: init?.body ? JSON.parse(init.body as string) : undefined,
      });
      return new Response(
        JSON.stringify({
          id: "m_x",
          user_id: "u",
          title: "t",
          counterparty_display_name: "C",
          me_display_name: "M",
          status: "scheduled",
          asr_provider: "whisper",
          calendar_event_id: null,
          created_at: "2026-05-11T00:00:00Z",
          started_at: null,
          ended_at: null,
          scheduled_start_at: "2026-06-15T14:00:00Z",
          scheduled_end_at: null,
          recordings_available: false,
          rerun_asr_pending: false,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    };

    render(
      <Wrapper>
        <AsrProviderSelector meeting={{ id: "m_x", asr_provider: "qwen3" }} />
      </Wrapper>,
    );
    const select = screen.getByTestId("asr-provider-selector") as HTMLSelectElement;
    await userEvent.selectOptions(select, "whisper");

    await waitFor(() => {
      expect(calls.length).toBeGreaterThan(0);
    });
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.url).toContain("/api/meetings/m_x");
    expect(patch?.body).toEqual({ asr_provider: "whisper" });
  });
});
