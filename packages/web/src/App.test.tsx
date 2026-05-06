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
    const { container } = render(<App />);
    expect(container).toBeDefined();
  });
});
