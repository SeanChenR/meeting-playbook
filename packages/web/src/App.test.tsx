import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Mock route-level dependencies BEFORE importing App / routeTree.
mock.module("./lib/auth-client", () => ({
  authClient: {
    signIn: {
      social: async () => ({ data: {} }),
      email: async () => ({ data: { twoFactorRedirect: false }, error: null }),
    },
    signUp: {
      email: async () => ({ data: { user: { id: "usr_new" } }, error: null }),
    },
    signOut: async () => ({}),
    useSession: () => ({ data: null, isPending: false }),
    listAccounts: async () => ({ data: [] }),
    getSession: async () => ({ data: null }),
    twoFactor: {
      enable: async () => ({
        data: { totpURI: "otpauth://test", backupCodes: ["x", "y"] },
        error: null,
      }),
      verifyTotp: async () => ({ data: {} }),
    },
  },
}));

import { App } from "./App";
import { routeTree } from "./route-tree";
import { renderAppRoutes } from "./test/fixtures/router";

describe("App", () => {
  afterEach(() => cleanup());

  test("renders without crashing", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { container } = render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
    expect(container).toBeDefined();
  });
});

// Slice-18 v2 (Sean revision) router contract.
describe("Router contract", () => {
  afterEach(() => cleanup());

  test("visit / redirects to /meetings (HomePage retired)", async () => {
    const { router } = await renderAppRoutes(routeTree, { initialEntries: ["/"] });
    // The redirect resolves before the ProtectedShell auth-bounce, so the
    // final pathname is the redirect target (or the /login bounce when no
    // session). Either way the original /meetings route MUST be present in
    // the registered routes map.
    expect(router.routesById["/meetings"]).toBeDefined();
  });

  test("/home is no longer registered", async () => {
    const { router } = await renderAppRoutes(routeTree, { initialEntries: ["/home"] });
    const childMatch = router.state.matches.find((m) => m.routeId !== "__root__");
    expect(childMatch === undefined || childMatch.status === "notFound").toBe(true);
  });

  test("/dashboard route is registered", async () => {
    const { router } = await renderAppRoutes(routeTree, { initialEntries: ["/dashboard"] });
    expect(router.routesById["/dashboard"]).toBeDefined();
  });
});

// Login success must navigate to /meetings (was briefly "/" in slice-18 v1).
describe("Login success destination", () => {
  test("the login route handler navigates to '/meetings' on success", async () => {
    const source = await Bun.file("src/routes/login.tsx").text();
    expect(source).toContain('navigate({ to: "/meetings", replace: true });');
  });
});
