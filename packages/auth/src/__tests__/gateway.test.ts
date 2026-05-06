/**
 * Tests for the Bun.serve gateway fetch handler.
 *
 * Covers all 6 requirements from spec `auth-gateway-contract`:
 *   - Routes auth-namespace requests to Better Auth handler
 *   - Authenticates non-auth /api/* requests
 *   - Injects X-User-Id header on forwarded requests
 *   - FastAPI backend trusts X-User-Id (verified via integration; here we verify forwarding)
 *   - Forwarded requests preserve client request metadata
 *   - WebSocket upgrades carry X-User-Id
 */

import { describe, expect, test } from "bun:test";
import { createGatewayHandler, type GatewayDeps } from "../server";

type SessionLike = { user: { id: string } } | null;

const mockAuth = (sessionResult: SessionLike = null): GatewayDeps["auth"] => ({
  handler: async (req: Request) => {
    return new Response(JSON.stringify({ from: "auth", path: new URL(req.url).pathname }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  },
  api: {
    getSession: async () => sessionResult,
  },
});

type RecordedCall = {
  url: string;
  method: string;
  headers: Headers;
  body: BodyInit | null | undefined;
};

const mockFetch = () => {
  const calls: RecordedCall[] = [];
  const fn: typeof fetch = (async (input: any, init: RequestInit = {}) => {
    const url = typeof input === "string" ? input : input.url;
    const headers = init.headers instanceof Headers ? init.headers : new Headers(init.headers);
    calls.push({
      url,
      method: init.method ?? "GET",
      headers,
      body: init.body,
    });
    return new Response("backend ok", {
      status: 200,
      headers: { "x-test": "from-backend" },
    });
  }) as typeof fetch;
  return { fn, calls };
};

const buildGateway = (auth: GatewayDeps["auth"]) => {
  const f = mockFetch();
  const gateway = createGatewayHandler({
    auth,
    backendUrl: "http://localhost:8000",
    fetch: f.fn,
  });
  return { gateway, calls: f.calls };
};

// ─── Requirement: Gateway routes auth-namespace requests to Better Auth handler ───
describe("Gateway routes auth-namespace requests to Better Auth handler", () => {
  test("POST /api/auth/sign-in/social → auth.handler", async () => {
    const { gateway, calls } = buildGateway(mockAuth());
    const req = new Request("http://localhost:3001/api/auth/sign-in/social", {
      method: "POST",
    });

    const res = await gateway(req);

    expect(res.status).toBe(200);
    const body = (await res.json()) as { from: string; path: string };
    expect(body.from).toBe("auth");
    expect(body.path).toBe("/api/auth/sign-in/social");
    expect(calls).toHaveLength(0); // backend never contacted
  });

  test("POST /api/auth/two-factor/enable → auth.handler", async () => {
    const { gateway } = buildGateway(mockAuth());
    const req = new Request("http://localhost:3001/api/auth/two-factor/enable", {
      method: "POST",
    });

    const res = await gateway(req);

    expect(res.status).toBe(200);
    const body = (await res.json()) as { path: string };
    expect(body.path).toBe("/api/auth/two-factor/enable");
  });
});

// ─── Requirement: Gateway authenticates non-auth /api/* requests ───
describe("Gateway authenticates non-auth /api/* requests", () => {
  test("returns 401 when no session for GET /api/me", async () => {
    const { gateway, calls } = buildGateway(mockAuth(null));
    const req = new Request("http://localhost:3001/api/me");

    const res = await gateway(req);

    expect(res.status).toBe(401);
    expect(calls).toHaveLength(0); // backend never contacted
    const body = (await res.json()) as { error_code: string };
    expect(body.error_code).toBe("auth.unauthenticated");
  });

  test("returns 401 when getSession resolves null (treat as expired)", async () => {
    const { gateway, calls } = buildGateway(mockAuth(null));
    const req = new Request("http://localhost:3001/api/meetings", {
      headers: { cookie: "better-auth.session_token=expired" },
    });

    const res = await gateway(req);

    expect(res.status).toBe(401);
    expect(calls).toHaveLength(0);
  });

  test("forwards to backend when session is valid", async () => {
    const { gateway, calls } = buildGateway(mockAuth({ user: { id: "usr_abc" } }));
    const req = new Request("http://localhost:3001/api/me");

    const res = await gateway(req);

    expect(res.status).toBe(200);
    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).toBe("http://localhost:8000/api/me");
  });
});

// ─── Requirement: Gateway injects X-User-Id header on forwarded requests ───
describe("Gateway injects X-User-Id header on forwarded requests", () => {
  test("sets X-User-Id from session.user.id", async () => {
    const { gateway, calls } = buildGateway(mockAuth({ user: { id: "usr_abc123" } }));
    const req = new Request("http://localhost:3001/api/me");

    await gateway(req);

    expect(calls[0]?.headers.get("X-User-Id")).toBe("usr_abc123");
  });

  test("overwrites client-supplied X-User-Id header (anti-impersonation)", async () => {
    const { gateway, calls } = buildGateway(mockAuth({ user: { id: "usr_legit" } }));
    const req = new Request("http://localhost:3001/api/me", {
      headers: { "X-User-Id": "usr_attacker" },
    });

    await gateway(req);

    expect(calls[0]?.headers.get("X-User-Id")).toBe("usr_legit");
  });
});

// ─── Requirement: Forwarded requests preserve client request metadata ───
describe("Forwarded requests preserve client request metadata", () => {
  test("preserves POST body", async () => {
    const { gateway, calls } = buildGateway(mockAuth({ user: { id: "usr" } }));
    const body = JSON.stringify({ title: "Q4 review" });
    const req = new Request("http://localhost:3001/api/meetings", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
    });

    await gateway(req);

    expect(calls[0]?.method).toBe("POST");
    expect(calls[0]?.body).toBeDefined();
    expect(calls[0]?.headers.get("content-type")).toBe("application/json");
  });

  test("preserves query string verbatim", async () => {
    const { gateway, calls } = buildGateway(mockAuth({ user: { id: "usr" } }));
    const req = new Request("http://localhost:3001/api/meetings?limit=20&page=2");

    await gateway(req);

    expect(calls[0]?.url).toBe("http://localhost:8000/api/meetings?limit=20&page=2");
  });

  test("strips Better Auth session cookie but preserves other cookies", async () => {
    const { gateway, calls } = buildGateway(mockAuth({ user: { id: "usr" } }));
    const req = new Request("http://localhost:3001/api/me", {
      headers: {
        cookie:
          "better-auth.session_token=secret123; analytics_id=abc; __Host-better-auth.csrf=xyz",
      },
    });

    await gateway(req);

    const fwdCookie = calls[0]?.headers.get("cookie") ?? "";
    expect(fwdCookie).not.toContain("better-auth.");
    expect(fwdCookie).not.toContain("__Host-better-auth.");
    expect(fwdCookie).toContain("analytics_id=abc");
  });

  test("removes cookie header entirely when only Better Auth cookies present", async () => {
    const { gateway, calls } = buildGateway(mockAuth({ user: { id: "usr" } }));
    const req = new Request("http://localhost:3001/api/me", {
      headers: { cookie: "better-auth.session_token=only-this" },
    });

    await gateway(req);

    expect(calls[0]?.headers.get("cookie")).toBeNull();
  });
});

