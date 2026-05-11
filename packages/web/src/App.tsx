import { createRouter, RouterProvider } from "@tanstack/react-router";
import { ThemeProvider } from "./lib/theme-provider";
import { Toaster } from "./components/ui/sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { routeTree } from "./route-tree";

const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

/**
 * App root — wraps the router with the three global Contexts:
 *   ThemeProvider     — `data-theme` attr + useTheme() hook (slice ui-overhaul)
 *   TooltipProvider   — radix tooltip group (1.3)
 *   <Toaster />       — sonner global toast portal (1.3)
 *
 * QueryClientProvider is mounted one level up in main.tsx so query state
 * spans the React StrictMode boundary too.
 */
export function App() {
  return (
    <ThemeProvider>
      <TooltipProvider delayDuration={200}>
        <RouterProvider router={router} />
        <Toaster />
      </TooltipProvider>
    </ThemeProvider>
  );
}
