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

The endpoint `POST /api/meetings/from-calendar` SHALL accept a JSON body `{event_id: string}` and, for the authenticated user, perform the following sequence: (1) fetch the event details from the user's Calendar, (2) create a meeting via the existing meeting repository with `title` set to the event title, `calendar_event_id` set to the event id, `scheduled_start_at` set to the Calendar event's start datetime (timezone-aware), and `scheduled_end_at` set to the Calendar event's end datetime (timezone-aware), (3) invoke the playbook generation capability to produce a draft from the event metadata, (4) persist the draft via the existing playbook repository, (5) return `{meeting_id: string}`. The meeting MUST belong to the authenticated user. If the playbook generation step fails, the meeting row MUST remain in the database (it is recoverable through the manual editor) and the response SHALL surface the corresponding playbook generation error code; the schedule timestamps SHALL remain populated regardless of generator outcome.

When the Calendar event has no end time (rare; the Google Calendar API may omit `end.dateTime` for all-day events), `scheduled_end_at` SHALL be persisted as `NULL`. When the event has no start time, the meeting SHALL still be created with `scheduled_start_at = NULL`.

#### Scenario: Successful import creates meeting linked to the calendar event with schedule populated

- **GIVEN** user A has Calendar connected and a Calendar event `gcal_evt_42` with title "Q3 review", start `2026-06-15T14:00:00Z`, and end `2026-06-15T15:00:00Z` exists in their calendar
- **WHEN** user A sends `POST /api/meetings/from-calendar` with body `{"event_id": "gcal_evt_42"}`
- **THEN** the response status SHALL be HTTP 201, a new meeting SHALL exist with `title = "Q3 review"`, `calendar_event_id = "gcal_evt_42"`, `scheduled_start_at = 2026-06-15T14:00:00+00:00`, and `scheduled_end_at = 2026-06-15T15:00:00+00:00` owned by user A, and a playbook for that meeting SHALL exist with all seven content fields populated by the generator

#### Scenario: Generator failure leaves the meeting persisted with schedule fields still populated

- **GIVEN** the Calendar event fetch succeeds (event has start and end) but the playbook generator raises a timeout
- **WHEN** user A sends `POST /api/meetings/from-calendar`
- **THEN** the meeting SHALL exist in the database with `calendar_event_id`, `scheduled_start_at`, and `scheduled_end_at` all populated; the response SHALL be a 504-class envelope with `error_code: playbook.generation_timeout`; the playbook for that meeting MUST NOT contain partial generator output (the slice-04 auto-create empty playbook remains acceptable)

#### Scenario: Importing another user's event identifier returns calendar.not_connected or 404 without leaking existence

- **GIVEN** user B has a Calendar event `gcal_evt_b` and user A has Calendar connected but no such event
- **WHEN** user A sends `POST /api/meetings/from-calendar` with body `{"event_id": "gcal_evt_b"}`
- **THEN** the response SHALL surface a Calendar-domain error code; the response body MUST NOT reveal that the event exists in any other user's calendar

#### Scenario: All-day event without end time persists scheduled_end_at as null

- **GIVEN** a Calendar event has `start.dateTime = 2026-07-01T09:00:00Z` but no `end.dateTime`
- **WHEN** the import succeeds
- **THEN** the resulting meeting SHALL have `scheduled_start_at = 2026-07-01T09:00:00+00:00` and `scheduled_end_at = NULL`


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Calendar event resource attendees are excluded from counterparty derivation

When the import endpoint fetches a Google Calendar event, the `attendees` list returned by the Google Calendar API may contain BOTH human attendees AND resource accounts (meeting rooms, equipment) marked with `resource: true`, `resourceEmail`, or an email ending with `@resource.calendar.google.com`. The implementation SHALL filter these resource entries out of the `CalendarEvent.attendees` list BEFORE `pick_counterparty` iterates over it. As a result, a meeting room name (e.g. `"MCTW - 6/F-6-龍貓 (3)"`) MUST NOT be selected as `counterparty_display_name`.

