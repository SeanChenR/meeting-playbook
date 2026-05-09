## ADDED Requirements

### Requirement: Calendar OAuth scope is granted via a separate connect flow

The application SHALL provide a Calendar connection flow that is distinct from the login OAuth flow. The flow MUST request the `https://www.googleapis.com/auth/calendar.events.readonly` scope, MUST NOT alter the existing login OAuth scopes for users who already authenticated, and MUST persist the resulting access token, refresh token, and expiry per user. The connection state SHALL be readable via a status check that returns whether Calendar is connected for the current user.

#### Scenario: Connecting Calendar leaves login behavior unchanged

- **GIVEN** user A has already logged in with Google using only the standard login scopes
- **WHEN** user A initiates the Calendar connection flow and grants the calendar.events.readonly scope
- **THEN** user A's existing session SHALL remain valid, and a subsequent connection-status check for user A SHALL report `connected: true`

#### Scenario: A user without Calendar connection is reported as not connected

- **WHEN** user B sends `GET /api/auth/calendar/status` and has never granted Calendar scope
- **THEN** the response SHALL contain `connected: false`

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

## ADDED Requirements (post-smoke ingest 2026-05-09)

### Requirement: POST from-calendar derives display names from session identity and attendee filtering

The endpoint `POST /api/meetings/from-calendar` SHALL populate the new meeting's display-name fields from session identity instead of hardcoded fallbacks. Specifically:

- `me_display_name` SHALL be the authenticated user's name as carried by the gateway in the `X-User-Name` header. If that header is absent, the value SHALL fall back to the local-part (the substring before `@`) of the `X-User-Email` header. The literal string `"Me"` MUST NOT be used unless both headers are absent.
- `counterparty_display_name` SHALL be derived from the event's attendees by selecting the first attendee whose email is NOT the authenticated user's email (case-insensitive comparison after trimming whitespace). Each attendee MUST be normalized as `displayName OR email-local-part`. If no other-party attendee exists, the value SHALL fall back in this order: (1) the event organizer's display name or email, (2) the event title, (3) the literal string `"Calendar event"`.

The Bun gateway SHALL set `X-User-Name` and `X-User-Email` on every authenticated non-public `/api/*` request, overwriting any client-supplied values, alongside the existing `X-User-Id` header.

#### Scenario: Importing a multi-attendee event picks the other attendee as counterparty

- **GIVEN** the authenticated user's email is `angus@example.com` and a Calendar event has attendees `["angus@example.com", "Lin Manager <lin@acme.com>"]`
- **WHEN** the user sends `POST /api/meetings/from-calendar` for that event
- **THEN** the resulting meeting's `counterparty_display_name` SHALL be `"Lin Manager"` (or `"lin"` if no displayName was provided), and MUST NOT be `angus@example.com`

#### Scenario: Importing a self-organized event with no other attendees falls back through organizer → title

- **GIVEN** a Calendar event whose only attendee is the authenticated user, organizer is `"Sean"`, and title is `"Solo prep"`
- **WHEN** the user imports that event
- **THEN** the resulting meeting's `counterparty_display_name` SHALL be `"Sean"`. If the organizer is also empty, it SHALL be `"Solo prep"`. The literal `"Calendar event"` SHALL be used only when all three (other-attendee, organizer, title) are empty.

#### Scenario: me_display_name is taken from X-User-Name not the literal "Me"

- **GIVEN** the gateway sets `X-User-Name: "Sean Chen"` for the authenticated user
- **WHEN** any Calendar import creates a meeting for that user
- **THEN** the meeting's `me_display_name` SHALL be `"Sean Chen"` (NOT the literal `"Me"`)

#### Scenario: Gateway always injects user-name and user-email on authenticated non-public traffic

- **GIVEN** an authenticated request to any non-public `/api/*` path
- **WHEN** the gateway proxies the request to the backend
- **THEN** the proxied request SHALL carry `X-User-Id`, `X-User-Name`, and `X-User-Email` headers, each set from the active Better Auth session, and any client-supplied values for those headers MUST be discarded
