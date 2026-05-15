# meeting-management Specification

## Purpose

TBD - created by archiving change 'slice-03-meeting-crud'. Update Purpose after archive.

## Requirements

### Requirement: Meeting belongs to exactly one user with strict ownership isolation

Every meeting record SHALL carry a non-nullable foreign key to the Better Auth `user.id`. The meeting REST endpoints MUST scope every read, list, and delete operation to the authenticated user identifier supplied via the `X-User-Id` header. When a user requests a meeting that does not exist OR exists but is owned by another user, the backend SHALL respond with HTTP 404 and MUST NOT distinguish between the two cases in the response body, in order to avoid leaking the existence of other users' meetings.

#### Scenario: List returns only meetings owned by the requesting user

- **WHEN** user A sends `GET /api/meetings` and user B owns meetings in the database
- **THEN** the response body SHALL contain only meetings owned by user A and SHALL NOT contain any meeting owned by user B

#### Scenario: Reading another user's meeting returns 404

- **GIVEN** a meeting with id `m_xyz` owned by user B
- **WHEN** user A sends `GET /api/meetings/m_xyz`
- **THEN** the response status SHALL be HTTP 404 and the response body MUST NOT reveal that `m_xyz` exists

#### Scenario: Deleting another user's meeting returns 404

- **GIVEN** a meeting with id `m_xyz` owned by user B
- **WHEN** user A sends `DELETE /api/meetings/m_xyz`
- **THEN** the response status SHALL be HTTP 404 and the meeting MUST remain in the database

#### Scenario: Reading own meeting returns 200

- **GIVEN** a meeting with id `m_own` owned by user A
- **WHEN** user A sends `GET /api/meetings/m_own`
- **THEN** the response status SHALL be HTTP 200 and the body SHALL contain the meeting fields


<!-- @trace
source: slice-03-meeting-crud
updated: 2026-05-07
code:
  - packages/web/src/components/locale-toggle.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/src/test-setup.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/lib/i18n.ts
  - CLAUDE.md
  - packages/web/src/App.tsx
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/i18n-errors.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/login.tsx
  - packages/web/package.json
  - packages/backend/meeting_playbook/meetings/schemas.py
  - bun.lock
  - packages/web/src/routes/totp/verify.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/main.tsx
  - packages/web/src/routes/home.tsx
  - docs/agents/meetings.md
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/ui/alert-dialog.tsx
  - packages/backend/meeting_playbook/meetings/__init__.py
  - packages/web/src/routes/signup.tsx
  - packages/auth/src/server.ts
  - packages/backend/alembic/versions/0001_create_meeting.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/routes/totp/enroll.tsx
tests:
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/lib/i18n-render.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/lib/i18n.test.ts
  - packages/web/src/routes/login-i18n.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/i18n-missing-key.test.ts
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/test_error_envelope.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/lib/i18n-bootstrap.test.ts
  - packages/auth/src/__tests__/error-envelope.test.ts
  - packages/backend/tests/meetings/__init__.py
-->

---
### Requirement: Meeting carries a title, counterparty display name, and me display name

A meeting record SHALL persist three required free-text fields: `title`, `counterparty_display_name`, and `me_display_name`. The `POST /api/meetings` endpoint MUST validate that all three fields are present and non-empty after trimming whitespace. When validation fails, the backend SHALL respond with an HTTP 4xx status and a JSON body containing an `error_code` value that the frontend resolves to a localized message via the i18n key registry.

#### Scenario: Successful create persists all three fields

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林經理", "me_display_name": "Sean"}`
- **THEN** the response status SHALL be HTTP 201 and the response body SHALL contain `title`, `counterparty_display_name`, and `me_display_name` matching the request

#### Scenario: Missing field is rejected with localized error code

- **WHEN** an authenticated user sends `POST /api/meetings` with body missing the `title` field
- **THEN** the response status SHALL be HTTP 422 and the response body SHALL contain an `error_code` such as `meeting.title.required`

##### Example: required-field validation matrix

| Request body | Expected status | Expected error_code |
| ----- | --------------- | ----- |
| `{"title": "", "counterparty_display_name": "林", "me_display_name": "Sean"}` | 422 | `meeting.title.required` |
| `{"title": "Q3", "counterparty_display_name": "  ", "me_display_name": "Sean"}` | 422 | `meeting.counterparty_display_name.required` |
| `{"title": "Q3", "counterparty_display_name": "林", "me_display_name": ""}` | 422 | `meeting.me_display_name.required` |
| `{"title": "Q3", "counterparty_display_name": "林", "me_display_name": "Sean"}` | 201 | (none) |


<!-- @trace
source: slice-03-meeting-crud
updated: 2026-05-07
code:
  - packages/web/src/components/locale-toggle.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/src/test-setup.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/lib/i18n.ts
  - CLAUDE.md
  - packages/web/src/App.tsx
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/i18n-errors.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/login.tsx
  - packages/web/package.json
  - packages/backend/meeting_playbook/meetings/schemas.py
  - bun.lock
  - packages/web/src/routes/totp/verify.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/main.tsx
  - packages/web/src/routes/home.tsx
  - docs/agents/meetings.md
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/ui/alert-dialog.tsx
  - packages/backend/meeting_playbook/meetings/__init__.py
  - packages/web/src/routes/signup.tsx
  - packages/auth/src/server.ts
  - packages/backend/alembic/versions/0001_create_meeting.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/routes/totp/enroll.tsx
tests:
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/lib/i18n-render.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/lib/i18n.test.ts
  - packages/web/src/routes/login-i18n.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/i18n-missing-key.test.ts
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/test_error_envelope.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/lib/i18n-bootstrap.test.ts
  - packages/auth/src/__tests__/error-envelope.test.ts
  - packages/backend/tests/meetings/__init__.py
-->

---
### Requirement: Meeting status defaults to scheduled at creation

A meeting record SHALL have a `status` column constrained to one of three values: `scheduled`, `in_progress`, `completed`. On creation via `POST /api/meetings`, the backend MUST set `status` to `scheduled` and MUST NOT accept a client-supplied status value. Status transitions out of `scheduled` are out of scope for this slice and SHALL be handled by a later slice.

#### Scenario: New meeting has status scheduled

- **WHEN** an authenticated user sends `POST /api/meetings` with a valid body
- **THEN** the response body SHALL contain `"status": "scheduled"`

#### Scenario: Client-supplied status on create is ignored

