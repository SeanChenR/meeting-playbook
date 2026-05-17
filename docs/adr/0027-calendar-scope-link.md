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

## Amended by slice-20b

- **Date**: 2026-05-15
- **Scope of amendment**: import-flow shape only — the OAuth `linkSocial`
  scope-grant decision above is unchanged.

### What changed

The original ADR shipped with `POST /api/meetings/from-calendar` as the
fire-and-forget import surface: one request fetched the event, created the
meeting, and ran the Playbook generator. Slice-20b introduces an
attachment capability (S20a) whose value depends on the user attaching
files *before* the generator runs. The fire-and-forget shape leaves no
room for that, and also leaves no room to fix the multi-attendee
counterparty-picker gap (slice-05 had no way to ask the user "which of
these is the counterparty?" mid-import).

S20b therefore splits the flow into two surfaces:

1. **Navigation**: clicking "匯入" on `/calendar/import` navigates the
   browser to `/meetings/new?from_calendar=<event_id>`. No `POST` fires
   on the click; the calendar-domain side is read-only at this stage.
2. **Single-event detail**: the preview form fetches `GET /api/calendar/events/{event_id}`
   (new endpoint added by S20b) to pre-fill `title`, schedule, counterparty
   display name, and me display name. Errors surface inline so the user
   can still submit a manual create if the calendar fetch fails.
3. **Meeting create + Playbook generate**: when the user confirms,
   `POST /api/meetings` is called with `calendar_event_id` and the
   selected `attachments[]`. The backend runs the same `CalendarClient.get_event`
   + `PlaybookGenerator` + `PlaybookRepository.upsert_for_meeting` chain
   the legacy endpoint used, but only AFTER the user has had a chance to
   stage attachments and correct display names.

The legacy `POST /api/meetings/from-calendar` endpoint is retained only
to emit HTTP 410 Gone with `error_code: calendar.import_endpoint_removed`
so stale frontend caches get a clear signal to reload.

### What did NOT change

- OAuth scope grant via Better Auth `linkSocial` — unchanged.
- The `account` row layout, the gateway internal token endpoint, and the
  token refresh mechanic — unchanged.
- Calendar-domain error codes (`calendar.not_connected`,
  `calendar.token_expired`, `calendar.network_error`) — unchanged; S20b
  adds one new code (`calendar.event_not_found`) for the typed 404 on
  the single-event endpoint.

### Why an amendment, not a new ADR

ADR-0027's subject is "how does the user grant the Calendar OAuth scope".
S20b changes what happens AFTER the scope is granted, but does not touch
the grant mechanism itself. Splitting into two ADRs would force future
readers to follow a cross-reference for no semantic gain; the amendment
keeps the import-flow narrative co-located with its OAuth dependency.
