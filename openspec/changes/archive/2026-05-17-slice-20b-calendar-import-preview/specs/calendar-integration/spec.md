## ADDED Requirements

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

## REMOVED Requirements

### Requirement: POST from-calendar creates a meeting and persists a generated playbook draft

**Reason**: The fire-and-forget `POST /api/meetings/from-calendar` is replaced by a preview-and-confirm flow. The user now navigates to `/meetings/new?from_calendar=<event_id>`, edits the pre-filled form, optionally attaches files, and explicitly confirms; meeting creation plus Playbook generation are then triggered through `POST /api/meetings` carrying `calendar_event_id` and `attachments[]`. Removing the endpoint guarantees that no Playbook generation can fire before the user has had a chance to attach files or correct counterparty / me display names.

**Migration**: The endpoint MUST return HTTP 410 Gone with body `{error_code: "calendar.import_endpoint_removed", message: ...}`. Front-end clients SHALL navigate the user to `/meetings/new?from_calendar=<event_id>` and submit via `POST /api/meetings`. The replacement contract for "create a meeting plus generate a playbook from a Calendar event" is recorded in the `meeting-management` and `playbook-generation` capability specs.

#### Scenario: Legacy endpoint MUST NOT create a meeting after this change

- **WHEN** any authenticated client sends `POST /api/meetings/from-calendar` with body `{"event_id": "gcal_evt_42"}`
- **THEN** the response SHALL be HTTP 410 with `error_code: calendar.import_endpoint_removed`, no meeting row SHALL be created, and the Playbook generation capability MUST NOT be invoked as a side effect of this request