- **WHEN** an authenticated user sends `POST /api/meetings` with a body containing `"status": "completed"`
- **THEN** the persisted meeting SHALL have `status` equal to `scheduled`, not `completed`


<!-- @trace
source: slice-03-meeting-crud
updated: 2026-05-07
code:
  - packages/web/src/components/locale-toggle.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/src/test-setup.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/lib/i18n.ts
  - CLAUDE.md
  - packages/web/src/App.tsx
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/i18n-errors.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/login.tsx
  - packages/web/package.json
  - packages/backend/meeting_playbook/meetings/schemas.py
  - bun.lock
  - packages/web/src/routes/totp/verify.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/main.tsx
  - packages/web/src/routes/home.tsx
  - docs/agents/meetings.md
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/ui/alert-dialog.tsx
  - packages/backend/meeting_playbook/meetings/__init__.py
  - packages/web/src/routes/signup.tsx
  - packages/auth/src/server.ts
  - packages/backend/alembic/versions/0001_create_meeting.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/routes/totp/enroll.tsx
tests:
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/lib/i18n-render.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/lib/i18n.test.ts
  - packages/web/src/routes/login-i18n.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/i18n-missing-key.test.ts
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/test_error_envelope.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/lib/i18n-bootstrap.test.ts
  - packages/auth/src/__tests__/error-envelope.test.ts
  - packages/backend/tests/meetings/__init__.py
-->

---
### Requirement: Meeting carries an optional Calendar event reference

A meeting record SHALL have a nullable `calendar_event_id` text column. On creation via `POST /api/meetings`, this column MUST be left null and SHALL NOT be settable by the create endpoint in this slice. A later slice will populate this column when integrating Google Calendar.

#### Scenario: New meeting has null calendar_event_id

- **WHEN** an authenticated user sends `POST /api/meetings` with a valid body
- **THEN** the persisted meeting SHALL have `calendar_event_id` equal to null


<!-- @trace
source: slice-03-meeting-crud
updated: 2026-05-07
code:
  - packages/web/src/components/locale-toggle.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/src/test-setup.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/lib/i18n.ts
  - CLAUDE.md
  - packages/web/src/App.tsx
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/i18n-errors.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/login.tsx
  - packages/web/package.json
  - packages/backend/meeting_playbook/meetings/schemas.py
  - bun.lock
  - packages/web/src/routes/totp/verify.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/main.tsx
  - packages/web/src/routes/home.tsx
  - docs/agents/meetings.md
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/ui/alert-dialog.tsx
  - packages/backend/meeting_playbook/meetings/__init__.py
  - packages/web/src/routes/signup.tsx
  - packages/auth/src/server.ts
  - packages/backend/alembic/versions/0001_create_meeting.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/routes/totp/enroll.tsx
tests:
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/lib/i18n-render.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/lib/i18n.test.ts
  - packages/web/src/routes/login-i18n.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/i18n-missing-key.test.ts
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/test_error_envelope.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/lib/i18n-bootstrap.test.ts
  - packages/auth/src/__tests__/error-envelope.test.ts
  - packages/backend/tests/meetings/__init__.py
-->

---
### Requirement: Meeting carries an ASR provider preference defaulting to whisper

A meeting record SHALL have an `asr_provider` text column, constrained to a value identifying a registered ASR provider. On creation via `POST /api/meetings`, the backend MUST default `asr_provider` to `whisper` when the client does not supply one, and MUST persist the value so that later slices reading the meeting honor the same provider choice for transcription sessions.

#### Scenario: New meeting defaults to whisper

- **WHEN** an authenticated user sends `POST /api/meetings` without specifying an ASR provider
- **THEN** the persisted meeting SHALL have `asr_provider` equal to `whisper`

#### Scenario: GET returns the persisted ASR provider

- **GIVEN** a meeting with `asr_provider` equal to `whisper` owned by user A
- **WHEN** user A sends `GET /api/meetings/{id}` for that meeting
- **THEN** the response body SHALL contain `"asr_provider": "whisper"`


<!-- @trace
source: slice-03-meeting-crud
updated: 2026-05-07
code:
  - packages/web/src/components/locale-toggle.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/src/test-setup.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/lib/i18n.ts
  - CLAUDE.md
  - packages/web/src/App.tsx
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/i18n-errors.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/login.tsx
  - packages/web/package.json
  - packages/backend/meeting_playbook/meetings/schemas.py
  - bun.lock
  - packages/web/src/routes/totp/verify.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/main.tsx
  - packages/web/src/routes/home.tsx
  - docs/agents/meetings.md
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/ui/alert-dialog.tsx
  - packages/backend/meeting_playbook/meetings/__init__.py
  - packages/web/src/routes/signup.tsx
  - packages/auth/src/server.ts
  - packages/backend/alembic/versions/0001_create_meeting.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/routes/totp/enroll.tsx
tests:
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/lib/i18n-render.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/lib/i18n.test.ts
  - packages/web/src/routes/login-i18n.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/i18n-missing-key.test.ts
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/test_error_envelope.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/lib/i18n-bootstrap.test.ts
  - packages/auth/src/__tests__/error-envelope.test.ts
  - packages/backend/tests/meetings/__init__.py
-->

---
### Requirement: Meeting list is sorted newest-first by creation time

The `GET /api/meetings` endpoint SHALL return meetings owned by the authenticated user in descending order of `created_at`. When the user owns no meetings, the response SHALL be HTTP 200 with an empty array body, never HTTP 404.

#### Scenario: Multiple meetings sort newest first

- **GIVEN** user A owns three meetings with `created_at` timestamps T1 < T2 < T3
- **WHEN** user A sends `GET /api/meetings`
- **THEN** the response body SHALL be a list ordered T3, T2, T1

#### Scenario: Empty list returns 200 with empty array

- **GIVEN** user A owns zero meetings
- **WHEN** user A sends `GET /api/meetings`
- **THEN** the response status SHALL be HTTP 200 and the body SHALL be an empty JSON array

<!-- @trace
source: slice-03-meeting-crud
updated: 2026-05-07
code:
  - packages/web/src/components/locale-toggle.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/src/test-setup.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/lib/i18n.ts
  - CLAUDE.md
  - packages/web/src/App.tsx
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/i18n-errors.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/login.tsx
  - packages/web/package.json
  - packages/backend/meeting_playbook/meetings/schemas.py
  - bun.lock
  - packages/web/src/routes/totp/verify.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/main.tsx
  - packages/web/src/routes/home.tsx
  - docs/agents/meetings.md
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/ui/alert-dialog.tsx
  - packages/backend/meeting_playbook/meetings/__init__.py
  - packages/web/src/routes/signup.tsx
  - packages/auth/src/server.ts
  - packages/backend/alembic/versions/0001_create_meeting.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/routes/totp/enroll.tsx
