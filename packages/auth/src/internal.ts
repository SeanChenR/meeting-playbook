/**
 * Internal token-store endpoints — Python backend ↔ Bun gateway only.
 *
 * Per ADR-0027 + slice-05 design:
 *   - GET  /__internal__/users/:id/calendar-token         → returns the user's Google access token + scope
 *   - POST /__internal__/users/:id/refresh-calendar-token → exchanges refresh_token at Google, updates the row, returns new token
 *
 * Both endpoints require `X-Internal-Auth: <secret>`. Without it the response
 * is 401 + envelope `{error_code: "auth.internal_unauthorized"}`. The
 * Python `TokenStore` is the only intended caller; the path prefix
 * `/__internal__/` is bound to localhost in production.
 */

import type { Pool } from "pg";

const CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly";
const PROVIDER_ID = "google";
const GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token";

export type InternalDeps = {
  dbPool: Pool;
  internalAuthSecret: string;
  /** Inject for tests; defaults to globalThis.fetch in production wiring. */
  fetch?: typeof fetch;
  /** Override Google OAuth client credentials (defaults to env). */
  google?: { clientId: string; clientSecret: string };
};

const TOKEN_PATH = /^\/__internal__\/users\/([^/]+)\/calendar-token$/;
const REFRESH_PATH = /^\/__internal__\/users\/([^/]+)\/refresh-calendar-token$/;

function envelope(status: number, errorCode: string, message: string): Response {
  return new Response(JSON.stringify({ error_code: errorCode, message }), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function unauthorized(): Response {
  return envelope(401, "auth.internal_unauthorized", "Missing or invalid X-Internal-Auth header.");
}

function notConnected(): Response {
  return envelope(404, "calendar.not_connected", "User has not granted Google Calendar scope.");
}

function tokenExpired(): Response {
  return envelope(
    401,
    "calendar.token_expired",
    "Stored refresh token is no longer valid; user must reconnect Calendar.",
  );
}

export function createInternalHandler(deps: InternalDeps) {
  const fetchImpl = deps.fetch ?? globalThis.fetch;

  async function selectAccount(userId: string) {
    const result = await deps.dbPool.query(
      'SELECT "userId", "providerId", "accessToken", "refreshToken", "accessTokenExpiresAt", "scope" ' +
        'FROM account WHERE "userId" = $1 AND "providerId" = $2 LIMIT 1',
      [userId, PROVIDER_ID],
    );
    return result.rows[0] as
      | {
          userId: string;
          providerId: string;
          accessToken: string | null;
          refreshToken: string | null;
          accessTokenExpiresAt: Date | null;
          scope: string | null;
        }
      | undefined;
  }

  async function getCalendarToken(userId: string): Promise<Response> {
    const row = await selectAccount(userId);
    if (!row || !row.scope || !row.scope.includes(CALENDAR_SCOPE) || !row.accessToken) {
      return notConnected();
    }
    return new Response(
      JSON.stringify({
        access_token: row.accessToken,
        scope: row.scope,
        expires_at: row.accessTokenExpiresAt?.toISOString() ?? null,
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }

  async function refreshCalendarToken(userId: string): Promise<Response> {
    const row = await selectAccount(userId);
    if (!row || !row.refreshToken) return notConnected();

    const clientId = deps.google?.clientId ?? process.env.GOOGLE_OAUTH_CLIENT_ID;
    const clientSecret = deps.google?.clientSecret ?? process.env.GOOGLE_OAUTH_CLIENT_SECRET;
    if (!clientId || !clientSecret) {
      return envelope(
        500,
        "common.internal_error",
        "Google OAuth client credentials are not configured.",
      );
    }

    const body = new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: row.refreshToken,
      client_id: clientId,
      client_secret: clientSecret,
    });

    const resp = await fetchImpl(GOOGLE_TOKEN_URL, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: body.toString(),
    });

    if (resp.status === 400 || resp.status === 401) {
      return tokenExpired();
    }
    if (!resp.ok) {
      return envelope(
        502,
        "calendar.network_error",
        "Google token endpoint returned an unexpected error.",
      );
    }

    const data = (await resp.json()) as { access_token: string; expires_in?: number };
    const newAccessToken = data.access_token;
    const expiresAt = new Date(Date.now() + (data.expires_in ?? 3600) * 1000);

    await deps.dbPool.query(
      'UPDATE account SET "accessToken" = $1, "accessTokenExpiresAt" = $2, "updatedAt" = now() ' +
        'WHERE "userId" = $3 AND "providerId" = $4',
      [newAccessToken, expiresAt, userId, PROVIDER_ID],
    );

    return new Response(
      JSON.stringify({
        access_token: newAccessToken,
        expires_at: expiresAt.toISOString(),
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }

  return async function handle(req: Request): Promise<Response> {
    const url = new URL(req.url);

    const tokenMatch = url.pathname.match(TOKEN_PATH);
    const refreshMatch = url.pathname.match(REFRESH_PATH);

    if (!tokenMatch && !refreshMatch) {
      return envelope(404, "http.404", `No internal route for ${url.pathname}`);
    }

    const provided = req.headers.get("X-Internal-Auth");
    if (!provided || provided !== deps.internalAuthSecret) {
      return unauthorized();
    }

    if (tokenMatch && req.method === "GET") {
      return getCalendarToken(tokenMatch[1]!);
    }
    if (refreshMatch && req.method === "POST") {
      return refreshCalendarToken(refreshMatch[1]!);
    }

    return envelope(405, "http.405", `Method not allowed for ${url.pathname}`);
  };
}
