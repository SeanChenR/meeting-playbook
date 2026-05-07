/**
 * useUpsertPlaybookMutation contract: on PUT success, the
 * `["playbook", meetingId]` cache is invalidated so any mounted view
 * automatically refetches.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useUpsertPlaybookMutation } from "./playbook-api";

const originalFetch = globalThis.fetch;

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

beforeEach(() => {
  globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    if (init?.method === "PUT" && url.includes("/playbook")) {
      return new Response(
        JSON.stringify({
          id: "pb_x",
          meeting_id: "m_target",
          free_form_markdown: "ok",
          objective: "",
          counterparty_profile: "",
          anticipated_topics: "",
          anticipated_objections: "",
          talking_points: "",
          red_lines: "",
          created_at: "2026-05-07T10:00:00Z",
          updated_at: "2026-05-07T10:00:00Z",
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    return new Response("not found", { status: 404 });
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  cleanup();
});

describe("useUpsertPlaybookMutation", () => {
  test("on success invalidates ['playbook', meetingId]", async () => {
    const { client, wrapper } = makeWrapper();
    const invalidateSpy = mock(client.invalidateQueries.bind(client));
    client.invalidateQueries = invalidateSpy as typeof client.invalidateQueries;

    const { result } = renderHook(() => useUpsertPlaybookMutation("m_target"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        free_form_markdown: "ok",
        objective: "",
        counterparty_profile: "",
        anticipated_topics: "",
        anticipated_objections: "",
        talking_points: "",
        red_lines: "",
      });
    });

    await waitFor(() => {
      expect(invalidateSpy.mock.calls.length).toBeGreaterThan(0);
    });
    const calls = invalidateSpy.mock.calls.map((c) => JSON.stringify(c[0]));
    expect(calls.some((s) => s.includes('"playbook"') && s.includes("m_target"))).toBe(true);
  });
});
