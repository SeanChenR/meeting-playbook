/**
 * useImportFromCalendarMutation contract: on success the ['meetings'] cache
 * is invalidated so the list page refetches and shows the new meeting.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useImportFromCalendarMutation } from "./calendar-api";

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
    if (init?.method === "POST" && url.includes("/api/meetings/from-calendar")) {
      return new Response(JSON.stringify({ meeting_id: "m_imported" }), {
        status: 201,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not found", { status: 404 });
  }) as unknown as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  cleanup();
});

describe("useImportFromCalendarMutation", () => {
  test("on success invalidates ['meetings']", async () => {
    const { client, wrapper } = makeWrapper();
    const invalidateSpy = mock(client.invalidateQueries.bind(client));
    client.invalidateQueries = invalidateSpy as typeof client.invalidateQueries;

    const { result } = renderHook(() => useImportFromCalendarMutation(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync("gcal_evt_42");
    });

    await waitFor(() => {
      expect(invalidateSpy.mock.calls.length).toBeGreaterThan(0);
    });
    const calls = invalidateSpy.mock.calls.map((c) => JSON.stringify(c[0]));
    expect(calls.some((s) => s.includes('"meetings"'))).toBe(true);
  });
});
