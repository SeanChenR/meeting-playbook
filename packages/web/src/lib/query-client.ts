/**
 * Single QueryClient instance for the whole web app.
 *
 * Mounted at app root via main.tsx's <QueryClientProvider>. Slices that
 * want stickier caches override per-query; the global defaults stay tight
 * so list/detail views always reflect server state on remount.
 */

import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 0,
      refetchOnWindowFocus: false,
    },
  },
});
