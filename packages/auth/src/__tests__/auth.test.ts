/**
 * Smoke tests for createAuth — verifies a Better Auth instance is constructed
 * with the expected surface (handler + api.getSession). Does not exercise DB.
 */

import { describe, expect, test } from "bun:test";
import { createAuth } from "../auth";

const stubPool = (): any => ({
  query: async () => ({ rows: [], rowCount: 0 }),
  connect: async () => ({
    release: () => {},
    query: async () => ({ rows: [], rowCount: 0 }),
  }),
  end: async () => {},
  on: () => {},
  removeListener: () => {},
});

describe("createAuth", () => {
  test("returns instance with handler function and api.getSession function", () => {
    const auth = createAuth({
      database: stubPool(),
      secret: "test-secret-32-bytes-base64-encoded-stub",
      google: { clientId: "test-client-id", clientSecret: "test-client-secret" },
    });

    expect(typeof auth.handler).toBe("function");
    expect(auth.api).toBeDefined();
    expect(typeof auth.api.getSession).toBe("function");
  });

  test("throws helpful error when DATABASE_URL env var is missing and no database injected", () => {
    const original = process.env.DATABASE_URL;
    delete process.env.DATABASE_URL;
    try {
      expect(() =>
        createAuth({
          secret: "test-secret",
          google: { clientId: "id", clientSecret: "secret" },
        }),
      ).toThrow(/DATABASE_URL/);
    } finally {
      if (original !== undefined) process.env.DATABASE_URL = original;
    }
  });
});
