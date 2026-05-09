# Calendar — agent notes

> Slice 5 (`slice-05-calendar-llm-playbook`) outcome.
> Spec: `openspec/specs/calendar-integration/spec.md` (after archive).
> ADR-0027: Calendar scope grant via Better Auth `linkSocialAccount`.

## End-to-end flow

```
Browser
  └─ /calendar  Upcoming events page
       │ (a) UpcomingEvents component fetches GET /api/calendar/upcoming
       │ (b) "Connect Google Calendar" CTA when 401 + calendar.not_connected
       │ (c) "Import + generate" → POST /api/meetings/from-calendar
       ▼
Bun gateway (sole ingress)
  ├─ /api/auth/calendar/link    → wraps Better Auth linkSocialAccount with calendar.events.readonly
  ├─ /api/auth/calendar/status  → wraps Better Auth listUserAccounts to check the scope
  └─ /api/calendar/* + /api/meetings/from-calendar → proxied to FastAPI with X-User-Id
       │
       ▼
FastAPI
  ├─ CalendarClient — wraps Google Calendar API via TokenStore
  └─ POST /api/meetings/from-calendar:
       events.get → MeetingRepository.create → PlaybookGenerator.generate → PlaybookRepository.upsert_for_meeting
       │
       ▼
Bun gateway internal endpoints (X-Internal-Auth required, 127.0.0.1 only)
  ├─ GET  /__internal__/users/:id/calendar-token
  └─ POST /__internal__/users/:id/refresh-calendar-token
       │
       ▼
PostgreSQL
  ├─ Better Auth account row (accessToken / refreshToken / scope)
  ├─ meeting (with calendar_event_id populated)
  └─ playbook (LLM-generated draft)
```

## Connect-Calendar contract

The login OAuth (Slice 1) only requested `openid email profile`. Calendar
scope is broader, so it lives in a separate flow:

- `POST /api/auth/calendar/link` — initiates the OAuth grant. Body
  `{callbackURL: "/calendar"}` is optional. Returns
  `{url, redirect}` — when `url` is set the frontend redirects the
  browser there to complete consent.
- `GET /api/auth/calendar/status` — reads the user's account row and
  returns `{connected: bool}` based on whether the Google account row
  carries the calendar scope.

Per ADR-0027 we use Better Auth's native `linkSocialAccount` for both;
no custom OAuth callback was needed.

## TokenStore invariant

The Better Auth `account` table is the **single source of truth** for
Google OAuth tokens. Python NEVER reads or writes that table directly;
instead, `TokenStore` (Python) calls the gateway's
`/__internal__/users/:id/calendar-token` and
`/__internal__/users/:id/refresh-calendar-token` endpoints with the
`X-Internal-Auth` shared secret.

Concretely: any new Python code that needs a Calendar access token MUST
go through `meeting_playbook.calendar.token_store.TokenStore`. Direct
queries against `account` from Python are a review block — they bypass
the refresh-on-expiry path that lives in the gateway.

## CalendarClient invariant

`meeting_playbook.calendar.client.CalendarClient` is the **only** access
path for Google Calendar API calls in this codebase. It exposes:

- `get_upcoming_events(user_id, hours=24) -> list[CalendarEvent]`
- `get_event(user_id, event_id) -> CalendarEvent`

Failure modes are typed:

- `CalendarNotConnected` → router maps to HTTP 401 + `calendar.not_connected`
- `CalendarTokenExpired` → router maps to HTTP 401 + `calendar.token_expired`
- `CalendarNetworkError` → router maps to HTTP 502 + `calendar.network_error`

The client follows pagination automatically; callers receive the full
list as a single array.

## Out of scope (until later slices)

- Calendar providers other than Google
- Two-way sync (writing back to Calendar)
- Webhooks / push notifications (user pulls)
- Recurring-series deduplication
- Caching across requests
- Background scheduled imports (cron)

## Display-name derivation (slice-05 ingest 2026-05-09)

When `POST /api/meetings/from-calendar` creates a meeting from a Calendar
event, the two display-name fields are derived from session identity, not
hardcoded fallbacks:

- `me_display_name` is taken from the gateway-injected `X-User-Name`
  header. If that header is empty (Better Auth user.name was empty), the
  endpoint falls back to the `X-User-Email` local-part, then finally to
  the literal `"Me"`. The literal MUST NOT appear when either header
  carries a value.
- `counterparty_display_name` is picked by
  `meeting_playbook.calendar.identity.pick_counterparty(event, user_email)`:
  - First attendee whose email is NOT the authenticated user's email
    (case-insensitive, whitespace-trimmed). The display string is the
    parsed `displayName`, falling back to the email's local-part.
  - If no other-party attendee exists: event organizer.
  - If no organizer: event title.
  - Last resort: the literal `"Calendar event"`.

The Bun gateway always sets `X-User-Id`, `X-User-Name`, and
`X-User-Email` together on every authenticated non-public `/api/*`
request. Public routes (`/api/health`) get none of them. Backend code
MUST trust these headers — they cannot be spoofed by clients because the
gateway overwrites any client-supplied values before forwarding.

Add new business endpoints by reusing
`meeting_playbook.meetings.dependencies.{get_user_id_dependency,
get_user_name_dependency, get_user_email_dependency}`.

## Limitation: Google identity required

The Calendar connect flow (`POST /api/auth/calendar/link`) wraps Better
Auth's `linkSocialAccount` against the `google` provider. Practical
consequences:

- Any user who connects Calendar — including users who originally signed
  up with email + password — ends up with a Google identity linked on
  their account. From that point on they may also sign in with Google.
- Users without a Google account cannot use Calendar in this slice.
  Microsoft Calendar / iCal would require a new provider-selection UI
  plus token-store fan-out and is explicitly out of scope (see slice-05
  design "Out of scope: non-Google identity providers for Calendar").

This limitation is intentional for the MVP. Tracking it here so future
agents do not propose a per-user "I don't want Google linked" toggle
without re-opening the design conversation.
