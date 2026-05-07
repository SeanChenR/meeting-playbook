/**
 * AC-7 Error envelope contract — Bun gateway side.
 *
 * Every error response from the gateway MUST carry the JSON envelope
 *   `{ error_code: <snake.dot.code>, message: <string> }`
 * so the frontend can localize via `errors.<code>` keys.
 *
 * Covered failure modes:
 *  - 401 unauthenticated (no session for non-public /api/*)
 *  - 404 unknown path (no viteUrl, non-/api request)
 *  - 5xx generic error when the proxied fetch throws
 */

import { describe, expect, test } from "bun:test";
import { createGatewayHandler, type GatewayDeps } from "../server";

const mockAuthNoSession: GatewayDeps["auth"] = {
  handler: async () =>
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  api: { getSession: async () => null },
};

const mockAuthValid: GatewayDeps["auth"] = {
  handler: async () => new Response(JSON.stringify({ ok: true }), { status: 200 }),
  api: { getSession: async () => ({ user: { id: "usr_x" } }) },
};

describe("Error envelope — gateway 401 unauthenticated", () => {
  test("returns {error_code, message} for /api/me without session", async () => {
    const gateway = createGatewayHandler({
      auth: mockAuthNoSession,
      backendUrl: "http://localhost:8000",
      fetch: (async () => new Response("backend", { status: 200 })) as typeof fetch,
    });

    const res = await gateway(new Request("http://localhost:3001/api/me"));

    expect(res.status).toBe(401);
    const body = (await res.json()) as { error_code: string; message: string };
    expect(body.error_code).toBe("auth.unauthenticated");
    expect(typeof body.message).toBe("string");
    expect(body.message.length).toBeGreaterThan(0);
  });
});

describe("Error envelope — gateway 404 unknown path", () => {
  test("returns {error_code, message} for non-/api path without viteUrl", async () => {
    const gateway = createGatewayHandler({
      auth: mockAuthValid,
      backendUrl: "http://localhost:8000",
      fetch: (async () => new Response("backend", { status: 200 })) as typeof fetch,
    });

    const res = await gateway(new Request("http://localhost:3001/unknown-page"));

    expect(res.status).toBe(404);
    const body = (await res.json()) as { error_code: string; message: string };
    expect(body.error_code).toBe("http.404");
    expect(typeof body.message).toBe("string");
  });
});

describe("Error envelope — gateway 500 fallback when fetch throws", () => {
  test("upstream fetch error surfaces as common.internal_error", async () => {
    const throwingFetch: typeof fetch = (async () => {
      throw new Error("upstream unreachable");
    }) as typeof fetch;

    const gateway = createGatewayHandler({
      auth: mockAuthValid,
      backendUrl: "http://localhost:8000",
      fetch: throwingFetch,
    });

    const res = await gateway(new Request("http://localhost:3001/api/me"));

    expect(res.status).toBe(500);
    const body = (await res.json()) as { error_code: string; message: string };
    expect(body.error_code).toBe("common.internal_error");
    expect(typeof body.message).toBe("string");
  });
});
