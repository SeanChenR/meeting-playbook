/**
 * Internal token-store endpoints — Python backend ↔ Bun gateway only.
 *
 * Per ADR-0027 and slice-05 design:
 *   - GET  /__internal__/users/:id/calendar-token         → returns access token from Better Auth `account` row
 *   - POST /__internal__/users/:id/refresh-calendar-token → exchanges refresh_token at Google, updates row, returns new token
 *
 * Both endpoints MUST require the `X-Internal-Auth: <secret>` header. Without
 * it, the response is 401 + `auth.internal_unauthorized` envelope.
 */

import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { createInternalHandler, type InternalDeps } from "../internal";

const VALID_SECRET = "test-internal-secret";
const CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly";

// Better Auth uses camelCase column names; row shape mirrors the DB schema.
type AccountRow = {
  userId: string;
  providerId: string;
  accessToken: string | null;
  refreshToken: string | null;
  accessTokenExpiresAt: Date | null;
  scope: string | null; // Better Auth stores space-separated scopes
};

function makeMockPool(rows: AccountRow[]) {
  const updates: Array<{ sql: string; params: unknown[] }> = [];
  const pool = {
    query: mock(async (sql: string, params?: unknown[]) => {
      const lowered = sql.toLowerCase();
      if (lowered.startsWith("select")) {
        const [userId, providerId] = params ?? [];
        const matched = rows.filter((r) => r.userId === userId && r.providerId === providerId);
        return { rows: matched };
      }
      if (lowered.startsWith("update")) {
        // Mutate the in-memory row so subsequent SELECTs see the new token.
        const newToken = String(params?.[0] ?? "");
        const expiresAt = params?.[1] as Date | undefined;
        const userId = params?.[2];
        for (const r of rows) {
          if (r.userId === userId && r.providerId === "google") {
            r.accessToken = newToken;
            if (expiresAt) r.accessTokenExpiresAt = expiresAt;
          }
        }
        updates.push({ sql, params: params ?? [] });
        return { rows: [] };
      }
      return { rows: [] };
    }),
  };
  return { pool, updates };
}

function makeFakeGoogleFetch(refreshResponse: object | { _status: number; _body: object }) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchImpl = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ url, init });
    if (url.startsWith("https://oauth2.googleapis.com/token")) {
      const status = (refreshResponse as { _status?: number })._status ?? 200;
      const body = (refreshResponse as { _body?: object })._body ?? refreshResponse;
      return new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      });
    }
    return new Response("not found", { status: 404 });
  }) as unknown as typeof fetch;
  return { fetchImpl, calls };
}

function makeBaseRow(): AccountRow {
  return {
    userId: "u_alpha",
    providerId: "google",
    accessToken: "at_existing",
    refreshToken: "rt_existing",
    accessTokenExpiresAt: new Date(Date.now() + 3600 * 1000),
    scope: `openid email profile ${CALENDAR_SCOPE}`,
  };
}

describe("internal /calendar-token GET", () => {
  let handler: ReturnType<typeof createInternalHandler>;
  let pool: ReturnType<typeof makeMockPool>["pool"];

  beforeEach(() => {
    const m = makeMockPool([makeBaseRow()]);
    pool = m.pool;
    const { fetchImpl } = makeFakeGoogleFetch({});
    const deps: InternalDeps = {
      dbPool: pool as never,
      internalAuthSecret: VALID_SECRET,
      fetch: fetchImpl,
    };
    handler = createInternalHandler(deps);
  });

  afterEach(() => {
    pool.query.mockReset();
  });

  test("rejects request without X-Internal-Auth header (401)", async () => {
    const resp = await handler(
      new Request("http://localhost/__internal__/users/u_alpha/calendar-token"),
    );
    expect(resp.status).toBe(401);
    const body = (await resp.json()) as { error_code: string };
    expect(body.error_code).toBe("auth.internal_unauthorized");
  });

  test("rejects request with wrong secret (401)", async () => {
    const resp = await handler(
      new Request("http://localhost/__internal__/users/u_alpha/calendar-token", {
        headers: { "X-Internal-Auth": "WRONG-SECRET" },
      }),
    );
    expect(resp.status).toBe(401);
  });

  test("returns access token + expires_at for connected user", async () => {
    const resp = await handler(
      new Request("http://localhost/__internal__/users/u_alpha/calendar-token", {
        headers: { "X-Internal-Auth": VALID_SECRET },
      }),
    );
    expect(resp.status).toBe(200);
    const body = (await resp.json()) as {
      access_token: string;
      expires_at: string;
      scope: string;
    };
    expect(body.access_token).toBe("at_existing");
    expect(body.scope).toContain(CALENDAR_SCOPE);
    expect(body.expires_at).toBeDefined();
  });

  test("returns 404 + calendar.not_connected when no Google account row exists", async () => {
    const empty = makeMockPool([]);
    const handler2 = createInternalHandler({
      dbPool: empty.pool as never,
      internalAuthSecret: VALID_SECRET,
      fetch: globalThis.fetch,
    });
    const resp = await handler2(
      new Request("http://localhost/__internal__/users/u_missing/calendar-token", {
        headers: { "X-Internal-Auth": VALID_SECRET },
      }),
    );
    expect(resp.status).toBe(404);
    const body = (await resp.json()) as { error_code: string };
    expect(body.error_code).toBe("calendar.not_connected");
  });

  test("returns 404 + calendar.not_connected when account exists but has no calendar scope", async () => {
    const noScope = makeMockPool([{ ...makeBaseRow(), scope: "openid email profile" }]);
    const handler2 = createInternalHandler({
      dbPool: noScope.pool as never,
      internalAuthSecret: VALID_SECRET,
      fetch: globalThis.fetch,
    });
    const resp = await handler2(
      new Request("http://localhost/__internal__/users/u_alpha/calendar-token", {
        headers: { "X-Internal-Auth": VALID_SECRET },
      }),
    );
    expect(resp.status).toBe(404);
    const body = (await resp.json()) as { error_code: string };
    expect(body.error_code).toBe("calendar.not_connected");
  });
});

