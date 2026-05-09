# ADR-0027: Calendar scope grant via Better Auth `linkSocial`

- **Status**: Accepted
- **Date**: 2026-05-08
- **Decider**: Sean

## Context

Slice 5 (`slice-05-calendar-llm-playbook`) requires reading the user's
Google Calendar. The login OAuth granted only `openid email profile` (per
slice-01); Calendar needs the additional scope
`https://www.googleapis.com/auth/calendar.events.readonly`. The user is
already logged in and we do not want to force re-login.

The slice design noted two implementation options:

1. Better Auth's `linkSocial({ provider: "google", scopes: [...] })` — extend
   the existing Google account with the new scope.
2. Hand-rolled OAuth callback — issue our own authorize URL with the new
   scope and store the resulting token in a custom column on `account`.

A 30-minute spike inspected the Better Auth 1.6.9 type definitions at
`node_modules/better-auth/dist/api/routes/account.d.mts`.

## Decision

Use Better Auth's native `linkSocialAccount` endpoint
(`POST /api/auth/link-social`) with body
`{ provider: "google", scopes: [...] }`. The `scopes` field is part of the
public API surface as of Better Auth 1.6.9. The connection-status check
uses `listUserAccounts`, which returns each account's `scopes: string[]`
field.

## Consequences

- We add **no** new schema, no custom OAuth callback, no Google `client_id`
  duplication. Tokens land in the existing `account` table fields
  (`accessToken`, `refreshToken`, `accessTokenExpiresAt`, `scopes`).
- Slice 5's `/api/auth/calendar/link` becomes a thin wrapper that calls
  `auth.api.linkSocialAccount({ body: { provider: "google", scopes: [CALENDAR_SCOPE] } })`.
- Slice 5's `/api/auth/calendar/status` becomes a thin wrapper around
  `auth.api.listUserAccounts(...)` and a check that the Google account row
  contains the calendar scope.
- The Python backend's `TokenStore` reads the token through the gateway's
  internal `/__internal__/users/:id/calendar-token` endpoint, which itself
  reads the `account` row via `pg.Pool` (no new column).
- Token refresh is implemented by calling `auth.api.refreshToken(...)` from
  the gateway internal endpoint when the access token has expired.
- If a future Better Auth release removes the `scopes` parameter from
  `linkSocialAccount`, this ADR will be superseded by a fork-or-handroll
  ADR.

## Alternatives considered

- **Hand-rolled OAuth callback** — explicitly considered as a fallback in
  the slice design. Not adopted because the native API works; revisit only
  if Better Auth removes the `scopes` body field.
- **Extending login OAuth scope** — rejected at design time. Login flow
  already shipped without Calendar; existing users would need to log out and
  back in to gain the new scope, and they would face a wider Google consent
  prompt at login time even if they never use Calendar.
