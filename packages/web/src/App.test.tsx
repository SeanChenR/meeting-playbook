import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render } from "@testing-library/react";

// Mock route-level dependencies BEFORE importing App
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
    useSession: () => ({ data: null, isPending: true }),
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

describe("App", () => {
  afterEach(() => cleanup());

  test("renders without crashing", () => {
    // Production wires this provider in main.tsx; the test mirrors that.
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
