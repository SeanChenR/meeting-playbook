/**
 * Better Auth instance — Google OAuth + email/password + TOTP 2FA on top of pg.Pool.
 *
 * Dual login (per slice-01 design revision):
 *   - Google OAuth: no app-level 2FA (Google's own 2FA covers it)
 *   - Email + password: opt-in TOTP 2FA via the twoFactor plugin
 *
 * Per ADR-0021 (Better Auth on Bun.serve) and ADR-0025 (no TS ORM —
 * Better Auth talks to pg.Pool directly).
 */

import { betterAuth } from "better-auth";
import { twoFactor } from "better-auth/plugins/two-factor";
import { Pool } from "pg";

type CreateAuthOptions = {
  /** Inject a pg.Pool (or pool-shaped object) for tests; defaults to one built from env. */
  database?: Pool;
  /** Override the secret; defaults to env. */
  secret?: string;
  /** Override Google credentials; defaults to env. */
  google?: { clientId: string; clientSecret: string };
  /** Override the base URL; defaults to BETTER_AUTH_URL env var or http://localhost:3001. */
  baseURL?: string;
};

const requireEnv = (name: string): string => {
  const v = process.env[name];
  if (!v) {
    throw new Error(
      `Missing required env var ${name}. ` +
        "Copy .env.example to .env and fill in the values, then restart.",
    );
  }
  return v;
};

export function createAuth(opts: CreateAuthOptions = {}) {
  const database = opts.database ?? new Pool({ connectionString: requireEnv("DATABASE_URL") });

  const secret = opts.secret ?? requireEnv("BETTER_AUTH_SECRET");

  const google = opts.google ?? {
    clientId: requireEnv("GOOGLE_OAUTH_CLIENT_ID"),
    clientSecret: requireEnv("GOOGLE_OAUTH_CLIENT_SECRET"),
  };

  const baseURL = opts.baseURL ?? process.env.BETTER_AUTH_URL ?? "http://localhost:3001";

  return betterAuth({
    appName: "Meeting Playbook",
    database,
    secret,
    baseURL,
    socialProviders: {
      google,
    },
    emailAndPassword: {
      enabled: true,
      autoSignIn: true,
      requireEmailVerification: false, // single-user side project; no SMTP wired
      minPasswordLength: 8,
    },
    plugins: [
      twoFactor({
        issuer: "Meeting Playbook",
      }),
    ],
    advanced: {
      cookies: {
        session_token: {
          attributes: {
            httpOnly: true,
            sameSite: "lax",
            // dev: false; flip to true when serving over HTTPS in prod
            secure: process.env.NODE_ENV === "production",
          },
        },
      },
    },
  });
}
