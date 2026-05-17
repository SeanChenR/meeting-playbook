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

The web client SHALL render the Google Calendar connection-status UI (connect button when disconnected, upcoming-events list when connected, one-click-import wizard) at the URL path `/settings/integrations`, nested inside the settings shell. The previously registered route `/calendar/import` MUST remain reachable as a redirect-only route: visiting `/calendar/import` SHALL redirect to `/settings/integrations` via `beforeLoad` so no intermediate page renders. The page's calendar-related business logic and i18n keys (`calendar.heading`, `calendar.empty`, etc.) MUST NOT change; only the canonical URL moves and the legacy URL becomes a redirect. All internal links in the web client that previously pointed to `/calendar/import` SHALL be updated to point to `/settings/integrations`.

#### Scenario: /settings/integrations renders the connection panel

- **WHEN** an authenticated user navigates to `/settings/integrations`
- **THEN** the page SHALL render the upcoming-events list (or the connect-Calendar prompt if not connected), behaving as the previous `/calendar/import` URL did, AND the page SHALL be wrapped in the settings sub-nav shell

#### Scenario: /calendar/import redirects to /settings/integrations

- **WHEN** an authenticated user navigates to `/calendar/import`
- **THEN** the browser SHALL be redirected to `/settings/integrations` AND the redirect MUST happen in `beforeLoad` so the legacy URL never renders a calendar UI of its own

#### Scenario: Internal navigation uses the new path

- **GIVEN** any internal link in the web client (home, navbar, meetings list, user menu) that previously had `to="/calendar/import"`
- **WHEN** the link is rendered after this change
- **THEN** the link's `to` attribute SHALL equal `"/settings/integrations"` (not `"/calendar/import"`)

<!-- @trace
source: slice-19-settings-sub-nav
updated: 2026-05-17
code:
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/routes/settings/profile.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/chunk-action-menu.tsx
  - bun.lock
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/src/routes/settings/integrations.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/web/src/route-tree.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/backend/meeting_playbook/tags/models.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/public/icons/whisper.png
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/routes/settings/security.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - CONTEXT.md
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/web/public/icons/google-calendar.png
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/web/src/components/settings/layout.tsx
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/lib/stats-api.ts
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/web/public/icons/google-authenticator.png
  - .env.example
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/uv.lock
  - packages/web/src/routes/settings/preferences.tsx
  - packages/backend/meeting_playbook/retention/job.py
  - packages/web/src/components/settings/all-sections.tsx
  - packages/web/src/components/ui/dialog.tsx
  - packages/backend/meeting_playbook/tags/__init__.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/tags/repository.py
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - packages/web/package.json
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/web/src/index.css
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/public/icons/qwen.png
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/ui/alert.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/auth/src/server.ts
  - README.md
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/web/src/lib/session-ws.ts
tests:
  - packages/backend/tests/tags/test_models.py
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/tags/test_router.py
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/conftest.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/web/src/lib/tag-palette.test.ts
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/test_config.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/App.test.tsx
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/attachments/test_validation.py
-->

---
### Requirement: GET single Calendar event returns the full detail used by the meeting preview form

The endpoint `GET /api/calendar/events/{event_id}` SHALL return a single Google Calendar event detail for the authenticated user. The response body SHALL include `id`, `title`, `start` (ISO 8601 timestamp or `null` for all-day events without a `dateTime`), `end` (ISO 8601 timestamp or `null`), optional `description`, optional `organizer` (display name + email or `null`), and an `attendees` array. The `attendees` array MUST be filtered through the same resource-attendee filter applied by `/upcoming` and `POST /api/meetings/from-calendar` (per the existing `_event_from_resource` rule): resource accounts identified by `resource: true`, `resourceEmail`, or an email suffix `@resource.calendar.google.com` MUST NOT appear in the response.

Calendar-domain error codes from the existing capability SHALL be reused for the upstream / token failure modes (`calendar.not_connected` HTTP 401, `calendar.token_expired` HTTP 401, `calendar.network_error` HTTP 502). The endpoint SHALL additionally emit `calendar.event_not_found` HTTP 404 when the requested `event_id` does not exist under the authenticated user's calendar; the response MUST NOT distinguish between "event does not exist" and "event exists under another user's calendar" beyond the single 404 code, to avoid leaking event existence across users.

#### Scenario: Returns the event detail with resource attendees filtered out

- **GIVEN** an authenticated user with Calendar connected and a Calendar event `gcal_evt_42` with title `"Q3 review"`, two human attendees, one resource attendee `c_room@resource.calendar.google.com`, and a description
- **WHEN** the user sends `GET /api/calendar/events/gcal_evt_42`
- **THEN** the response SHALL be HTTP 200 with body `id="gcal_evt_42"`, `title="Q3 review"`, the description populated, and `attendees` containing exactly the two human entries (the resource attendee MUST NOT appear)

#### Scenario: Unknown event identifier returns calendar.event_not_found

- **GIVEN** an authenticated user with Calendar connected and no event with id `gcal_missing` in their calendar
- **WHEN** the user sends `GET /api/calendar/events/gcal_missing`
- **THEN** the response SHALL be HTTP 404 and the body's `error_code` SHALL equal `calendar.event_not_found`

#### Scenario: Calendar not connected returns calendar.not_connected

- **GIVEN** an authenticated user who has never granted Calendar scope
- **WHEN** the user sends `GET /api/calendar/events/any_id`
- **THEN** the response SHALL be HTTP 401 and the body's `error_code` SHALL equal `calendar.not_connected`

<!-- @trace
source: slice-20b-calendar-import-preview
updated: 2026-05-17
code:
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/components/settings/layout.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/pyproject.toml
  - packages/auth/src/server.ts
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/web/src/route-tree.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/backend/meeting_playbook/retention/job.py
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - docs/adr/0027-calendar-scope-link.md
  - bun.lock
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/components/metadata-card.tsx
  - CONTEXT.md
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/backend/meeting_playbook/tags/__init__.py
  - packages/web/src/index.css
  - packages/web/src/locales/en.json
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/hooks/use-mini-player.ts
  - packages/web/src/lib/stats-api.ts
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/tags/repository.py
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/src/components/ui/dialog.tsx
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - .env.example
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/settings/all-sections.tsx
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/public/icons/google-calendar.png
  - packages/web/src/routes/settings/preferences.tsx
  - packages/web/src/routes/settings/profile.tsx
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/lib/calendar-api.ts
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/routes/settings/tags.tsx
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/tags-api.ts
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/web/public/icons/qwen.png
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - packages/backend/meeting_playbook/tags/models.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/lib/tag-palette.ts
  - README.md
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/web/public/icons/google-authenticator.png
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/routes/settings/integrations.tsx
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/sessions/repository.py
tests:
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/attachments/__init__.py
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/backend/tests/audio_playback/__init__.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/test_config.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/lib/tags-api.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/backend/tests/tags/test_router.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/backend/tests/attachments/test_processor.py
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/backend/tests/conftest.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/web/src/App.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/web/src/lib/stats-api.test.ts
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/rerun/test_runtime.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/backend/tests/tags/test_models.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/calendar/test_get_event_endpoint.py
-->