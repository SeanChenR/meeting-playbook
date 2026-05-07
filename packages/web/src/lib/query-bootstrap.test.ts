/**
 * Bootstrap test for TanStack Query integration.
 *
 * Verifies main.tsx mounts the QueryClient at the app root so all routes
 * can resolve useQuery / useMutation context.
 */

import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("main.tsx bootstraps TanStack Query", () => {
  const mainPath = join(__dirname, "..", "main.tsx");
  const main = readFileSync(mainPath, "utf-8");

  test("imports the queryClient singleton", () => {
    expect(main).toContain("./lib/query-client");
  });

  test("wraps <App /> with <QueryClientProvider>", () => {
    expect(main).toContain("QueryClientProvider");
    expect(main).toMatch(/<QueryClientProvider[^>]*>\s*<App\s*\/>/);
  });
});
