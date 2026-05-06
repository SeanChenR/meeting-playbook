# ADR-0021: Better Auth on Bun.serve — dual login (Google + email/password) with opt-in TOTP

- **Status**: Accepted (revised 2026-05-06)
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The product is single-user today (ADR-0001) but the user wants future-deploy-readiness. Adding auth retroactively is harder than building it in. The user picked Better Auth (https://github.com/better-auth/better-auth) — a TypeScript-first, framework-agnostic auth library with built-in social providers and 2FA.

When implementing Slice 1 (#2), the Better Auth two-factor plugin docs surfaced a constraint: **TOTP enrollment requires a credential (email/password) account** because `twoFactor.enable({password})` validates the password before generating the secret. Pure Google-OAuth users have no password and cannot enroll TOTP through this plugin.

This drove a design revision: support **two login paths in parallel** — the mainstream Google OAuth path (no app-level 2FA, since Google itself enforces 2FA on most accounts), plus an email/password path that gets opt-in TOTP.

## Decision
- Auth lives in `packages/auth`, served by `Bun.serve()` natively (no Hono / Express needed).
- Better Auth handles `/api/auth/*` routes via its `handler` function.
- The same Bun.serve process acts as an **API gateway**: any `/api/*` that is not `/api/auth/*` is proxied to the FastAPI backend on port 8000. WebSocket upgrades are also proxied with `X-User-Id` injection (per spec `auth-gateway-contract`).
- **Login methods enabled in parallel**:
  - **Google OAuth** — `socialProviders.google` configured. No app-level 2FA enforced; Google's own 2FA covers it.
  - **Email + password** — `emailAndPassword.enabled = true`, `minPasswordLength = 8`, `requireEmailVerification = false` (no SMTP wired in slice 1; revisit when deploy approaches), `autoSignIn = true`.
- **TOTP 2FA** is enabled via the `twoFactor` plugin with `issuer: "Meeting Playbook"`, but **opt-in**: a user with a password can choose "Enable two-factor" from `/home`, walk through the password-confirm → QR + backup codes → 6-digit verify flow. After enrolment, subsequent email/password logins go through `/totp/verify` before reaching `/home`.
- Session cookie: `httpOnly`, `sameSite=lax`, `secure` flips to `true` when `NODE_ENV === "production"`.

## Consequences
- The Python backend trusts the auth gateway: it reads the `X-User-Id` header injected by the gateway after Better Auth validates the session. The backend does not call out to the auth service for every request.
- Frontend talks to `localhost:3001` exclusively in dev (Vite proxies `/api/*` to it). In prod, the same Bun.serve process serves the built frontend `dist/` and gateways the API.
- The user's Google-OAuth identity and email/password identity are linked through Better Auth's `account` table; if the user signs in with Google for the same email they later sign up with, Better Auth's `accountLinking` (default `true`) merges them.
- One-time external setup: GCP OAuth client + redirect URI `http://localhost:3001/api/auth/callback/google`. TOTP enrolment is no longer required at first login; the user opts in from `/home` whenever they want it.
- The Better Auth schema (`user`, `session`, `account`, `verification`, `twoFactor`) is initialized via `@better-auth/cli generate + migrate --config packages/auth/auth.ts`. Re-run after any plugin or config change.

## Alternatives considered
- **No auth in v1** — would require retrofit before any deploy.
- **NextAuth / Auth.js** — Next.js-coupled; we use Vite.
- **Lucia Auth** — viable but Better Auth's TOTP + social provider story is more batteries-included.
- **Bun.serve + Hono + Better Auth** — Hono is unnecessary; Better Auth integrates with Bun.serve directly.
- **Google OAuth only with no 2FA option** — first design before the Better Auth constraint surfaced; rejected because it removes the user-control affordance for higher-security workflows.
- **Forced TOTP at first login** — original Slice 1 design; rejected because it cannot apply to Google-only users.
- **Auto-create a placeholder password for Google users so they can enrol TOTP** — rejected as a security smell (random password the user does not know creates a phantom credential surface).

## Schema impact
| Table | Owner | Notes |
|---|---|---|
| `user` | Better Auth | Adds `twoFactorEnabled` boolean (per twoFactor plugin) |
| `session` | Better Auth | Standard schema |
| `account` | Better Auth | Stores `password` for credential accounts; `providerId` distinguishes "credential" vs "google" rows |
| `verification` | Better Auth | Email verification, password reset tokens |
| `twoFactor` | Better Auth | `secret`, `backupCodes`, `userId`, `verified` |

Application tables (Slice 3+) FK to `user.id` from the Better Auth side.
