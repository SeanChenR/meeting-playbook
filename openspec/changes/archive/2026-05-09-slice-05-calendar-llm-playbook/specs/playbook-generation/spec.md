## ADDED Requirements

### Requirement: Generator produces all seven playbook fields with non-empty content for any Calendar event input

The `PlaybookGenerator` capability SHALL accept a Calendar event record (title, attendees, start time, end time, optional description, organizer) and produce a playbook draft containing all seven content fields defined by `playbook-management`: `free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`. Every structured field in the returned draft MUST be a non-empty string. The free-form markdown body MUST contain at least three lines of markdown content.

#### Scenario: Rich event input produces seven non-empty fields

- **GIVEN** a Calendar event with title, two attendees, a description longer than 200 characters, and a one-hour duration
- **WHEN** the generator processes that event
- **THEN** the returned draft SHALL contain non-empty strings for `free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, and `red_lines`

#### Scenario: Sparse event input still produces seven non-empty fields via fallback

- **GIVEN** a Calendar event with only a title (no description, no attendees other than the user, no organizer name)
- **WHEN** the generator processes that event
- **THEN** the returned draft SHALL still contain non-empty strings for all six structured fields and a `free_form_markdown` of at least three lines

##### Example: minimum non-empty contract per field

| Field | Minimum content |
| ----- | --------------- |
| `free_form_markdown` | at least three lines (each line ≥ 1 non-whitespace character) |
| `objective` | non-empty string after trimming whitespace |
| `counterparty_profile` | non-empty string after trimming whitespace |
| `anticipated_topics` | non-empty string after trimming whitespace |
| `anticipated_objections` | non-empty string after trimming whitespace |
| `talking_points` | non-empty string after trimming whitespace |
| `red_lines` | non-empty string after trimming whitespace |

---

### Requirement: Generator uses Vertex AI Gemini 2.5 Pro through the official SDK

The generator SHALL invoke the Gemini 2.5 Pro model on Vertex AI through the `google-genai` SDK with structured-output mode (response schema enforcing the seven string fields). The generator SHALL NOT call any non-Vertex-AI provider, and SHALL NOT bypass the SDK by issuing raw HTTP requests. Authentication MUST flow through Application Default Credentials so deployments can swap service accounts without code changes.

#### Scenario: Non-Vertex provider is forbidden

- **WHEN** the generator code is reviewed
- **THEN** there MUST be no import of, nor HTTP call to, providers other than Vertex AI's Gemini family

#### Scenario: Structured-output schema is enforced

- **WHEN** the generator builds its request to Gemini 2.5 Pro
- **THEN** the request SHALL include a JSON response schema with exactly the seven string keys defined by `playbook-management`

---

### Requirement: Generator surfaces localizable failure codes for upstream and parsing errors

When generation cannot succeed, the generator SHALL raise an exception that the calling router maps into one of the following error codes, each resolved by the frontend through the i18n key registry:

- `playbook.generation_timeout` — the Vertex AI call exceeded a 60-second deadline. HTTP 504.
- `playbook.generation_failed` — the Vertex AI call returned an error response, or the returned JSON could not be validated against the seven-field schema. HTTP 502.

These codes SHALL be the only generator-domain failure codes; new failure modes require a separate change.

#### Scenario: Upstream timeout surfaces playbook.generation_timeout

- **GIVEN** the Vertex AI request takes longer than 60 seconds
- **WHEN** the generator is invoked
- **THEN** the generator SHALL raise an error that the router maps to HTTP 504 with `error_code: playbook.generation_timeout`

#### Scenario: Schema validation failure surfaces playbook.generation_failed

- **GIVEN** the Vertex AI response is HTTP 200 but the body cannot be parsed as JSON conforming to the seven-string-fields schema
- **WHEN** the generator processes that response
- **THEN** the generator SHALL raise an error that the router maps to HTTP 502 with `error_code: playbook.generation_failed`

---

### Requirement: Generator output is suitable for direct upsert through the existing playbook repository

The generator SHALL emit a draft whose shape exactly matches the upsert payload accepted by `PlaybookRepository.upsert_for_meeting` defined in `playbook-management`: a dictionary with exactly the seven string keys (`free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`) and no additional keys. Callers MUST be able to pass the draft straight to the repository without remapping or filtering.

#### Scenario: Draft is shape-compatible with the upsert payload

- **WHEN** the generator returns a draft for any input event
- **THEN** the draft's keys SHALL be exactly the seven content-field names defined by `playbook-management`, and each value SHALL be a string

#### Scenario: Repository upsert succeeds without intermediate transformation

- **GIVEN** a generator output `draft` and a meeting `m_target`
- **WHEN** `PlaybookRepository.upsert_for_meeting(meeting_id="m_target", payload=draft)` is invoked
- **THEN** the upsert SHALL succeed and persist all seven fields verbatim

## ADDED Requirements (post-smoke ingest 2026-05-09 round 2)

### Requirement: Generator output is written from the signed-in viewer's point of view

The generator SHALL accept the signed-in user's email and display name as inputs (`viewer_email`, `viewer_name`) and SHALL emit a draft whose seven content fields read as preparation FOR that viewer, not as a third-person summary of the meeting. The prompt sent to Vertex AI SHALL include a leading paragraph that names the viewer, classifies their role in the meeting, names the other parties, and explicitly instructs the model to write from the viewer's perspective.

The viewer's role SHALL be classified as one of three labels:

- `organizer` — the viewer's email matches the event organizer's email (case-insensitive, whitespace-trimmed)
- `attendee` — the viewer's email matches an attendee email and is not the organizer
- `external` — the viewer's email matches neither the organizer nor any attendee (e.g. events read from a subscribed calendar)

The prompt SHALL include a role-specific guidance sentence so the model produces appropriately framed content for each label.

#### Scenario: Organizer-perspective prompt names the viewer as the host

- **GIVEN** a Calendar event where `event.organizer_email` equals the viewer's email
- **WHEN** the generator builds the primary prompt
- **THEN** the prompt SHALL contain the viewer's name and email, the literal role label `organizer`, and a sentence instructing the model that the viewer is hosting / driving the meeting

#### Scenario: Attendee-perspective prompt names the viewer as a participant

- **GIVEN** a Calendar event where the viewer's email is in `event.attendees` but NOT the organizer
- **WHEN** the generator builds the primary prompt
- **THEN** the prompt SHALL contain the literal role label `attendee` and a sentence instructing the model that the viewer was invited by someone else and the playbook should read as participant preparation

#### Scenario: External-perspective prompt names the viewer as an observer

- **GIVEN** a Calendar event where the viewer's email is neither the organizer nor in attendees (a subscribed-calendar event)
- **WHEN** the generator builds the primary prompt
- **THEN** the prompt SHALL contain the literal role label `external` and a sentence instructing the model that the viewer is previewing this event from a subscribed calendar

#### Scenario: Empty viewer_email degrades safely to external role

- **GIVEN** an empty `viewer_email`
- **WHEN** the generator builds the primary prompt
- **THEN** the role classification SHALL be `external` and the prompt SHALL still be valid and emitted

#### Scenario: Generator output shape is unchanged across roles

- **GIVEN** any of the three role classifications
- **WHEN** the generator returns the draft
- **THEN** the draft keys SHALL be exactly the seven content-field names defined by `playbook-management`, identical to the round-1 contract — only the textual content varies by role
