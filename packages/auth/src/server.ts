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

type SessionLike = { user: { id: string; name?: string; email?: string } } | null;

type AccountListItem = {
  providerId: string;
  scopes?: string[];
};

type AuthLike = {
  handler: (req: Request) => Promise<Response> | Response;
  api: {
    getSession: (opts: { headers: Headers }) => Promise<SessionLike> | SessionLike;
    linkSocialAccount?: (opts: {
      body: { provider: string; scopes: string[]; callbackURL?: string };
      headers: Headers;
    }) => Promise<{ url?: string; redirect?: boolean } | Response>;
    listUserAccounts?: (opts: { headers: Headers }) => Promise<AccountListItem[]>;
  };
};

export type GatewayDeps = {
  auth: AuthLike;
  backendUrl: string;
  /** When set, non-/api requests are proxied here (dev convenience). */
  viteUrl?: string;
  /** Inject for tests; defaults to globalThis.fetch. */
  fetch?: typeof fetch;
  /** Optional internal handler for /__internal__/* paths (Python ↔ gateway). */
  internalHandler?: (req: Request) => Promise<Response>;
};

const AUTH_PREFIX = "/api/auth/";
const API_PREFIX = "/api/";
const INTERNAL_PREFIX = "/__internal__/";

const CALENDAR_LINK_PATH = "/api/auth/calendar/link";
const CALENDAR_STATUS_PATH = "/api/auth/calendar/status";
const CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly";

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

/**
 * Build the standard error envelope JSON response used everywhere a non-2xx
 * leaves the gateway. Frontend reads `error_code` to choose a localized
 * message; `message` is a developer-facing English fallback.
 */
