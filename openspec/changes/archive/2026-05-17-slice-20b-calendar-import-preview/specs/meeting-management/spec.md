## MODIFIED Requirements

### Requirement: Meeting carries an optional Calendar event reference

A meeting record SHALL have a nullable `calendar_event_id` text column. The `POST /api/meetings` endpoint SHALL accept an optional `calendar_event_id` field in the request body: when present and non-null, the field MUST be persisted onto the meeting row and additionally MUST cause Playbook generation to be triggered for that meeting (per the `playbook-generation` capability contract); when omitted or `null`, the meeting row SHALL be persisted with `calendar_event_id = null` and Playbook generation MUST NOT be invoked (the slice-04 auto-create empty playbook path remains in effect for manual creation).

#### Scenario: New manual meeting has null calendar_event_id

- **WHEN** an authenticated user sends `POST /api/meetings` with a valid body and `calendar_event_id` omitted
- **THEN** the persisted meeting SHALL have `calendar_event_id` equal to `null`

#### Scenario: Create with calendar_event_id persists the reference

- **WHEN** an authenticated user sends `POST /api/meetings` with body containing `calendar_event_id: "gcal_evt_42"` plus the three required free-text fields
- **THEN** the response SHALL be HTTP 201 and the persisted meeting SHALL have `calendar_event_id = "gcal_evt_42"`

## ADDED Requirements

### Requirement: POST /api/meetings accepts an attachments list that associates pre-uploaded attachments with the new meeting

The endpoint `POST /api/meetings` SHALL accept an optional `attachments` field in the request body containing a JSON array of attachment identifier strings. Each identifier MUST reference an attachment row previously uploaded through the attachment capability (slice-20a) that is owned by the authenticated user AND has `meeting_id IS NULL` (i.e., not yet associated with any meeting). The endpoint SHALL validate every identifier against these two conditions BEFORE creating the meeting row; if any identifier fails validation the endpoint MUST NOT create the meeting and MUST return HTTP 422 with `error_code: attachment.not_attachable`. When all identifiers pass validation, the endpoint SHALL create the meeting row first, then update each referenced attachment row's `meeting_id` to the new meeting's id, all within a single database transaction.

#### Scenario: Successful create attaches all supplied attachments to the new meeting

- **GIVEN** an authenticated user owns two pending attachments `att_1` and `att_2`, each with `meeting_id = null`
- **WHEN** the user sends `POST /api/meetings` with body containing `attachments: ["att_1", "att_2"]` plus the three required free-text fields
- **THEN** the response SHALL be HTTP 201 and after the request both `att_1` and `att_2` rows SHALL have `meeting_id` equal to the new meeting's id

#### Scenario: Attachment owned by another user is rejected with attachment.not_attachable

- **GIVEN** user A is authenticated and an attachment `att_other` is owned by user B with `meeting_id = null`
- **WHEN** user A sends `POST /api/meetings` with body containing `attachments: ["att_other"]`
- **THEN** the response SHALL be HTTP 422 with `error_code: attachment.not_attachable`, no meeting SHALL have been created, and `att_other` SHALL remain unchanged

#### Scenario: Already-attached attachment is rejected with attachment.not_attachable

- **GIVEN** an authenticated user owns an attachment `att_taken` whose `meeting_id` is already set to a previous meeting
- **WHEN** the user sends `POST /api/meetings` with body containing `attachments: ["att_taken"]`
- **THEN** the response SHALL be HTTP 422 with `error_code: attachment.not_attachable` and no new meeting SHALL have been created

#### Scenario: Empty or omitted attachments list creates a meeting with no attachments

- **WHEN** an authenticated user sends `POST /api/meetings` with `attachments` omitted (or set to `[]`)
- **THEN** the response SHALL be HTTP 201, the meeting SHALL be created, and no attachment rows SHALL be updated by this request

### Requirement: POST /api/meetings/from-calendar is removed and returns HTTP 410 Gone

The legacy endpoint `POST /api/meetings/from-calendar` SHALL be removed from the meeting create surface. The route SHALL be retained only to emit a deprecation response: every request to `POST /api/meetings/from-calendar`, regardless of body content or authentication state, SHALL return HTTP 410 Gone with body `{error_code: "calendar.import_endpoint_removed", message: <localizable string indicating the preview flow at /meetings/new>}`. Calendar-driven meeting creation MUST be performed through the `POST /api/meetings` endpoint with `calendar_event_id` set, per the modified `Meeting carries an optional Calendar event reference` requirement.