describe("internal /refresh-calendar-token POST", () => {
  test("rejects without secret", async () => {
    const m = makeMockPool([makeBaseRow()]);
    const { fetchImpl } = makeFakeGoogleFetch({});
    const handler = createInternalHandler({
      dbPool: m.pool as never,
      internalAuthSecret: VALID_SECRET,
      fetch: fetchImpl,
    });
    const resp = await handler(
      new Request("http://localhost/__internal__/users/u_alpha/refresh-calendar-token", {
        method: "POST",
      }),
    );
    expect(resp.status).toBe(401);
  });

  test("exchanges refresh_token at Google and updates the account row", async () => {
    const m = makeMockPool([makeBaseRow()]);
    const { fetchImpl, calls } = makeFakeGoogleFetch({
      access_token: "at_new_value",
      expires_in: 3600,
      token_type: "Bearer",
    });
    const handler = createInternalHandler({
      dbPool: m.pool as never,
      internalAuthSecret: VALID_SECRET,
      fetch: fetchImpl,
      google: { clientId: "test-client", clientSecret: "test-secret" },
    });

    const resp = await handler(
      new Request("http://localhost/__internal__/users/u_alpha/refresh-calendar-token", {
        method: "POST",
        headers: { "X-Internal-Auth": VALID_SECRET },
      }),
    );
    expect(resp.status).toBe(200);
    const body = (await resp.json()) as { access_token: string };
    expect(body.access_token).toBe("at_new_value");

    // Verify the Google token endpoint was called with grant_type=refresh_token
    const tokenCall = calls.find((c) => c.url.includes("oauth2.googleapis.com/token"));
    expect(tokenCall).toBeDefined();
    const formBody = String(tokenCall!.init?.body);
    expect(formBody).toContain("grant_type=refresh_token");
    expect(formBody).toContain("refresh_token=rt_existing");

    // Verify the account row was updated
    expect(m.updates.length).toBeGreaterThan(0);
    const updateParams = String(m.updates[0]?.params);
    expect(updateParams).toContain("at_new_value");
  });

  test("returns 401 + calendar.token_expired when Google rejects invalid_grant", async () => {
    const m = makeMockPool([makeBaseRow()]);
    const { fetchImpl } = makeFakeGoogleFetch({
      _status: 400,
      _body: { error: "invalid_grant", error_description: "Bad refresh token" },
    });
    const handler = createInternalHandler({
      dbPool: m.pool as never,
      internalAuthSecret: VALID_SECRET,
      fetch: fetchImpl,
      google: { clientId: "test-client", clientSecret: "test-secret" },
    });
    const resp = await handler(
      new Request("http://localhost/__internal__/users/u_alpha/refresh-calendar-token", {
        method: "POST",
        headers: { "X-Internal-Auth": VALID_SECRET },
      }),
    );
    expect(resp.status).toBe(401);
    const body = (await resp.json()) as { error_code: string };
    expect(body.error_code).toBe("calendar.token_expired");
  });
});
