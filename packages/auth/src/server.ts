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
 *
 * Plus two dev-mode conveniences (not part of the spec):
 *   - PUBLIC_API_PATHS pass through without auth (e.g. /api/health for probes)
 *   - In dev, non-/api requests are reverse-proxied to the Vite dev server so
 *     the browser sees a single origin (the gateway). This avoids the
 *     cross-port cookie problem during OAuth callback redirects.
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
  /** When set, non-/api requests are proxied here (dev convenience). */
  viteUrl?: string;
  /** Inject for tests; defaults to globalThis.fetch. */
  fetch?: typeof fetch;
};

const AUTH_PREFIX = "/api/auth/";
const API_PREFIX = "/api/";

/** Paths under /api/* that the gateway forwards without an auth check. */
const PUBLIC_API_PATHS = new Set<string>(["/api/health"]);

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

    // /api/* (non-auth)
    if (url.pathname.startsWith(API_PREFIX)) {
      const isPublic = PUBLIC_API_PATHS.has(url.pathname);

      if (!isPublic) {
        const session = await deps.auth.api.getSession({ headers: req.headers });
        if (!session) {
          return unauthorized();
        }

        const wsUpgrade = isWebSocketUpgrade(req);

        const headers = new Headers(req.headers);
        stripBetterAuthCookies(headers);
        headers.set("X-User-Id", session.user.id);

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

      // Public API path — forward as-is (no auth check, no X-User-Id).
      const headers = new Headers(req.headers);
      stripBetterAuthCookies(headers);
      headers.delete("X-User-Id");
      const upstream = `${deps.backendUrl}${url.pathname}${url.search}`;
      return fetchImpl(upstream, {
        method: req.method,
        headers,
        body: req.body,
        // @ts-expect-error
        duplex: "half",
      });
    }

    // Non-/api — in dev, reverse-proxy to Vite so the browser sees a single
    // origin. In prod, the built dist/ should be served here (TODO when prod
    // build lands).
    if (deps.viteUrl) {
      const upstream = `${deps.viteUrl}${url.pathname}${url.search}`;
      const headers = new Headers(req.headers);
      // Vite expects the Host header to match its bind, but cross-fetch
      // tends to manage this. Strip cookies that aren't relevant.
      return fetchImpl(upstream, {
        method: req.method,
        headers,
        body: req.body,
        // @ts-expect-error
        duplex: "half",
      });
    }

    return new Response("Not Found", { status: 404 });
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Bun.serve entry point — only runs when this file is the entrypoint.
// ─────────────────────────────────────────────────────────────────────────────
if (import.meta.main) {
  const { auth } = await import("../auth");
  const isDev = process.env.NODE_ENV !== "production";
  const gateway = createGatewayHandler({
    auth,
    backendUrl: process.env.BACKEND_URL ?? "http://localhost:8000",
    viteUrl: isDev ? (process.env.VITE_URL ?? "http://localhost:5173") : undefined,
  });

  const port = Number(process.env.PORT ?? 3001);
  Bun.serve({
    port,
    fetch: gateway,
  });

  // eslint-disable-next-line no-console
  console.log(`auth gateway listening on http://localhost:${port} (dev=${isDev})`);
}
