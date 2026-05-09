/**
 * Slice 5 ingest: gateway injects X-User-Name + X-User-Email alongside X-User-Id.
 *
 * Per spec calendar-integration "POST from-calendar derives display names from
 * session identity and attendee filtering": the gateway MUST set the three
 * identity headers on every authenticated non-public /api/* request, sourced
 * from the active Better Auth session, and any client-supplied values for
 * those headers MUST be discarded. Public paths (/api/health) get none of them.
 */

import { describe, expect, test } from "bun:test";
import { createGatewayHandler, type GatewayDeps } from "../server";

type ExtendedSession = {
  user: { id: string; name?: string; email?: string };
} | null;

const mockAuth = (sessionResult: ExtendedSession): GatewayDeps["auth"] => ({
  handler: async () =>
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  api: {
    getSession: async () => sessionResult as unknown as never,
  },
});

type RecordedCall = { url: string; headers: Headers };

const mockFetch = () => {
  const calls: RecordedCall[] = [];
  const fn = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ url, headers: new Headers(init?.headers) });
    return new Response(JSON.stringify({ from: "backend" }), { status: 200 });
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

describe("Gateway injects X-User-Name + X-User-Email alongside X-User-Id", () => {
  test("authenticated /api/meetings forwards all three identity headers from session (URL-encoded for non-ASCII safety)", async () => {
    const { gateway, calls } = buildGateway(
      mockAuth({
        user: { id: "usr_abc", name: "Sean Chen", email: "sean@example.com" },
      }),
    );

    await gateway(new Request("http://localhost:3001/api/meetings"));

    expect(calls).toHaveLength(1);
    expect(calls[0]?.headers.get("X-User-Id")).toBe("usr_abc");
    // ASCII name encodes to itself except spaces (%20).
    expect(calls[0]?.headers.get("X-User-Name")).toBe("Sean%20Chen");
    expect(calls[0]?.headers.get("X-User-Email")).toBe("sean%40example.com");
  });

  test("non-ASCII Chinese name is URL-encoded so HTTP headers do not throw", async () => {
    const { gateway, calls } = buildGateway(
      mockAuth({
        user: { id: "usr_zh", name: "陳尚恩", email: "user@example.com" },
      }),
    );

    await gateway(new Request("http://localhost:3001/api/meetings"));

    const encoded = encodeURIComponent("陳尚恩");
    expect(calls[0]?.headers.get("X-User-Name")).toBe(encoded);
    // Decoding round-trips back to the original string.
    expect(decodeURIComponent(calls[0]?.headers.get("X-User-Name") ?? "")).toBe("陳尚恩");
  });

  test("client-supplied X-User-Name and X-User-Email headers are discarded and overwritten by session values", async () => {
    const { gateway, calls } = buildGateway(
      mockAuth({
        user: { id: "usr_real", name: "Sean Chen", email: "sean@example.com" },
      }),
    );

    await gateway(
      new Request("http://localhost:3001/api/meetings", {
        headers: {
          "X-User-Id": "usr_attacker",
          "X-User-Name": "Mallory",
          "X-User-Email": "mallory@evil.com",
        },
      }),
    );

    expect(calls[0]?.headers.get("X-User-Id")).toBe("usr_real");
    expect(calls[0]?.headers.get("X-User-Name")).toBe("Sean%20Chen");
    expect(calls[0]?.headers.get("X-User-Email")).toBe("sean%40example.com");
  });

  test("public /api/health does NOT receive any of the three identity headers", async () => {
    const { gateway, calls } = buildGateway(
      mockAuth({
        user: { id: "usr_should_not_leak", name: "Sean", email: "sean@x.com" },
      }),
    );

    await gateway(
      new Request("http://localhost:3001/api/health", {
        headers: {
          "X-User-Id": "client-supplied",
          "X-User-Name": "client-supplied",
          "X-User-Email": "client-supplied",
        },
      }),
    );

    expect(calls).toHaveLength(1);
    expect(calls[0]?.headers.get("X-User-Id")).toBeNull();
    expect(calls[0]?.headers.get("X-User-Name")).toBeNull();
    expect(calls[0]?.headers.get("X-User-Email")).toBeNull();
  });
});
