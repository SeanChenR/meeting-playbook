/**
 * Test fixture: render a component inside a TanStack Router memory history
 * + a fresh QueryClient. Each call builds a fresh router and client so
 * tests cannot leak cache state into each other.
 *
 * Usage:
 *   await renderWithRouter(<Login />, { initialEntries: ["/login"] });
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { ThemeProvider } from "../../lib/theme-provider";

interface Options {
  initialEntries?: string[];
  /** When the test only renders one component, a wrapper route is enough; the
   * test does not need the full app route tree. */
  path?: string;
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

/**
 * Render a component as the contents of a synthetic route. Use this when
 * the test cares about the component itself, not the route tree.
 */
export async function renderWithRouter(
  element: ReactElement,
  { initialEntries = ["/"], path = "/" }: Options = {},
): Promise<RenderResult & { router: ReturnType<typeof createRouter> }> {
  const rootRoute = createRootRoute({
    component: () => <Outlet />,
  });
  const childRoute = createRoute({
    getParentRoute: () => rootRoute,
    path,
    component: () => element,
  });
  const routeTree = rootRoute.addChildren([childRoute]);
  const history = createMemoryHistory({ initialEntries });
  const router = createRouter({ routeTree, history });
  await router.load();

  const queryClient = makeQueryClient();

  const utils = render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        {/* Cast through unknown — TanStack Router's typed Register can't be
            narrowed to the synthetic test routes; the runtime is identical. */}
        <RouterProvider
          router={router as unknown as Parameters<typeof RouterProvider>[0]["router"]}
        />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return { ...utils, router: router as ReturnType<typeof createRouter> };
}

/**
 * Render the production route tree against memory history. Use this when
 * the test exercises navigation across routes (e.g., create form redirects
 * to detail page).
 */
export async function renderAppRoutes(
  routeTree: Parameters<typeof createRouter>[0]["routeTree"],
  { initialEntries = ["/"] }: Options = {},
): Promise<{ utils: RenderResult; router: ReturnType<typeof createRouter> }> {
  const history = createMemoryHistory({ initialEntries });
  const router = createRouter({ routeTree, history });
  await router.load();
  const queryClient = makeQueryClient();
  const utils = render(
    <ThemeProvider initialTheme="light">
      <QueryClientProvider client={queryClient}>
        <RouterProvider
          router={router as unknown as Parameters<typeof RouterProvider>[0]["router"]}
        />
      </QueryClientProvider>
    </ThemeProvider>,
  );
  return { utils, router: router as ReturnType<typeof createRouter> };
}

/**
 * Bare QueryClient wrapper for hook tests that don't need a router.
 */
export function makeQueryWrapper() {
  const client = makeQueryClient();
  function wrapper({ children }: { children: ReactNode }) {
    return (
      <ThemeProvider initialTheme="light">
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </ThemeProvider>
    );
  }
  return { client, wrapper };
}