#### Scenario: Calling the legacy endpoint returns HTTP 410

- **WHEN** an authenticated user sends `POST /api/meetings/from-calendar` with body `{"event_id": "gcal_evt_42"}`
- **THEN** the response SHALL be HTTP 410 and the body's `error_code` SHALL equal `calendar.import_endpoint_removed`

#### Scenario: Legacy endpoint never creates a meeting

- **WHEN** any client sends `POST /api/meetings/from-calendar` for any event id
- **THEN** no meeting row SHALL be created and no Playbook generation SHALL be invoked as a side effect of this request

### Requirement: /meetings/new route pre-fills the form from a Calendar event when from_calendar query is present

The front-end route `/meetings/new` SHALL accept an optional `from_calendar` URL query parameter carrying a Calendar event identifier. When the parameter is present, the route SHALL invoke `GET /api/calendar/events/{event_id}` and pre-fill the form fields as follows: `title` from the event title; `scheduled_start_at` from the event start (or left empty if the event has no `start.dateTime`); `scheduled_end_at` from the event end (or left empty); `me_display_name` from the authenticated user's display name; `counterparty_display_name` from the existing `pick_counterparty` rule applied to the filtered attendee list. The user MUST be able to edit every pre-filled field before submission. On submit, the route SHALL send `POST /api/meetings` with the form values plus `calendar_event_id` equal to the query parameter value plus any selected attachment identifiers in `attachments[]`.

When the Calendar fetch fails (any calendar-domain error code), the route SHALL display the localized error message inline (per the existing i18n error code registry), SHALL leave the form fields un-pre-filled (still editable), and SHALL allow the user to submit a manual create (without `calendar_event_id`) if desired.

#### Scenario: Single non-viewer attendee pre-fills counterparty

- **GIVEN** an authenticated user `Sean` (email `sean@example.com`) navigates to `/meetings/new?from_calendar=gcal_evt_42`, and `gcal_evt_42` has attendees `[{email: "sean@example.com", displayName: "Sean"}, {email: "lin@example.com", displayName: "林經理"}]`
- **WHEN** the route mounts and the Calendar fetch resolves successfully
- **THEN** the form's `counterparty_display_name` field SHALL be pre-filled with `"林經理"` and `me_display_name` SHALL be pre-filled with `"Sean"`

#### Scenario: Multiple non-viewer attendees leave counterparty empty

- **GIVEN** an authenticated user navigates to `/meetings/new?from_calendar=gcal_evt_88` where the event has the viewer plus two non-viewer human attendees
- **WHEN** the route mounts and the Calendar fetch resolves successfully
- **THEN** the form's `counterparty_display_name` field SHALL be empty (the user fills it in manually)

#### Scenario: Calendar fetch error displays inline message and allows manual create

- **GIVEN** an authenticated user navigates to `/meetings/new?from_calendar=gcal_unknown` and the Calendar fetch returns HTTP 404 with `error_code: calendar.event_not_found`
- **WHEN** the route renders the fetch result
- **THEN** the page SHALL display the localized message for `calendar.event_not_found`, the form SHALL remain rendered with empty fields, and a subsequent submit without `calendar_event_id` SHALL create a manual meeting normally

### Requirement: Calendar import button on /calendar/import navigates to the preview form instead of firing a create request

The Calendar import action exposed in the front-end at `/calendar/import` (the upcoming-events list registered per the existing capability spec entry `Calendar import lives at /calendar/import to disambiguate from the meetings calendar view`) SHALL no longer fire a `POST` request when the user clicks the import button on a row. Instead, clicking the button SHALL navigate the browser to `/meetings/new?from_calendar=<event_id>` where `<event_id>` is the Google Calendar event identifier for the row. No network request SHALL be issued by the import button click; the Calendar event detail is fetched by the destination route via `GET /api/calendar/events/{event_id}`.

#### Scenario: Clicking the import button navigates without issuing a network request

- **GIVEN** an authenticated user is on `/calendar/import` and at least one upcoming event row is rendered
- **WHEN** the user clicks the import button on the row for event `gcal_evt_42`
- **THEN** the browser SHALL navigate to `/meetings/new?from_calendar=gcal_evt_42` and no `POST` request SHALL have been issued during the click handler
