# calendar-integration Specification

## Purpose

TBD - created by archiving change 'slice-05-calendar-llm-playbook'. Update Purpose after archive.

## Requirements

### Requirement: Calendar OAuth scope is granted via a separate connect flow

The application SHALL provide a Calendar connection flow that is distinct from the login OAuth flow. The flow MUST request the `https://www.googleapis.com/auth/calendar.events.readonly` scope, MUST NOT alter the existing login OAuth scopes for users who already authenticated, and MUST persist the resulting access token, refresh token, and expiry per user. The connection state SHALL be readable via a status check that returns whether Calendar is connected for the current user.

#### Scenario: Connecting Calendar leaves login behavior unchanged

- **GIVEN** user A has already logged in with Google using only the standard login scopes
- **WHEN** user A initiates the Calendar connection flow and grants the calendar.events.readonly scope
- **THEN** user A's existing session SHALL remain valid, and a subsequent connection-status check for user A SHALL report `connected: true`

#### Scenario: A user without Calendar connection is reported as not connected

- **WHEN** user B sends `GET /api/auth/calendar/status` and has never granted Calendar scope
- **THEN** the response SHALL contain `connected: false`


<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->

---
### Requirement: GET upcoming events returns the user's events ordered by start time

The endpoint `GET /api/calendar/upcoming` SHALL return Calendar events that start within the supplied `hours` window (default 24, minimum 1, maximum 168) for the authenticated user, ordered by start time ascending. Each returned event SHALL include the event id, title, start and end timestamps, attendee count, optional description, and the organizer display name. The endpoint MUST handle Google Calendar API pagination internally; the client MUST receive the complete list as a single array.

#### Scenario: Returns ordered events from a multi-page Google response

- **GIVEN** user A has Calendar connected and the underlying Google Calendar API returns two pages of events totalling four events
- **WHEN** user A sends `GET /api/calendar/upcoming?hours=24`
- **THEN** the response SHALL be HTTP 200 with a JSON array of length 4, ordered by `start` ascending

#### Scenario: Returns an empty array when the user has no upcoming events

- **GIVEN** user A has Calendar connected but no events in the next 24 hours
- **WHEN** user A sends `GET /api/calendar/upcoming?hours=24`
- **THEN** the response status SHALL be HTTP 200 and the body SHALL be an empty JSON array


<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->

---
### Requirement: Calendar failure modes surface localizable error codes

When a Calendar request cannot succeed, the backend SHALL respond with the standard error envelope `{error_code, message}` carrying one of the following codes, each of which the frontend resolves via the i18n key registry:

- `calendar.not_connected` — the user has no Calendar scope token, or the token has been revoked at Google. HTTP 401.
- `calendar.token_expired` — the access token expired and the refresh attempt failed. HTTP 401.
- `calendar.network_error` — the upstream Google Calendar API call failed due to a transport error or persistent 5xx response. HTTP 502.

These error codes SHALL be the only Calendar-domain error codes emitted by the calendar router; future additions require a separate change.

#### Scenario: Listing without Calendar scope returns calendar.not_connected

- **GIVEN** user A has not granted Calendar scope
- **WHEN** user A sends `GET /api/calendar/upcoming`
- **THEN** the response status SHALL be HTTP 401 and the body's `error_code` SHALL be `calendar.not_connected`

#### Scenario: Refresh token rejection returns calendar.token_expired

- **GIVEN** user A's stored access token is expired and the refresh attempt against Google returns HTTP 400 invalid_grant
- **WHEN** user A sends `GET /api/calendar/upcoming`
- **THEN** the response status SHALL be HTTP 401 and the body's `error_code` SHALL be `calendar.token_expired`

#### Scenario: Persistent upstream 5xx returns calendar.network_error

- **GIVEN** the Google Calendar API returns HTTP 503 on every retry
- **WHEN** user A sends `GET /api/calendar/upcoming`
- **THEN** the response status SHALL be HTTP 502 and the body's `error_code` SHALL be `calendar.network_error`


<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->

---
### Requirement: POST from-calendar creates a meeting and persists a generated playbook draft

The endpoint `POST /api/meetings/from-calendar` SHALL accept a JSON body `{event_id: string}` and, for the authenticated user, perform the following sequence: (1) fetch the event details from the user's Calendar, (2) create a meeting via the existing meeting repository with `title` set to the event title and `calendar_event_id` set to the event id, (3) invoke the playbook generation capability to produce a draft from the event metadata, (4) persist the draft via the existing playbook repository, (5) return `{meeting_id: string}`. The meeting MUST belong to the authenticated user. If the playbook generation step fails, the meeting row MUST remain in the database (it is recoverable through the manual editor) and the response SHALL surface the corresponding playbook generation error code.

#### Scenario: Successful import creates meeting linked to the calendar event

- **GIVEN** user A has Calendar connected and a Calendar event `gcal_evt_42` with title "Q3 review" exists in their calendar
- **WHEN** user A sends `POST /api/meetings/from-calendar` with body `{"event_id": "gcal_evt_42"}`
- **THEN** the response status SHALL be HTTP 201, a new meeting SHALL exist with `title = "Q3 review"` and `calendar_event_id = "gcal_evt_42"` owned by user A, and a playbook for that meeting SHALL exist with all seven content fields populated by the generator

#### Scenario: Generator failure leaves the meeting persisted but no playbook content overwrite

- **GIVEN** the Calendar event fetch succeeds but the playbook generator raises a timeout
- **WHEN** user A sends `POST /api/meetings/from-calendar`
- **THEN** the meeting SHALL exist in the database with `calendar_event_id` populated, the response SHALL be a 504-class envelope with `error_code: playbook.generation_timeout`, and the playbook for that meeting MUST NOT contain partial generator output (the slice-04 auto-create empty playbook remains acceptable)

#### Scenario: Importing another user's event identifier returns calendar.not_connected or 404 without leaking existence

- **GIVEN** user B has a Calendar event `gcal_evt_b` and user A has Calendar connected but no such event
- **WHEN** user A sends `POST /api/meetings/from-calendar` with body `{"event_id": "gcal_evt_b"}`
- **THEN** the response SHALL surface a Calendar-domain error code; the response body MUST NOT reveal that the event exists in any other user's calendar

<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->