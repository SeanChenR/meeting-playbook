/**
 * Calendar scope grant + status endpoints — gateway-side wrappers around
 * Better Auth's `linkSocialAccount` and `listUserAccounts` APIs.
 *
 * Per ADR-0027:
 *   - POST /api/auth/calendar/link    → initiates OAuth with calendar.events.readonly
 *   - GET  /api/auth/calendar/status  → { connected: bool } based on the user's account scopes
 */

import { describe, expect, mock, test } from "bun:test";
import { createGatewayHandler, type GatewayDeps } from "../server";

const CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly";

function makeAuth({
  session,
  linkResult,
  accountScopes,
}: {
  session: { user: { id: string } } | null;
  linkResult?: { url?: string; redirect?: boolean };
  accountScopes?: string[];
}) {
  const linkSocialAccount = mock(
    async (_opts: unknown) => linkResult ?? { url: "https://accounts.google.com/oauth?scope=..." },
  );
  const listUserAccounts = mock(async (_opts: unknown) => [
    {
      providerId: "google",
      accountId: "google_account_42",
      scopes: accountScopes ?? [],
      id: "acc_42",
      userId: session?.user.id ?? "u_unknown",
      createdAt: new Date(),
      updatedAt: new Date(),
    },
  ]);

  const auth: GatewayDeps["auth"] = {
    handler: async () =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    api: {
      getSession: async () => session,
      // Extra methods used by /api/auth/calendar/* — typed loose because GatewayDeps['auth'] only requires handler+getSession.
      linkSocialAccount,
      listUserAccounts,
    } as unknown as GatewayDeps["auth"]["api"],
  };
  return { auth, linkSocialAccount, listUserAccounts };
}

describe("POST /api/auth/calendar/link", () => {
  test("requires a session — without one returns 401", async () => {
    const { auth } = makeAuth({ session: null });
    const gateway = createGatewayHandler({
      auth,
      backendUrl: "http://localhost:8000",
    });

    const resp = await gateway(
      new Request("http://localhost:3001/api/auth/calendar/link", {
        method: "POST",
      }),
    );
    expect(resp.status).toBe(401);
    const body = (await resp.json()) as { error_code: string };
    expect(body.error_code).toBe("auth.unauthenticated");
  });

  test("authenticated POST calls linkSocialAccount with calendar.events.readonly scope", async () => {
    const { auth, linkSocialAccount } = makeAuth({
      session: { user: { id: "u_alpha" } },
      linkResult: { url: "https://accounts.google.com/oauth?scope=calendar", redirect: true },
    });
    const gateway = createGatewayHandler({
      auth,
      backendUrl: "http://localhost:8000",
    });

    const resp = await gateway(
      new Request("http://localhost:3001/api/auth/calendar/link", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ callbackURL: "/calendar" }),
      }),
    );

    expect(resp.status).toBe(200);
    const body = (await resp.json()) as { url: string };
    expect(body.url).toContain("accounts.google.com");

    expect(linkSocialAccount).toHaveBeenCalledTimes(1);
    const callArg = linkSocialAccount.mock.calls[0]?.[0] as {
      body: { provider: string; scopes: string[]; callbackURL?: string };
    };
    expect(callArg.body.provider).toBe("google");
    expect(callArg.body.scopes).toContain(CALENDAR_SCOPE);
    expect(callArg.body.callbackURL).toBe("/calendar");
  });
});

describe("GET /api/auth/calendar/status", () => {
  test("requires a session", async () => {
    const { auth } = makeAuth({ session: null });
    const gateway = createGatewayHandler({
      auth,
      backendUrl: "http://localhost:8000",
    });

    const resp = await gateway(new Request("http://localhost:3001/api/auth/calendar/status"));
    expect(resp.status).toBe(401);
  });

  test("returns connected=true when the Google account row carries the calendar scope", async () => {
    const { auth } = makeAuth({
      session: { user: { id: "u_alpha" } },
      accountScopes: ["openid", "email", "profile", CALENDAR_SCOPE],
    });
    const gateway = createGatewayHandler({
      auth,
      backendUrl: "http://localhost:8000",
    });

    const resp = await gateway(new Request("http://localhost:3001/api/auth/calendar/status"));
    expect(resp.status).toBe(200);
    const body = (await resp.json()) as { connected: boolean };
    expect(body.connected).toBe(true);
  });

  test("returns connected=false when scope is missing", async () => {
    const { auth } = makeAuth({
      session: { user: { id: "u_alpha" } },
      accountScopes: ["openid", "email", "profile"],
    });
    const gateway = createGatewayHandler({
      auth,
      backendUrl: "http://localhost:8000",
    });

    const resp = await gateway(new Request("http://localhost:3001/api/auth/calendar/status"));
    expect(resp.status).toBe(200);
    const body = (await resp.json()) as { connected: boolean };
    expect(body.connected).toBe(false);
  });
});