tests:
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/lib/i18n-render.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/lib/i18n.test.ts
  - packages/web/src/routes/login-i18n.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/i18n-missing-key.test.ts
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/test_error_envelope.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/conftest.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/lib/i18n-bootstrap.test.ts
  - packages/auth/src/__tests__/error-envelope.test.ts
  - packages/backend/tests/meetings/__init__.py
-->

---
### Requirement: Meeting status transitions are atomic and only allowed in the forward direction

The repository SHALL provide `MeetingRepository.transition_status(meeting_id, expected_from, target)` as the SINGLE write path for the meeting `status` column. The transition SHALL succeed atomically (single SQL `UPDATE ... WHERE status = :expected_from RETURNING id`) so two concurrent attempts cannot both transition the same row. The only allowed transitions are:

- `scheduled → in_progress` (when a session starts)
- `in_progress → completed` (when a session ends)

Any other combination (backwards, skipping a state, repeating the current state) MUST raise `MeetingStatusConflict` carrying the requested transition and the actual current status. Direct `UPDATE meeting SET status = ...` SQL outside `transition_status` is forbidden in all production code paths.

#### Scenario: Allowed transition succeeds atomically

- **GIVEN** meeting `m_abc` has `status = "scheduled"`
- **WHEN** `MeetingRepository.transition_status("m_abc", expected_from="scheduled", target="in_progress")` is invoked
- **THEN** the row's status SHALL become `"in_progress"`, `updated_at` SHALL advance, and the call SHALL return successfully

#### Scenario: Backwards transition raises MeetingStatusConflict

- **GIVEN** meeting `m_abc` has `status = "completed"`
- **WHEN** `MeetingRepository.transition_status("m_abc", expected_from="in_progress", target="completed")` is invoked
- **THEN** the call SHALL raise `MeetingStatusConflict`, the row's status SHALL remain `"completed"`, and `updated_at` MUST NOT change

#### Scenario: Concurrent transition attempts are mutually exclusive

- **GIVEN** meeting `m_abc` has `status = "scheduled"` and two requests both attempt `scheduled → in_progress`
- **WHEN** both requests execute concurrently
- **THEN** exactly one SHALL succeed and exactly one SHALL raise `MeetingStatusConflict` (the second request observes status as already `in_progress`)

#### Scenario: Direct UPDATE bypassing transition_status is treated as a contract violation

- **WHEN** the meeting-domain source code is reviewed
- **THEN** there MUST be no `UPDATE meeting SET status` SQL anywhere outside `MeetingRepository.transition_status`; greppable enforcement is acceptable

<!-- @trace
source: slice-06-mic-transcript-session
updated: 2026-05-10
code:
  - packages/backend/meeting_playbook/sessions/service.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - docs/agents/audio.md
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/asr/base.py
  - packages/web/src/components/transcript-pane.tsx
  - docs/agents/sessions.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/web/src/lib/session-ws.ts
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/backend/meeting_playbook/audio/__init__.py
  - docs/agents/asr.md
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/alembic/versions/0003_create_session_tables.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/locales/zh-TW.json
  - .env.example
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/asr/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/sessions/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/capture-indicator.tsx
  - packages/web/src/lib/transcripts-api.ts
tests:
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/auth/src/__tests__/gateway-websocket.test.ts
  - packages/backend/tests/audio/__init__.py
  - packages/backend/tests/asr/__init__.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/backend/tests/audio/test_capture_protocol.py
  - packages/backend/tests/sessions/test_service.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/sessions/__init__.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/backend/tests/meetings/test_transition_status.py
  - packages/backend/tests/asr/fixtures/short_speech_zh.wav
  - packages/backend/tests/test_alembic_session_tables.py
  - packages/backend/tests/asr/test_base.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/audio/test_capture_integration.py
  - packages/backend/tests/asr/fixtures/short_speech_en.wav
  - packages/backend/tests/sessions/test_repository.py
-->
---
### Requirement: Meeting carries optional scheduled start and end timestamps

The `meeting` table SHALL persist `scheduled_start_at` as `TIMESTAMP WITH TIME ZONE NOT NULL` and `scheduled_end_at` as `TIMESTAMP WITH TIME ZONE NULL`. The `scheduled_start_at` column captures when a meeting is planned to begin and SHALL always be present (distinct from `created_at` which is when the row was created, and distinct from `started_at` / `ended_at` which capture actual session wall-clock times). The `scheduled_end_at` column remains optional and represents when the meeting is planned to finish.

The `POST /api/meetings` endpoint SHALL require a `scheduled_start_at` field as an ISO 8601 timestamp in its request body and SHALL reject any request that omits it or supplies `null` with HTTP 422 and `error_code = "meeting.scheduled_start_at.required"`. The endpoint SHALL accept `scheduled_end_at` as an optional ISO 8601 timestamp; when omitted, the column SHALL be persisted as `NULL`. When both fields are provided in the same request, the backend SHALL reject the request with HTTP 422 and `error_code = "meeting.invalid_time_range"` if `scheduled_end_at < scheduled_start_at`. The `GET /api/meetings` (list) and `GET /api/meetings/{id}` (detail) endpoints SHALL include both fields in their response payloads; `scheduled_start_at` SHALL always be a non-null ISO 8601 string, while `scheduled_end_at` SHALL be a string or `null`.

The `MeetingRepository.create()` method signature SHALL accept `scheduled_start_at: datetime` as a required keyword argument and `scheduled_end_at: datetime | None = None` as optional. The repository's read methods (`get_for_user`, `list_for_user`) SHALL include both columns in returned dataclasses.

Pre-existing meeting rows that contained `NULL` in `scheduled_start_at` before this requirement landed SHALL be backfilled to the row's `created_at` value by the migration that establishes the NOT NULL constraint. Once backfilled, the original NULL state SHALL NOT be recoverable; downgrading the column to nullable SHALL NOT restore NULLs in previously-backfilled rows.

