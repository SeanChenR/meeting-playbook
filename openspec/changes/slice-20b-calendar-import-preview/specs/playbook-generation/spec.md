## ADDED Requirements

### Requirement: Playbook generation is triggered by POST /api/meetings when calendar_event_id is supplied

The Playbook generation capability SHALL be triggered exclusively by `POST /api/meetings` when the request body contains a non-null `calendar_event_id` field. When triggered, the meeting create endpoint SHALL: (1) fetch the Calendar event detail for the supplied `event_id` through the existing `CalendarClient.get_event` path, (2) create the meeting row, (3) optionally associate any attachments listed in the request body, (4) invoke the existing `PlaybookGenerator` capability with the fetched Calendar event, (5) persist the resulting draft through the existing `PlaybookRepository.upsert_for_meeting` contract.

When `POST /api/meetings` is invoked WITHOUT `calendar_event_id` (or with `calendar_event_id: null`), the Playbook generation capability MUST NOT be invoked; the slice-04 auto-create empty playbook path remains in effect for manual meeting creation. Generator failure handling SHALL match the contract documented in this capability's existing `Generator surfaces localizable failure codes for upstream and parsing errors` requirement: the meeting row stays persisted, attachments stay associated, and the response surfaces the corresponding generator error code (`playbook.generation_timeout` HTTP 504 or `playbook.generation_failed` HTTP 502).

#### Scenario: Create meeting with calendar_event_id triggers Playbook generation

- **GIVEN** an authenticated user with Calendar connected and a Calendar event `gcal_evt_42` with title `"Q3 review"` and a one-hour duration
- **WHEN** the user sends `POST /api/meetings` with body containing `calendar_event_id: "gcal_evt_42"`, `title: "Q3 review"`, `counterparty_display_name: "林經理"`, `me_display_name: "Sean"`, `attachments: []`
- **THEN** the response SHALL be HTTP 201, the new meeting row SHALL have `calendar_event_id = "gcal_evt_42"`, and a Playbook row SHALL exist for that meeting with the seven content fields populated by the generator

#### Scenario: Create meeting without calendar_event_id does not invoke the generator

- **WHEN** an authenticated user sends `POST /api/meetings` with a valid body and `calendar_event_id` omitted (or set to null)
- **THEN** the response SHALL be HTTP 201, the persisted meeting SHALL have `calendar_event_id = null`, and the Playbook for that meeting SHALL be the slice-04 auto-created empty draft (the generator MUST NOT have been called for this request)

#### Scenario: Generator failure leaves the meeting and attachments persisted

- **GIVEN** the Calendar event fetch succeeds but the generator raises a timeout
- **WHEN** an authenticated user sends `POST /api/meetings` with `calendar_event_id` and a non-empty `attachments[]` array
- **THEN** the meeting row SHALL exist in the database with `calendar_event_id` populated, each listed attachment SHALL be associated with the new meeting, and the response SHALL be a 504-class envelope with `error_code: playbook.generation_timeout`
