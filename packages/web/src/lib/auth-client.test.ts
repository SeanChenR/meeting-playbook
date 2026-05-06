/**
 * Smoke test for auth-client module — confirms the client object is constructed
 * with the expected surface (signIn, signOut, useSession, twoFactor methods).
 */

import { describe, expect, test } from "bun:test";
import { authClient } from "./auth-client";

describe("authClient", () => {
  test("exposes signIn.social", () => {
    expect(typeof authClient.signIn.social).toBe("function");
  });

  test("exposes signOut", () => {
    expect(typeof authClient.signOut).toBe("function");
  });

  test("exposes useSession hook", () => {
    expect(typeof authClient.useSession).toBe("function");
  });

  test("exposes twoFactor.verifyTotp via plugin", () => {
    const tf = (authClient as { twoFactor?: { verifyTotp?: unknown } }).twoFactor;
    expect(tf).toBeDefined();
    expect(typeof tf?.verifyTotp).toBe("function");
  });
});
