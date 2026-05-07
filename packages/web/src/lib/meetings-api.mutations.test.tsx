/**
 * Mutation hook contract: on success the meeting cache invalidates so any
 * mounted list / detail view refetches automatically.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useCreateMeetingMutation, useDeleteMeetingMutation } from "./meetings-api";

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
    if (init?.method === "POST" && url.endsWith("/api/meetings")) {
      return new Response(
        JSON.stringify({
          id: "m_new",
          user_id: "u",
          title: "T",
          counterparty_display_name: "C",
          me_display_name: "M",
          status: "scheduled",
          asr_provider: "whisper",
          calendar_event_id: null,
          created_at: "2026-05-07T10:00:00Z",
          started_at: null,
          ended_at: null,
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      );
    }
    if (init?.method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    return new Response("[]", {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  cleanup();
});

describe("useCreateMeetingMutation", () => {
  test("on success invalidates the ['meetings'] list cache", async () => {
    const { client, wrapper } = makeWrapper();
    const invalidateSpy = mock(client.invalidateQueries.bind(client));
    client.invalidateQueries = invalidateSpy as typeof client.invalidateQueries;

    const { result } = renderHook(() => useCreateMeetingMutation(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({
        title: "T",
        counterparty_display_name: "C",
        me_display_name: "M",
      });
    });

    await waitFor(() => {
      expect(invalidateSpy.mock.calls.length).toBeGreaterThan(0);
    });
    const calledWith = invalidateSpy.mock.calls.map((c) => JSON.stringify(c[0]));
    expect(calledWith.some((s) => s.includes('"meetings"'))).toBe(true);
  });
});

describe("useDeleteMeetingMutation", () => {
  test("on success invalidates ['meetings'] and ['meetings', id]", async () => {
    const { client, wrapper } = makeWrapper();
    const invalidateSpy = mock(client.invalidateQueries.bind(client));
    client.invalidateQueries = invalidateSpy as typeof client.invalidateQueries;

    const { result } = renderHook(() => useDeleteMeetingMutation(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync("m_target");
    });

    await waitFor(() => {
      expect(invalidateSpy.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    const calls = invalidateSpy.mock.calls.map((c) => JSON.stringify(c[0]));
    expect(calls.some((s) => s.includes('"meetings"') && !s.includes("m_target"))).toBe(true);
    expect(calls.some((s) => s.includes("m_target"))).toBe(true);
  });
});

describe("useQueryClient is the same singleton", () => {
  test("two hooks under the same provider observe the same client", () => {
    const { wrapper } = makeWrapper();
    const { result: a } = renderHook(() => useQueryClient(), { wrapper });
    const { result: b } = renderHook(() => useQueryClient(), { wrapper });
    expect(a.current).toBe(b.current);
  });
});