The filter SHALL apply at the parsing boundary (`_event_from_resource` in `packages/backend/meeting_playbook/calendar/client.py`) so all downstream consumers (counterparty picker, viewer-role classifier, prompt formatter) see only human attendees. Room information SHALL NOT be promoted to any other meeting field by this slice — slice-7 simply drops it from counterparty candidates.

#### Scenario: Room attendee is filtered out so counterparty picks the human

- **GIVEN** a Calendar event with attendees `[{email: "sean@example.com", displayName: "Sean", resource: false}, {email: "c_xx@resource.calendar.google.com", displayName: "MCTW - 6/F-6-龍貓 (3)", resource: true}, {email: "lin@example.com", displayName: "林經理"}]` and the viewer is `sean@example.com`
- **WHEN** the import endpoint runs
- **THEN** the resulting meeting's `counterparty_display_name` SHALL equal `"林經理"` (the only non-viewer human), and SHALL NOT contain `"龍貓"` anywhere

#### Scenario: Resource detected via email suffix when resource flag is missing

- **GIVEN** an attendee `{email: "c_abc@resource.calendar.google.com", displayName: "Some Room"}` (no explicit `resource: true` field)
- **WHEN** `_event_from_resource` parses the event
- **THEN** that attendee SHALL be excluded from `event.attendees`

#### Scenario: All-human event preserves the existing pick order

- **GIVEN** a Calendar event with two human attendees and zero resource attendees
- **WHEN** the import endpoint runs
- **THEN** the resource-filter SHALL be a no-op and `pick_counterparty` SHALL return the same value as it did before slice-7 round 2

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->


<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->

---
### Requirement: Calendar import lives at /calendar/import to disambiguate from the meetings calendar view

The web client SHALL register the upcoming-events / one-click-import wizard at the URL path `/calendar/import` (NOT `/calendar`). The page MUST remain reachable through that path; the previously used `/calendar` URL is no longer registered. All internal links from other routes (home, meetings list, navigation) that previously pointed to `/calendar` SHALL be updated to point to `/calendar/import`. The page's component, business logic, and i18n keys (`calendar.heading`, `calendar.empty`, etc.) are unchanged — only the URL path moves.

#### Scenario: /calendar/import renders the import wizard

- **WHEN** an authenticated user navigates to `/calendar/import`
- **THEN** the page SHALL render the upcoming-events list (or the connect-Calendar prompt if not connected), behaving as the previous `/calendar` URL did

#### Scenario: Internal navigation uses the new path

- **GIVEN** the home page renders a link historically labeled "Open Calendar import"
- **WHEN** the page renders
- **THEN** the link's `to` attribute SHALL equal `"/calendar/import"` (not `"/calendar"`)

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
-->

<!-- @trace
source: slice-07-dualstream-and-ui-bundle
updated: 2026-05-10
code:
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/web/src/components/layout-switcher.tsx
  - packages/backend/meeting_playbook/sessions/service.py
  - docs/agents/audio.md
  - packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py
  - packages/backend/meeting_playbook/asr/base.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/audio/devices.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/package.json
  - .env.example
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/audio/capture.py
  - docs/BLACKHOLE_SETUP.md
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/index.css
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/calendar/client.py
  - bun.lock
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/components/headphones-hint.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/hooks/use-detail-layout.ts
  - packages/web/src/test-setup.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/markdown-preview.tsx
  - packages/web/vite.config.ts
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/routes/calendar/upcoming.tsx
tests:
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/backend/tests/asr/fixtures/counterparty_short.wav
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/backend/tests/audio/test_devices.py
  - packages/web/src/components/headphones-hint.test.tsx
  - packages/backend/tests/asr/fixtures/README.md
  - packages/backend/tests/sessions/test_repository.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_preflight.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/web/src/hooks/use-detail-layout.test.tsx
  - packages/web/src/lib/markdown-preview.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
-->