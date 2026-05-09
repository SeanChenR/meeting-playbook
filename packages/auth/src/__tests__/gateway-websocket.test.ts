/**
 * Slice 6 — gateway authenticates WebSocket upgrades and forwards identity
 * headers, mirroring the regular `/api/*` proxy path.
 *
 * Per spec auth-gateway-contract ADDED requirement "Gateway authenticates
 * and proxies WebSocket upgrades with identity headers preserved":
 * - Authenticated WS upgrade carries X-User-Id / X-User-Name / X-User-Email
 *   (URL-encoded for non-ASCII safety)
 * - Unauthenticated WS upgrade is rejected before reaching the backend
 * - Public path (/api/health) WS upgrade attempt does NOT receive identity
 *   headers (treated as a regular public-path forward, no auth)
 */

import { describe, expect, mock, test } from "bun:test";
import { createGatewayHandler, type GatewayDeps } from "../server";

type SessionLike = { user: { id: string; name?: string; email?: string } } | null;

const mockAuth = (session: SessionLike): GatewayDeps["auth"] => ({
  handler: async () =>
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  api: { getSession: async () => session as never },
});

type RecordedCall = { url: string; headers: Headers };

const mockFetch = () => {
  const calls: RecordedCall[] = [];
  const fn = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ url, headers: new Headers(init?.headers) });
    return new Response(JSON.stringify({ from: "backend" }), { status: 101 });
  }) as typeof fetch;
  return { fn, calls };
};

const buildGateway = (auth: GatewayDeps["auth"]) => {
  const { fn, calls } = mockFetch();
  const gateway = createGatewayHandler({
    auth,
    backendUrl: "http://localhost:8000",
    fetch: fn,
  });
  return { gateway, calls };
};

const wsUpgradeHeaders = {
  upgrade: "websocket",
  connection: "Upgrade",
  "sec-websocket-version": "13",
  "sec-websocket-key": "dGhlIHNhbXBsZSBub25jZQ==",
};

describe("Gateway authenticates and proxies WebSocket upgrades", () => {
  test("authenticated WS upgrade carries the three identity headers (URL-encoded)", async () => {
    const { gateway, calls } = buildGateway(
      mockAuth({
        user: { id: "usr_abc", name: "Sean Chen", email: "sean@example.com" },
      }),
    );

    await gateway(
      new Request("http://localhost:3001/api/meetings/m_abc/session", {
        headers: wsUpgradeHeaders,
      }),
    );

    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).toContain("/api/meetings/m_abc/session");
    expect(calls[0]?.headers.get("X-User-Id")).toBe("usr_abc");
    expect(calls[0]?.headers.get("X-User-Name")).toBe("Sean%20Chen");
    expect(calls[0]?.headers.get("X-User-Email")).toBe("sean%40example.com");
  });

  test("unauthenticated WS upgrade is rejected and upstream is NOT contacted", async () => {
    const { gateway, calls } = buildGateway(mockAuth(null));

    const resp = await gateway(
      new Request("http://localhost:3001/api/meetings/m_abc/session", {
        headers: wsUpgradeHeaders,
      }),
    );

    expect(resp.status).toBe(401);
    const body = (await resp.json()) as { error_code: string };
    expect(body.error_code).toBe("auth.unauthenticated");
    expect(calls).toHaveLength(0);
  });

  test("public-path WS upgrade attempt forwards without identity headers", async () => {
    const { gateway, calls } = buildGateway(
      mockAuth({
        user: { id: "usr_should_not_leak", name: "Sean", email: "sean@x.com" },
      }),
    );

    await gateway(
      new Request("http://localhost:3001/api/health", {
        headers: { ...wsUpgradeHeaders, "X-User-Id": "client-supplied" },
      }),
    );

    expect(calls).toHaveLength(1);
    expect(calls[0]?.headers.get("X-User-Id")).toBeNull();
    expect(calls[0]?.headers.get("X-User-Name")).toBeNull();
    expect(calls[0]?.headers.get("X-User-Email")).toBeNull();
  });
});