#### Scenario: Create with both schedule fields persists them

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean", "scheduled_start_at": "2026-06-15T14:00:00Z", "scheduled_end_at": "2026-06-15T15:00:00Z"}`
- **THEN** the response status SHALL be HTTP 201, the response body SHALL include `scheduled_start_at = "2026-06-15T14:00:00Z"` and `scheduled_end_at = "2026-06-15T15:00:00Z"`, and the database row SHALL store those timezone-aware values

#### Scenario: Create without scheduled_start_at is rejected

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean"}` (no `scheduled_start_at`)
- **THEN** the response status SHALL be HTTP 422 and the response body SHALL contain `error_code = "meeting.scheduled_start_at.required"` and no row SHALL be inserted

#### Scenario: Create with end-before-start is rejected

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3", "counterparty_display_name": "林", "me_display_name": "Sean", "scheduled_start_at": "2026-06-15T15:00:00Z", "scheduled_end_at": "2026-06-15T14:00:00Z"}`
- **THEN** the response status SHALL be HTTP 422 and the response body SHALL contain `error_code = "meeting.invalid_time_range"` and no row SHALL be inserted

#### Scenario: Create without scheduled_end_at stores NULL only for end

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean", "scheduled_start_at": "2026-06-15T14:00:00Z"}` (no `scheduled_end_at`)
- **THEN** the response status SHALL be HTTP 201, the response body SHALL include the supplied `scheduled_start_at` and `scheduled_end_at = null`; the database row SHALL hold the timezone-aware start value and `NULL` in `scheduled_end_at`

#### Scenario: List endpoint returns schedule fields for every row

- **GIVEN** the authenticated user owns three meetings whose `scheduled_start_at` values are all non-null, one with `scheduled_end_at` set and two with `scheduled_end_at = NULL`
- **WHEN** the user sends `GET /api/meetings`
- **THEN** the response SHALL include all three meetings and each item SHALL contain a non-null `scheduled_start_at` ISO 8601 string and a `scheduled_end_at` that is either an ISO 8601 string or `null`

#### Scenario: Migration backfills pre-existing NULL rows and enforces NOT NULL

- **GIVEN** the `meeting` table holds rows from prior slices, including some with `scheduled_start_at IS NULL`
- **WHEN** Alembic migration `0012_meeting_start_not_null` upgrades the schema in a single transaction
- **THEN** every previously-NULL `scheduled_start_at` SHALL be set to that row's `created_at` value, the column SHALL afterwards have `NOT NULL` enforced at the database level, and a subsequent `SELECT COUNT(*) FROM meeting WHERE scheduled_start_at IS NULL` SHALL return `0`; the downgrade SHALL drop the NOT NULL constraint but SHALL NOT revert backfilled values to NULL


<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->

---
### Requirement: New meetings default to qwen3 ASR provider; existing rows are not back-filled

The `Meeting.asr_provider` SQLAlchemy column SHALL change its server-side default and ORM default from `"whisper"` to `"qwen3"`. Alembic migration `0008_meeting_asr_provider_default_qwen3` SHALL update the `DEFAULT` clause on the column ONLY; it SHALL NOT issue an `UPDATE` against any existing rows. Pre-existing meeting rows continue to carry whatever value was inserted at create time (typically `"whisper"` for slice-7..10 historical rows).

The POST `/api/meetings` endpoint SHALL respect the new default: when the request body omits `asr_provider`, the new row SHALL be persisted with `asr_provider = "qwen3"`.

#### Scenario: Migration changes default but does not back-fill historical rows

- **GIVEN** the database at slice-10 head with 4 existing meeting rows whose `asr_provider = "whisper"`
- **WHEN** Alembic upgrades to `0008_meeting_asr_provider_default_qwen3`
- **THEN** the column DEFAULT in `pg_attribute` / `information_schema.columns` SHALL be `'qwen3'`; all 4 existing rows SHALL still report `asr_provider = "whisper"`

#### Scenario: New meeting created without asr_provider in body uses qwen3

- **GIVEN** a backend at the new migration head
- **WHEN** the client POSTs `/api/meetings` with `{title, counterparty_display_name, me_display_name}` (no `asr_provider`)
- **THEN** the persisted row SHALL have `asr_provider = "qwen3"`; the response body SHALL include `"asr_provider": "qwen3"`


<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->

---
### Requirement: GET /api/meetings/{id} returns recordings_available and rerun_asr_pending derived fields

The GET single-meeting response payload SHALL gain two derived boolean fields, computed server-side and never persisted to the meeting row:

- **`recordings_available: bool`** — `true` when at least one row in `recording` for this `meeting_id` has `deleted_at IS NULL`; `false` otherwise (including when no recording rows exist at all, e.g. for `scheduled` meetings that never ran). The `source` value (`live` or `offline`) SHALL NOT affect this computation — offline-ingested recordings are counted identically to live-captured ones for the purpose of `recordings_available`.
- **`rerun_asr_pending: bool`** — `true` when the in-flight re-run registry (`packages/backend/meeting_playbook/asr/rerun_runtime.py`) reports `is_pending(meeting_id)`; `false` otherwise.

Both fields SHALL be present on every GET response (no conditional omission); the OpenAPI / Pydantic response model SHALL declare them as required boolean fields.

#### Scenario: Completed meeting with non-deleted recordings reports recordings_available true

- **GIVEN** a `completed` meeting with 2 recording rows (one for me-stream, one for counterparty), both with `deleted_at IS NULL`
- **WHEN** GET `/api/meetings/{id}` is called
- **THEN** the response body SHALL contain `"recordings_available": true` AND `"rerun_asr_pending": false`

#### Scenario: Meeting with all recordings cleaned up reports recordings_available false

- **GIVEN** a `completed` meeting with 2 recording rows, both with `deleted_at = some past timestamp`
- **WHEN** GET `/api/meetings/{id}` is called
- **THEN** the response body SHALL contain `"recordings_available": false`

#### Scenario: Scheduled meeting with no recording rows yet reports recordings_available false

- **GIVEN** a `scheduled` meeting that has never started (zero rows in `recording`)
- **WHEN** GET `/api/meetings/{id}` is called
- **THEN** `"recordings_available"` SHALL be `false` AND `"rerun_asr_pending"` SHALL be `false`

#### Scenario: Active re-run flips rerun_asr_pending true; clears after completion

- **GIVEN** a completed meeting whose re-run task was just spawned (registry contains the meeting ID)
- **WHEN** GET `/api/meetings/{id}` is called while the task is still running
- **THEN** the response body SHALL contain `"rerun_asr_pending": true`
- **AND WHEN** the task completes and pops the registry entry; a subsequent GET fires
- **THEN** the response body SHALL contain `"rerun_asr_pending": false`