// ─── Requirement: WebSocket upgrades carry X-User-Id ───
describe("WebSocket upgrades carry X-User-Id", () => {
  test("forwards WS upgrade with X-User-Id when session is valid", async () => {
    const { gateway, calls } = buildGateway(mockAuth({ user: { id: "usr_ws" } }));
    const req = new Request("http://localhost:3001/api/meetings/123/session", {
      headers: {
        upgrade: "websocket",
        connection: "upgrade",
        "sec-websocket-key": "test-key",
        "sec-websocket-version": "13",
      },
    });

    await gateway(req);

    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).toBe("http://localhost:8000/api/meetings/123/session");
    expect(calls[0]?.headers.get("X-User-Id")).toBe("usr_ws");
    expect(calls[0]?.headers.get("upgrade")).toBe("websocket");
  });

  test("rejects WS upgrade with 401 when no session", async () => {
    const { gateway, calls } = buildGateway(mockAuth(null));
    const req = new Request("http://localhost:3001/api/meetings/1/session", {
      headers: { upgrade: "websocket", connection: "upgrade" },
    });

    const res = await gateway(req);

    expect(res.status).toBe(401);
    expect(calls).toHaveLength(0);
  });
});

// ─── Public API paths (gateway forwards without auth) ───
describe("PUBLIC_API_PATHS pass through without auth", () => {
  test("/api/health forwards to backend without session validation", async () => {
    const f = mockFetch();
    const gateway = createGatewayHandler({
      auth: mockAuth(null), // no session
      backendUrl: "http://localhost:8000",
      fetch: f.fn,
    });

    const res = await gateway(new Request("http://localhost:3001/api/health"));

    expect(res.status).toBe(200);
    expect(f.calls).toHaveLength(1);
    expect(f.calls[0]?.url).toBe("http://localhost:8000/api/health");
    // No X-User-Id should be set on a public path
    expect(f.calls[0]?.headers.get("X-User-Id")).toBeNull();
  });

  test("a non-public /api/* path with no session still returns 401", async () => {
    const { gateway, calls } = buildGateway(mockAuth(null));

    const res = await gateway(new Request("http://localhost:3001/api/me"));

    expect(res.status).toBe(401);
    expect(calls).toHaveLength(0);
  });
});

// ─── Non-API paths ───
describe("non-API paths", () => {
  test("returns 404 when no viteUrl configured (production behavior)", async () => {
    const { gateway } = buildGateway(mockAuth({ user: { id: "usr" } }));
    const req = new Request("http://localhost:3001/unrelated");

    const res = await gateway(req);

    expect(res.status).toBe(404);
  });

  test("proxies to viteUrl when configured (dev convenience)", async () => {
    const f = mockFetch();
    const gateway = createGatewayHandler({
      auth: mockAuth({ user: { id: "usr" } }),
      backendUrl: "http://localhost:8000",
      viteUrl: "http://localhost:5173",
      fetch: f.fn,
    });

    const res = await gateway(new Request("http://localhost:3001/home"));

    expect(res.status).toBe(200);
    expect(f.calls).toHaveLength(1);
    expect(f.calls[0]?.url).toBe("http://localhost:5173/home");
  });

  test("proxies root / to Vite when configured", async () => {
    const f = mockFetch();
    const gateway = createGatewayHandler({
      auth: mockAuth(null),
      backendUrl: "http://localhost:8000",
      viteUrl: "http://localhost:5173",
      fetch: f.fn,
    });

    await gateway(new Request("http://localhost:3001/"));

    expect(f.calls[0]?.url).toBe("http://localhost:5173/");
  });

  test("preserves query string when proxying to Vite", async () => {
    const f = mockFetch();
    const gateway = createGatewayHandler({
      auth: mockAuth({ user: { id: "usr" } }),
      backendUrl: "http://localhost:8000",
      viteUrl: "http://localhost:5173",
      fetch: f.fn,
    });

    await gateway(new Request("http://localhost:3001/login?next=/home"));

    expect(f.calls[0]?.url).toBe("http://localhost:5173/login?next=/home");
  });
});
