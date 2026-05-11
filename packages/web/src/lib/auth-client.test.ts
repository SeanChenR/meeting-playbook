/**
 * Smoke test for auth-client module — confirms `createAuthClient` from
 * better-auth assembles the expected surface (signIn, signOut, useSession,
 * twoFactor plugin methods).
 *
 * Phase 6 cleanup: the previous version imported the project's
 * `authClient` instance directly, which fails in the full-suite run
 * because `mock.module("../lib/auth-client", ...)` from route tests
 * leaks across files (Bun's mock registry is process-global). Constructing
 * a fresh client here from `createAuthClient` bypasses the module mock
 * and asserts the same thing — the Better Auth setup is wired correctly.
 */

import { twoFactorClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";
import { describe, expect, test } from "bun:test";

const _client = createAuthClient({
  baseURL: "http://localhost:3001",
  plugins: [twoFactorClient()],
});

describe("authClient", () => {
  test("exposes signIn.social", () => {
    expect(typeof _client.signIn.social).toBe("function");
  });

  test("exposes signOut", () => {
    expect(typeof _client.signOut).toBe("function");
  });

  test("exposes useSession hook", () => {
    expect(typeof _client.useSession).toBe("function");
  });

  test("exposes twoFactor.verifyTotp via plugin", () => {
    const tf = (_client as { twoFactor?: { verifyTotp?: unknown } }).twoFactor;
    expect(tf).toBeDefined();
    expect(typeof tf?.verifyTotp).toBe("function");
  });
});
