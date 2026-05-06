/**
 * Better Auth React client — talks to the gateway origin.
 *
 * In dev, Vite proxies /api/* to the gateway (localhost:3001) so the relative
 * `/api/auth` path resolves correctly through both same-origin (prod) and
 * proxy (dev) modes.
 */

import { twoFactorClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";

const inferBaseURL = (): string => {
  if (typeof window !== "undefined") {
    const origin = window.location?.origin;
    if (origin && origin !== "null") return origin;
  }
  return "http://localhost:3001";
};

export const authClient = createAuthClient({
  baseURL: inferBaseURL(),
  plugins: [twoFactorClient()],
});

export type AuthClient = typeof authClient;