function errorEnvelope(status: number, errorCode: string, message: string): Response {
  return new Response(JSON.stringify({ error_code: errorCode, message }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function unauthorized(): Response {
  return errorEnvelope(
    401,
    "auth.unauthenticated",
    "A valid Better Auth session is required for this endpoint.",
  );
}

export function createGatewayHandler(deps: GatewayDeps) {
  const fetchImpl = deps.fetch ?? globalThis.fetch;

  return async function gateway(req: Request): Promise<Response> {
    try {
      return await routeRequest(req);
    } catch {
      // Hide internal details — clients see a stable error_code only.
      return errorEnvelope(
        500,
        "common.internal_error",
        "An unexpected error occurred while processing the request.",
      );
    }
  };

  async function calendarLink(req: Request): Promise<Response> {
    const session = await deps.auth.api.getSession({ headers: req.headers });
    if (!session) return unauthorized();

    const linkSocialAccount = deps.auth.api.linkSocialAccount;
    if (!linkSocialAccount) {
      return errorEnvelope(
        500,
        "common.internal_error",
        "linkSocialAccount API is not available on this Better Auth build.",
      );
    }

    let callbackURL: string | undefined;
    try {
      const body = (await req.json()) as { callbackURL?: string };
      callbackURL = body.callbackURL;
    } catch {
      // Empty body is fine; callbackURL stays undefined.
    }

    const result = await linkSocialAccount({
      body: {
        provider: "google",
        scopes: [CALENDAR_SCOPE],
        ...(callbackURL ? { callbackURL } : {}),
      },
      headers: req.headers,
    });

    if (result instanceof Response) return result;

    return new Response(
      JSON.stringify({
        url: result.url ?? null,
        redirect: result.redirect ?? false,
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }

  async function calendarStatus(req: Request): Promise<Response> {
    const session = await deps.auth.api.getSession({ headers: req.headers });
    if (!session) return unauthorized();

    const listUserAccounts = deps.auth.api.listUserAccounts;
    if (!listUserAccounts) {
      return errorEnvelope(
        500,
        "common.internal_error",
        "listUserAccounts API is not available on this Better Auth build.",
      );
    }

    const accounts = await listUserAccounts({ headers: req.headers });
    const google = accounts.find((a) => a.providerId === "google");
    const connected = google?.scopes?.includes(CALENDAR_SCOPE) === true;

    return new Response(JSON.stringify({ connected }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }

  async function routeRequest(req: Request): Promise<Response> {
    const url = new URL(req.url);

    // /__internal__/* — Python backend ↔ gateway only (X-Internal-Auth required).
    if (url.pathname.startsWith(INTERNAL_PREFIX)) {
      if (!deps.internalHandler) {
        return errorEnvelope(404, "http.404", `No internal handler configured`);
      }
      return deps.internalHandler(req);
    }

    // /api/auth/calendar/* — Calendar scope grant + status (custom routes
    // wrapping Better Auth's linkSocialAccount + listUserAccounts).
    if (url.pathname === CALENDAR_LINK_PATH && req.method === "POST") {
      return calendarLink(req);
    }
    if (url.pathname === CALENDAR_STATUS_PATH && req.method === "GET") {
      return calendarStatus(req);
    }

    // /api/auth/* — Better Auth owns the rest of this namespace.
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
        // Slice 5 ingest: backend uses these to populate me_display_name and
        // pick the counterparty when importing a Calendar event. Always set
        // (never trust client-supplied), even when the field is empty.
        // URL-encode because HTTP headers reject non-ISO-8859-1 (user.name
        // is often Chinese / Japanese / emoji); backend dependency decodes.
        headers.set("X-User-Name", encodeURIComponent(session.user.name ?? ""));
        headers.set("X-User-Email", encodeURIComponent(session.user.email ?? ""));

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

      // Public API path — forward as-is (no auth check, no identity headers).
      const headers = new Headers(req.headers);
      stripBetterAuthCookies(headers);
      headers.delete("X-User-Id");
      headers.delete("X-User-Name");
      headers.delete("X-User-Email");
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

    return errorEnvelope(404, "http.404", `No route for ${url.pathname}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Bun.serve entry point — only runs when this file is the entrypoint.
// ─────────────────────────────────────────────────────────────────────────────
if (import.meta.main) {
  const { auth } = await import("../auth");
  const { Pool } = await import("pg");
  const { createInternalHandler } = await import("./internal");
  const isDev = process.env.NODE_ENV !== "production";

  const internalSecret = process.env.BACKEND_INTERNAL_AUTH_SECRET;
  const dbUrl = process.env.DATABASE_URL;
  const internalHandler =
    internalSecret && dbUrl
      ? createInternalHandler({
          dbPool: new Pool({ connectionString: dbUrl }),
          internalAuthSecret: internalSecret,
        })
      : undefined;

  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const gateway = createGatewayHandler({
    auth,
    backendUrl,
    viteUrl: isDev ? (process.env.VITE_URL ?? "http://localhost:5173") : undefined,
    internalHandler,
  });

  // ─── WebSocket proxy bridge (slice-06) ────────────────────────────────
  // The fetch-based gateway path (createGatewayHandler) handles HTTP only.
  // WS upgrades for /api/* are intercepted here: we authenticate, then
  // upgrade the client connection and open a parallel WS to the upstream
  // FastAPI backend, bridging frames in both directions.

  type BridgeData = {
    upstream: WebSocket | null;
    pending: Array<string | Uint8Array>;
    upstreamReady: boolean;
  };

  const port = Number(process.env.PORT ?? 3001);
  Bun.serve<BridgeData, undefined>({
    port,
    async fetch(req, server) {
      const url = new URL(req.url);
      const isApiNonAuth =
        url.pathname.startsWith(API_PREFIX) &&
        !url.pathname.startsWith(AUTH_PREFIX) &&
        !PUBLIC_API_PATHS.has(url.pathname);

      if (isApiNonAuth && isWebSocketUpgrade(req)) {
        const session = await auth.api.getSession({ headers: req.headers });
        if (!session) return unauthorized();

        const wsUrl = backendUrl.replace(/^http/, "ws") + url.pathname + url.search;
        const userName = encodeURIComponent(session.user.name ?? "");
        const userEmail = encodeURIComponent(session.user.email ?? "");

        // Open upstream WS to FastAPI with identity headers injected.
        const upstream = new WebSocket(wsUrl, {
          // Bun extension: custom headers on WebSocket client
          headers: {
            "X-User-Id": session.user.id,
            "X-User-Name": userName,
            "X-User-Email": userEmail,
          },
        } as never);

        const upgraded = server.upgrade(req, {
          data: {
            upstream,
            pending: [] as Array<string | Uint8Array>,
            upstreamReady: false,
          } satisfies BridgeData,
        });
        if (!upgraded) {
          upstream.close();
          return new Response("WebSocket upgrade failed", { status: 500 });
        }
        return undefined;
      }

      return gateway(req);
    },
    websocket: {
      open(ws) {
        const { upstream } = ws.data;
        if (!upstream) return;

        upstream.addEventListener("open", () => {
          ws.data.upstreamReady = true;
          for (const m of ws.data.pending) upstream.send(m);
          ws.data.pending = [];
        });
        upstream.addEventListener("message", (ev) => {
          ws.send(ev.data as string);
        });
        upstream.addEventListener("close", () => {
          ws.close();
        });
        upstream.addEventListener("error", () => {
          ws.close();
        });
      },
      message(ws, message) {
        const { upstream, upstreamReady } = ws.data;
        if (!upstream) return;
        if (upstreamReady) {
          upstream.send(message as string);
        } else {
          ws.data.pending.push(message as string | Uint8Array);
        }
      },
      close(ws) {
        ws.data.upstream?.close();
      },
    },
  });

  // eslint-disable-next-line no-console
  console.log(`auth gateway listening on http://localhost:${port} (dev=${isDev})`);
}
