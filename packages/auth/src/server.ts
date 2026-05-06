/**
 * Bun.serve gateway — auth ingress + reverse proxy to FastAPI backend.
 *
 * Implements `auth-gateway-contract` (openspec/changes/slice-01-auth-shell/specs):
 *   - Routes /api/auth/* to the Better Auth handler
 *   - Validates Better Auth session for non-auth /api/*
 *   - Injects X-User-Id header (overwriting any client-supplied value)
 *   - Strips Better Auth session cookie from forwarded requests
 *   - Preserves method, body, query, other headers
 *   - Forwards WebSocket upgrades with X-User-Id (frame relay lands in Slice 6)
 */

type SessionLike = { user: { id: string } } | null;

type AuthLike = {
  handler: (req: Request) => Promise<Response> | Response;
  api: {
    getSession: (opts: { headers: Headers }) => Promise<SessionLike> | SessionLike;
  };
};

export type GatewayDeps = {
  auth: AuthLike;
  backendUrl: string;
  /** Inject for tests; defaults to globalThis.fetch. */
  fetch?: typeof fetch;
};

const AUTH_PREFIX = "/api/auth/";
const API_PREFIX = "/api/";

const BETTER_AUTH_COOKIE_PREFIXES = [
  "better-auth.",
  "__Host-better-auth.",
  "__Secure-better-auth.",
];

function stripBetterAuthCookies(headers: Headers): void {
  const cookieHeader = headers.get("cookie");
  if (!cookieHeader) return;

  const remaining = cookieHeader
    .split(";")
    .map((c) => c.trim())
    .filter((c) => !BETTER_AUTH_COOKIE_PREFIXES.some((prefix) => c.startsWith(prefix)))
    .join("; ");

  if (remaining) {
    headers.set("cookie", remaining);
  } else {
    headers.delete("cookie");
  }
}

function isWebSocketUpgrade(req: Request): boolean {
  return req.headers.get("upgrade")?.toLowerCase() === "websocket";
}

function unauthorized(): Response {
  return new Response(
    JSON.stringify({
      error_code: "auth.unauthenticated",
      message: "A valid Better Auth session is required for this endpoint.",
    }),
    {
      status: 401,
      headers: { "content-type": "application/json" },
    },
  );
}

export function createGatewayHandler(deps: GatewayDeps) {
  const fetchImpl = deps.fetch ?? globalThis.fetch;

  return async function gateway(req: Request): Promise<Response> {
    const url = new URL(req.url);

    // /api/auth/* — Better Auth owns this namespace.
    if (url.pathname.startsWith(AUTH_PREFIX)) {
      return deps.auth.handler(req);
    }

    // /api/* (non-auth) — validate session, inject X-User-Id, proxy.
    if (url.pathname.startsWith(API_PREFIX)) {
      const session = await deps.auth.api.getSession({ headers: req.headers });
      if (!session) {
        return unauthorized();
      }

      const wsUpgrade = isWebSocketUpgrade(req);

      // Build forwarded headers
      const headers = new Headers(req.headers);
      stripBetterAuthCookies(headers);
      headers.set("X-User-Id", session.user.id); // overwrite any client-supplied value

      const upstream = `${deps.backendUrl}${url.pathname}${url.search}`;

      const init: RequestInit = {
        method: req.method,
        headers,
        body: wsUpgrade ? null : req.body,
        // @ts-expect-error: Bun supports `duplex: "half"` for streaming bodies
        duplex: wsUpgrade ? undefined : "half",
      };

      return fetchImpl(upstream, init);
    }

    return new Response("Not Found", { status: 404 });
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Bun.serve entry point — only runs when this file is the entrypoint.
// ─────────────────────────────────────────────────────────────────────────────
if (import.meta.main) {
  // Reuse the singleton built for the Better Auth CLI (../auth.ts).
  const { auth } = await import("../auth");
  const gateway = createGatewayHandler({
    auth,
    backendUrl: process.env.BACKEND_URL ?? "http://localhost:8000",
  });

  const port = Number(process.env.PORT ?? 3001);
  Bun.serve({
    port,
    fetch: gateway,
  });

  // eslint-disable-next-line no-console
  console.log(`auth gateway listening on http://localhost:${port}`);
}
