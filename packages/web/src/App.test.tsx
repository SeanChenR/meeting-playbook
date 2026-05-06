import { afterEach, describe, expect, mock, test } from "bun:test";
import { cleanup, render } from "@testing-library/react";

// Mock route-level dependencies BEFORE importing App
mock.module("./lib/auth-client", () => ({
  authClient: {
    signIn: { social: async () => ({ data: {} }) },
    signOut: async () => ({}),
    useSession: () => ({ data: null, isPending: true }),
    twoFactor: {
      enable: async () => ({ data: { totpURI: "otpauth://test" } }),
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
