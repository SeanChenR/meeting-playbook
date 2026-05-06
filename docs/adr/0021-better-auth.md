# ADR-0021: Better Auth on Bun.serve, with Google OAuth and TOTP 2FA

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The product is single-user today (ADR-0001) but the user wants future-deploy-readiness. Adding auth retroactively is harder than building it in. The user picked Better Auth (https://github.com/better-auth/better-auth) — a TypeScript-first, framework-agnostic auth library with built-in social providers and 2FA.

## Decision
- Auth lives in `packages/auth`, served by `Bun.serve()` natively (no Hono / Express needed).
- Better Auth handles `/api/auth/*` routes via its `handler` function.
- The same Bun.serve process acts as an **API gateway**: any `/api/*` that is not `/api/auth/*` is proxied to the FastAPI backend on port 8000. WebSocket upgrades are also proxied.
- Social provider: Google OAuth.
- 2FA: TOTP via Better Auth's two-factor plugin (authenticator app of the user's choice).
- Session/cookie configuration: secure, httpOnly, samesite=lax.

## Consequences
- The Python backend trusts the auth gateway: it reads a session header injected by the gateway after Better Auth validates. The backend does not call out to the auth service for every request.
- Frontend talks to `localhost:3001` exclusively in dev (Vite proxies `/api/*` to it). In prod, the same Bun.serve process serves the built frontend `dist/` and gateways the API.
- One-time external setup: GCP OAuth client + redirect URI `http://localhost:3001/api/auth/callback/google`; user enrolls TOTP via authenticator app on first login.

## Alternatives considered
- **No auth in v1** — would require retrofit before any deploy.
- **NextAuth / Auth.js** — Next.js-coupled; we use Vite.
- **Lucia Auth** — viable but Better Auth's TOTP + social provider story is more batteries-included.
- **Bun.serve + Hono + Better Auth** — Hono is unnecessary; Better Auth integrates with Bun.serve directly.