#### Scenario: Offline-ingested recording counts toward recordings_available

- **GIVEN** a `completed` meeting whose only recording row has `source = "offline"`, `stream = "me"`, and `deleted_at IS NULL`
- **WHEN** GET `/api/meetings/{id}` is called
- **THEN** the response body SHALL contain `"recordings_available": true` AND `"rerun_asr_pending": false`


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: /meetings SHALL render meetings as a 3-column date-bucketed Kanban

The `/meetings` route SHALL render meetings as a 3-column Kanban board grouped by **lifecycle state**, not by time window.

The three columns SHALL be, in left-to-right visual order:

- **待補錄** (`needs_recording`) — meetings whose `status` is `"scheduled"` AND whose `scheduled_start_at` is strictly less than `now`. Semantic: the scheduled time has already passed but no recording session has begun, so the meeting either needs a follow-up recording (offline ingest or manual entry) or needs to be removed. Column accent: primary.
- **未來** (`upcoming`) — meetings whose `status` is `"scheduled"` AND whose `scheduled_start_at` is greater than or equal to `now`. Semantic: all future commitments that have not yet started. Column accent: muted-foreground.
- **已結束** (`completed`) — meetings whose `status` is one of `"in_progress"` or `"completed"`. Semantic: any meeting whose recording session has been started (regardless of whether it has been finalized) is treated as "actually happened" and SHALL be classified here, independent of `scheduled_start_at`. Column accent: secondary.

Bucket assignment SHALL be implemented by a pure helper function `getMeetingDateBucket(meeting, now)` exported from `packages/web/src/lib/meetings-bucket.ts`. The helper SHALL be called from the Kanban component during render with `now = new Date()`. The helper SHALL return one of the three literal strings `"needs_recording"`, `"upcoming"`, `"completed"` and SHALL NOT return any other value.

The Kanban component SHALL display column headers using the i18n keys `meetings.kanban.bucketNeedsRecording`, `meetings.kanban.bucketUpcoming`, `meetings.kanban.bucketCompleted` (in that left-to-right order). The legacy keys `meetings.kanban.bucketUpcoming`, `meetings.kanban.bucketFuture`, `meetings.kanban.bucketPast` SHALL be removed from both `zh-TW.json` and `en.json` to prevent the analyzer from missing dead translations. The 7-day window constant `SEVEN_DAYS_MS` SHALL be removed from `meetings-bucket.ts`.

The "已結束" column SHALL sort its meetings by `scheduled_start_at` in descending order (most recent first), reusing the existing `_sortPastDesc` helper renamed to `_sortCompletedDesc`. The other two columns SHALL render in the order returned by the backend list endpoint.

Each column SHALL render a header with the bucket label, a count badge, a vertically scrollable card list, and an empty-state hint. The Kanban container SHALL use `grid-template-columns: repeat(3, minmax(280px, 1fr))`. Drag-and-drop reordering SHALL NOT be supported in this iteration.

#### Scenario: Three-bucket distribution under new rules

- **GIVEN** `now = 2026-05-12T10:00:00 local` and the backend returns five meetings:

  | id | status        | scheduled_start_at        |
  |----|---------------|---------------------------|
  | a  | in_progress   | 2026-04-01T09:00:00       |
  | b  | scheduled     | 2026-05-13T15:00:00       |
  | c  | scheduled     | 2026-05-25T15:00:00       |
  | d  | scheduled     | 2026-05-01T15:00:00       |
  | e  | completed     | 2026-04-15T10:00:00       |

- **WHEN** the /meetings Kanban renders
- **THEN** column 待補錄 SHALL contain meeting `d` (scheduled but `scheduled_start_at < now`)
- **AND** column 未來 SHALL contain meetings `b` and `c` (scheduled with `scheduled_start_at >= now`)
- **AND** column 已結束 SHALL contain meetings `a` (in_progress) and `e` (completed)

#### Scenario: in_progress meeting with past scheduled_start_at falls into 已結束

- **GIVEN** a meeting with `status === "in_progress"` and `scheduled_start_at = "2026-04-01T09:00:00"` and `now = "2026-05-12T10:00:00"`
- **WHEN** `getMeetingDateBucket` is called
- **THEN** the helper SHALL return `"completed"` (because `status === "in_progress"` short-circuits before the time comparison)

#### Scenario: Overdue scheduled meeting falls into 待補錄

- **GIVEN** a meeting with `status === "scheduled"` and `scheduled_start_at = "2026-05-01T15:00:00"` and `now = "2026-05-12T10:00:00"`
- **WHEN** `getMeetingDateBucket` is called
- **THEN** the helper SHALL return `"needs_recording"` (not `"completed"`, because the meeting was never started)

#### Scenario: Scheduled meeting at exactly now falls into 未來

- **GIVEN** a meeting with `status === "scheduled"` and `scheduled_start_at` equal to `now` (boundary case)
- **WHEN** `getMeetingDateBucket` is called
- **THEN** the helper SHALL return `"upcoming"` (the comparison is `scheduled_start_at >= now`, half-open in the future direction)

#### Scenario: Invalid scheduled_start_at string falls into 待補錄 as safe default

- **GIVEN** a meeting with `status === "scheduled"` and `scheduled_start_at = "not-a-date"` so `Date.parse` returns `NaN`
- **WHEN** `getMeetingDateBucket` is called
- **THEN** the helper SHALL return `"needs_recording"` as a safe default (instead of the previous `"past"` default, since malformed time is treated as "we have no idea when this is meant to happen → needs human attention")
- **AND** SHALL emit a `console.warn` in dev (when `import.meta.env.DEV`)


<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->

---
### Requirement: PATCH /api/meetings/{id} accepts partial updates to title, scheduled times, display names, and asr_provider

