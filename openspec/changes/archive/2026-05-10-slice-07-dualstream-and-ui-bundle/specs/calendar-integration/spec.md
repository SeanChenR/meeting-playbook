## ADDED Requirements

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

### Requirement: Calendar import lives at /calendar/import to disambiguate from the meetings calendar view

The web client SHALL register the upcoming-events / one-click-import wizard at the URL path `/calendar/import` (NOT `/calendar`). The page MUST remain reachable through that path; the previously used `/calendar` URL is no longer registered. All internal links from other routes (home, meetings list, navigation) that previously pointed to `/calendar` SHALL be updated to point to `/calendar/import`. The page's component, business logic, and i18n keys (`calendar.heading`, `calendar.empty`, etc.) are unchanged — only the URL path moves.

#### Scenario: /calendar/import renders the import wizard

- **WHEN** an authenticated user navigates to `/calendar/import`
- **THEN** the page SHALL render the upcoming-events list (or the connect-Calendar prompt if not connected), behaving as the previous `/calendar` URL did

#### Scenario: Internal navigation uses the new path

- **GIVEN** the home page renders a link historically labeled "Open Calendar import"
- **WHEN** the page renders
- **THEN** the link's `to` attribute SHALL equal `"/calendar/import"` (not `"/calendar"`)

## MODIFIED Requirements

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
