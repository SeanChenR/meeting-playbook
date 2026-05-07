/**
 * The app uses a single QueryClient instance per ADR (One QueryClient
 * mounted at app root). Defaults are picked for a local-first desktop tool:
 * - staleTime: 0 — every render kicks a refetch unless cached. Slices that
 *   need stickier caches override per-query.
 * - refetchOnWindowFocus: false — desktop tool, no point re-pulling on focus.
 *
 * If these defaults are loosened, existing tests that rely on them break.
 */

import { describe, expect, test } from "bun:test";
import { queryClient } from "./query-client";

describe("queryClient default options", () => {
  test("staleTime defaults to 0", () => {
    const opts = queryClient.getDefaultOptions().queries;
    expect(opts?.staleTime).toBe(0);
  });

  test("refetchOnWindowFocus defaults to false", () => {
    const opts = queryClient.getDefaultOptions().queries;
    expect(opts?.refetchOnWindowFocus).toBe(false);
  });

  test("module exports a singleton — repeated imports return the same instance", async () => {
    const a = await import("./query-client");
    const b = await import("./query-client");
    expect(a.queryClient).toBe(b.queryClient);
  });
});