The backend SHALL expose `PATCH /api/meetings/{id}` accepting a JSON body with up to six optional fields: `title`, `scheduled_start_at`, `scheduled_end_at`, `counterparty_display_name`, `me_display_name`, `asr_provider`. Any subset of these fields (zero or more) SHALL be accepted; fields that are absent from the request body SHALL leave the corresponding column unchanged. A request with an empty body (no fields supplied) SHALL be treated as a no-op and SHALL return HTTP 200 with the current persisted meeting. Each string field, when present, SHALL be stripped of surrounding whitespace and SHALL NOT be empty after stripping; otherwise the endpoint SHALL respond with HTTP 422 and `error_code = "meeting.invalid_field"`. The endpoint SHALL validate that, after merging the request body with the current row, `scheduled_end_at` (if non-null) is greater than or equal to `scheduled_start_at`; otherwise the endpoint SHALL respond with HTTP 422 and `error_code = "meeting.invalid_time_range"`. The endpoint SHALL return HTTP 404 with `error_code = "meeting.not_found"` when the meeting does not exist OR is owned by a different user, and MUST NOT distinguish between those two cases. A successful update SHALL return HTTP 200 with the `MeetingDetailRead` response shape (the same shape returned by `GET /api/meetings/{id}`), reflecting the merged state of the row.

#### Scenario: PATCH with title only updates only title

- **GIVEN** an authenticated user `u_a` owning meeting `m_x` with `title = "Old"`, `counterparty_display_name = "林"`, `me_display_name = "Sean"`, `scheduled_start_at = "2026-06-15T14:00:00Z"`, `asr_provider = "qwen3"`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"title": "New"}`
- **THEN** the response status SHALL be HTTP 200, the response body SHALL show `title = "New"` and all other fields unchanged, and the database row SHALL persist `title = "New"` while every other column SHALL be byte-identical to its prior value

#### Scenario: PATCH with multiple fields updates them atomically

- **GIVEN** an authenticated user `u_a` owning meeting `m_x`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"title": "Updated", "scheduled_start_at": "2026-07-01T09:00:00Z", "scheduled_end_at": "2026-07-01T10:00:00Z", "me_display_name": "S. Chen"}`
- **THEN** the response status SHALL be HTTP 200 and all four supplied fields SHALL be reflected in the response body and in a single subsequent SELECT against the row

#### Scenario: PATCH with empty body returns current row

- **GIVEN** an authenticated user `u_a` owning meeting `m_x`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{}`
- **THEN** the response status SHALL be HTTP 200 and the response body SHALL be byte-identical to the body returned by `GET /api/meetings/m_x` immediately prior

#### Scenario: PATCH with empty title is rejected

- **GIVEN** an authenticated user `u_a` owning meeting `m_x`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"title": "   "}`
- **THEN** the response status SHALL be HTTP 422, the response body SHALL contain `error_code = "meeting.invalid_field"`, and the meeting row SHALL be unchanged

#### Scenario: PATCH with end-before-start is rejected even when only end is supplied

- **GIVEN** an authenticated user `u_a` owning meeting `m_x` with `scheduled_start_at = "2026-06-15T15:00:00Z"`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"scheduled_end_at": "2026-06-15T14:00:00Z"}`
- **THEN** the response status SHALL be HTTP 422, the response body SHALL contain `error_code = "meeting.invalid_time_range"`, and `scheduled_end_at` SHALL remain at its prior value

#### Scenario: PATCH on a meeting owned by another user returns 404

- **GIVEN** meeting `m_y` is owned by user `u_b`
- **WHEN** user `u_a` sends `PATCH /api/meetings/m_y` with body `{"title": "Hijack"}`
- **THEN** the response status SHALL be HTTP 404, the response body SHALL contain `error_code = "meeting.not_found"`, and the row owned by `u_b` SHALL be unchanged

#### Scenario: PATCH with asr_provider only retains slice-11 behavior

- **GIVEN** an authenticated user `u_a` owning meeting `m_x` with `asr_provider = "qwen3"`
- **WHEN** the user sends `PATCH /api/meetings/m_x` with body `{"asr_provider": "whisper"}`
- **THEN** the response status SHALL be HTTP 200, the response body SHALL show `asr_provider = "whisper"`, and the database row SHALL persist `asr_provider = "whisper"`


<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->

---
### Requirement: MeetingRepository.update_for_user writes any subset of mutable meeting fields in a single UPDATE

The backend SHALL provide `async MeetingRepository.update_for_user(*, user_id: str, meeting_id: str, fields: dict[str, Any]) -> Meeting | None` at `packages/backend/meeting_playbook/meetings/repository.py`. The method SHALL accept a dictionary whose keys are a subset of `{"title", "scheduled_start_at", "scheduled_end_at", "counterparty_display_name", "me_display_name", "asr_provider"}` and SHALL emit a single SQL `UPDATE` statement scoped to `(id = meeting_id AND user_id = user_id)`. When `fields` is empty, the method SHALL skip the UPDATE and SHALL return the result of `get_for_user(user_id=user_id, meeting_id=meeting_id)`. When `fields` is non-empty and the meeting does not exist OR is owned by another user, the method SHALL return `None`. When the update succeeds, the method SHALL return the refreshed `Meeting` row reflecting all committed columns. The existing `update_asr_provider_for_user` method SHALL be retained as a thin wrapper that delegates to `update_for_user(fields={"asr_provider": <value>})` so slice-11 callers and tests remain functional.

#### Scenario: update_for_user with empty fields returns the row unchanged

- **GIVEN** a meeting `m_x` owned by `u_a` with `title = "Original"`
- **WHEN** `repo.update_for_user(user_id="u_a", meeting_id="m_x", fields={})` runs
- **THEN** the call SHALL emit zero UPDATE statements (verified by SQLAlchemy event listener), the returned `Meeting` SHALL have `title = "Original"`, and no other row SHALL be modified

#### Scenario: update_for_user with multiple fields emits one UPDATE

- **GIVEN** a meeting `m_x` owned by `u_a`
- **WHEN** `repo.update_for_user(user_id="u_a", meeting_id="m_x", fields={"title": "T2", "me_display_name": "S2"})` runs
- **THEN** the call SHALL emit exactly one UPDATE statement (verified by SQLAlchemy event listener), the returned `Meeting` SHALL have `title = "T2"` and `me_display_name = "S2"`, and a subsequent SELECT SHALL confirm both columns

#### Scenario: update_for_user across owners returns None

- **GIVEN** a meeting `m_y` owned by `u_b`
- **WHEN** `repo.update_for_user(user_id="u_a", meeting_id="m_y", fields={"title": "Hijack"})` runs
- **THEN** the call SHALL return `None` and the row owned by `u_b` SHALL be unchanged

#### Scenario: update_asr_provider_for_user still works after refactor

- **GIVEN** a meeting `m_x` owned by `u_a` with `asr_provider = "qwen3"`
- **WHEN** `repo.update_asr_provider_for_user(user_id="u_a", meeting_id="m_x", asr_provider="whisper")` runs
- **THEN** the returned `Meeting` SHALL have `asr_provider = "whisper"` and the database row SHALL persist the new value


<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->

---
### Requirement: Meeting list, kanban, and calendar views render scheduled_start_at without created_at fallback

The web client SHALL render scheduled-time displays for a meeting solely from `meeting.scheduled_start_at` and SHALL NOT fall back to `meeting.created_at` for any view, sort key, or date bucket. The `MeetingCard` component SHALL format the scheduled start time using `meeting.scheduled_start_at` only. The Kanban view (`MeetingsKanban`) SHALL sort and bucket meetings by `meeting.scheduled_start_at` only. The Calendar view (`meetings-calendar-utils.toCalendarEvent`) SHALL build calendar events from `meeting.scheduled_start_at` only and SHALL treat the value as guaranteed non-null after slice-15 lands. The TypeScript type for `Meeting.scheduled_start_at` SHALL be narrowed from `string | null` to `string`.

#### Scenario: MeetingCard renders the scheduled start, not created_at

- **GIVEN** a meeting with `scheduled_start_at = "2026-06-15T14:00:00Z"` and `created_at = "2026-05-01T00:00:00Z"`
- **WHEN** `<MeetingCard meeting={meeting} />` renders
- **THEN** the rendered time text SHALL be derived from `2026-06-15T14:00:00Z` and SHALL NOT mention `2026-05-01T00:00:00Z`

#### Scenario: Kanban sorts by scheduled_start_at and never by created_at

- **GIVEN** two meetings `A` and `B`, where `A.scheduled_start_at = "2026-07-01T00:00:00Z"` and `A.created_at = "2026-01-01T00:00:00Z"`, while `B.scheduled_start_at = "2026-06-01T00:00:00Z"` and `B.created_at = "2026-08-01T00:00:00Z"`
- **WHEN** `MeetingsKanban` renders both meetings in the same column
- **THEN** the visual order SHALL place `A` after `B` (because `A.scheduled_start_at > B.scheduled_start_at`), confirming that `created_at` is not consulted

#### Scenario: Calendar event helper returns an event for every row after slice-15

- **GIVEN** a meeting row whose `scheduled_start_at` is a valid ISO 8601 string (guaranteed by NOT NULL constraint)
- **WHEN** `toCalendarEvent(meeting)` runs
- **THEN** the call SHALL return a non-null calendar event object whose `start` field equals `meeting.scheduled_start_at`


<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->

---
### Requirement: meeting detail page lets the user inline-edit title, scheduled times, and display names

The web client SHALL provide an inline edit form on the meeting detail route (`/meetings/$meetingId`) that lets the authenticated user change `title`, `scheduled_start_at`, `scheduled_end_at`, `counterparty_display_name`, and `me_display_name` for the meeting they own. The form SHALL be implemented as a React component at `packages/web/src/components/meeting-edit-form.tsx`, accept the current `Meeting` as a prop, validate inputs with a zod schema that mirrors the backend rules (non-empty trimmed strings; `scheduled_end_at >= scheduled_start_at` when both present), and submit to `PATCH /api/meetings/{id}` only the fields that the user changed. On a successful response the component SHALL invalidate the React Query caches keyed `["meetings"]` and `["meeting", meetingId]` so all three list views (List / Kanban / Calendar) and the detail page reflect the change without a full page reload. On a non-200 response the component SHALL surface the localized error message via `localizedErrorMessage(error_code, t)` and SHALL leave the form open with the user's draft intact. All user-visible strings introduced by this form SHALL exist in both `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json` under the `meetings.edit.*` namespace.

#### Scenario: Edit form saves a changed title and updates the cache

- **GIVEN** the authenticated user is viewing `/meetings/m_x` for a meeting whose `title = "Old"` and clicks the Edit toggle
- **WHEN** the user changes `title` to `"New"` and clicks Save
- **THEN** the component SHALL send `PATCH /api/meetings/m_x` with body `{"title": "New"}`, SHALL render a localized "Saved" confirmation on HTTP 200, and SHALL invalidate the React Query caches `["meetings"]` and `["meeting", "m_x"]` such that returning to the list view shows the new title

#### Scenario: Edit form rejects end-before-start client-side before sending

- **GIVEN** the authenticated user is editing meeting `m_x` with `scheduled_start_at = "2026-06-15T15:00:00Z"`
- **WHEN** the user sets `scheduled_end_at` to `"2026-06-15T14:00:00Z"` and clicks Save
- **THEN** the component SHALL block the request, render the localized `errors.meeting.invalidTimeRange` message next to the `scheduled_end_at` field, and SHALL NOT call `PATCH /api/meetings/m_x`

#### Scenario: Edit form surfaces a server-side 422 in the localized error message

- **GIVEN** the authenticated user submits an edit for meeting `m_x`
- **WHEN** the server responds with HTTP 422 and body `{"error_code": "meeting.invalid_field", "message": "..."}`
- **THEN** the form SHALL remain open with the user's input intact, render the localized message for `meeting.invalid_field`, and re-enable the Save button so the user can correct and retry


<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->

---
### Requirement: meeting detail edit form opens as a centered modal dialog

The `<MeetingEditForm>` component, when triggered from the meeting detail route's Edit toolbar button, SHALL render inside a shadcn `<Dialog>` modal that is centered on the viewport. The dialog SHALL include a `<DialogTitle>` displaying the localized string `meetings.edit.dialogTitle` and a `<DialogDescription>` displaying `meetings.edit.dialogDescription`. The dialog SHALL be dismissible by pressing the Escape key, clicking the backdrop, clicking the Cancel button, or successfully saving (a 200 response from `PATCH /api/meetings/{id}`). The dialog SHALL NOT push the underlying page layout. While the dialog is open, the rest of the detail page SHALL be visible but covered by a semi-transparent backdrop. The dialog SHALL be a sibling of the detail page content (not nested inside a transformed parent) so the centering math is unaffected by scroll position.

#### Scenario: Clicking Edit opens the dialog and rendering the form

- **GIVEN** the authenticated user is viewing `/meetings/m_x` with the edit toggle visible
- **WHEN** the user clicks the toolbar Edit button
- **THEN** a shadcn `<Dialog>` SHALL open centered on the viewport, the dialog title SHALL read the localized string for `meetings.edit.dialogTitle`, the form's five fields SHALL be pre-filled with the meeting's current values, and the page below SHALL be covered by a semi-transparent backdrop

#### Scenario: Pressing Escape closes the dialog

- **GIVEN** the edit dialog is open with a draft change to the title
- **WHEN** the user presses the Escape key
- **THEN** the dialog SHALL close, the draft SHALL be discarded, and no `PATCH /api/meetings/m_x` request SHALL be sent


<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->

---
### Requirement: meeting detail actions bar always renders an upload-audio button

The meeting detail route SHALL render a persistent "Upload audio" button inside the `<MetadataCard>` actions row for every meeting, regardless of the meeting's `status` value. The detail page SHALL pass a `<Button>` element into the `<MetadataCard>` component's new `uploadSlot` prop; the button SHALL have `data-testid="metadata-upload-audio"` and SHALL render the localized label `meetings.session.uploadAudio`. Clicking the button SHALL open the existing `<UploadDialog>` by setting the detail page's `offlineIngestOpen` state to `true`.

The button's visual treatment SHALL adapt to `meeting.status`:

- `status === "scheduled"` → variant `"outline"`, `disabled = false`
- `status === "in_progress"` → variant `"outline"`, `disabled = true` (offline ingest is not allowed while live capture is running; double-writing the `recording` child table would create ambiguous source rows)
- `status === "completed"` → variant `"secondary"`, `disabled = false` (re-ingest is allowed for re-running ASR on completed meetings)

The legacy `<UploadBanner>` component and its `shouldShowOfflineIngestBanner(meeting, now)` predicate SHALL be removed from the codebase along with their tests. The locale keys `offline_ingest.banner.heading`, `offline_ingest.banner.subhead`, `offline_ingest.banner.cta` SHALL be removed from both `zh-TW.json` and `en.json`.

#### Scenario: Upload button is outline-enabled for scheduled meetings

- **GIVEN** a meeting `m_x` with `status = "scheduled"`
- **WHEN** the user navigates to `/meetings/m_x`
- **THEN** a button with `data-testid="metadata-upload-audio"` SHALL be present, SHALL carry the `outline` variant class, SHALL NOT be disabled, and SHALL display the localized text for `meetings.session.uploadAudio`

#### Scenario: Upload button is disabled while in_progress

- **GIVEN** a meeting `m_x` with `status = "in_progress"`
- **WHEN** the user navigates to `/meetings/m_x`
- **THEN** the upload button SHALL be present but `disabled = true`, and clicking SHALL NOT open the upload dialog

#### Scenario: Upload button is secondary-enabled for completed meetings

- **GIVEN** a meeting `m_x` with `status = "completed"`
- **WHEN** the user navigates to `/meetings/m_x`
- **THEN** the upload button SHALL be present, SHALL carry the `secondary` variant class, SHALL NOT be disabled, and clicking SHALL open the upload dialog (used for re-running ASR)


<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->

---
### Requirement: needs_recording kanban cards offer a hover-only upload shortcut and a custom empty CTA

`<MeetingCard>` SHALL accept a `showUploadShortcut?: boolean` prop. When `showUploadShortcut === true`, the card SHALL render a small button with `data-testid="meeting-card-upload-shortcut"` displaying the localized label `meetings.kanban.uploadShortcut`. The button SHALL be visually hidden by default (`opacity-0`) and SHALL fade in only when the card root is hovered (`group-hover:opacity-100 transition-opacity`). Clicking the button SHALL navigate to `/meetings/$id` with `search = { action: "upload" }` for the card's meeting id; clicking SHALL NOT propagate to the card's primary link. When `showUploadShortcut !== true` (default), the card SHALL NOT render the shortcut button at all (DOM-absent, not just hidden).

`<MeetingsKanban>` SHALL pass `showUploadShortcut={true}` to every `<MeetingCard>` rendered inside the `needs_recording` column and `showUploadShortcut={false}` (or omit the prop) for `upcoming` and `completed` columns.

The meeting detail route SHALL read `useSearch().action`; when `action === "upload"`, the route SHALL set `offlineIngestOpen` to `true` on mount AND SHALL clear the `action` query param via `navigate({ search: { action: undefined }, replace: true })` so that page reloads do not re-trigger the dialog.

When the `needs_recording` column has zero meetings, `<MeetingsKanban>` SHALL render the localized string `meetings.kanban.bucketNeedsRecordingEmpty` (zh-TW: "目前沒有待補錄的會議"; en: "No meetings to follow up on") instead of the shared `meetings.kanban.bucketEmpty` hint. The `upcoming` and `completed` columns SHALL continue to use `meetings.kanban.bucketEmpty` when empty.

#### Scenario: needs_recording card mounts the hover shortcut

- **GIVEN** a meeting `m_x` with `status = "scheduled"` and `scheduled_start_at < now` so it lands in the needs_recording bucket
- **WHEN** the Kanban renders `<MeetingCard meeting={m_x} showUploadShortcut={true} />`
- **THEN** a button with `data-testid="meeting-card-upload-shortcut"` SHALL exist in the DOM with class `opacity-0` AND class `group-hover:opacity-100`

#### Scenario: Clicking the shortcut navigates with action=upload

- **GIVEN** a needs_recording card is rendered with the hover shortcut
- **WHEN** the user clicks `data-testid="meeting-card-upload-shortcut"`
- **THEN** the router SHALL navigate to `/meetings/m_x` with `search = { action: "upload" }`, and the click handler SHALL call `event.stopPropagation()` so the card's primary link does NOT also fire

#### Scenario: Detail page reads action=upload and auto-opens the dialog

- **GIVEN** the detail route mounts with `useSearch().action === "upload"`
- **WHEN** the route's mount effect runs
- **THEN** `offlineIngestOpen` SHALL be set to `true`, the upload dialog SHALL open, AND the route SHALL call `navigate({ search: { action: undefined }, replace: true })` to scrub the query so subsequent reloads do not re-fire

#### Scenario: needs_recording empty column shows the custom CTA

- **GIVEN** no meeting in the user's data set falls into the needs_recording bucket
- **WHEN** the Kanban renders the empty needs_recording column
- **THEN** the column body SHALL contain `data-testid="kanban-empty-needs_recording"` AND its text SHALL be the localized string for `meetings.kanban.bucketNeedsRecordingEmpty` (NOT `meetings.kanban.bucketEmpty`)

<!-- @trace
source: slice-15-meeting-edit
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - .env.example
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - CONTEXT.md
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/pyproject.toml
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/package.json
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/ui/dialog.tsx
tests:
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
-->