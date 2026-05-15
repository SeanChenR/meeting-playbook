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

The `meeting` table SHALL persist two optional timestamp columns: `scheduled_start_at` and `scheduled_end_at`, both `TIMESTAMP WITH TIME ZONE NULL`. These columns capture when a meeting is planned to occur (distinct from `created_at` which is when the row was created, and distinct from `started_at` / `ended_at` which capture actual session wall-clock times). Existing meeting rows created before this capability SHALL retain `NULL` in both new columns; no backfill SHALL be performed by the migration.

The `POST /api/meetings` endpoint SHALL accept two optional ISO 8601 timestamp fields `scheduled_start_at` and `scheduled_end_at` in its request body. When omitted, both columns SHALL be persisted as `NULL`. When provided, the values SHALL be persisted as parsed timezone-aware timestamps. The `GET /api/meetings` (list) and `GET /api/meetings/{id}` (detail) endpoints SHALL include both fields in their response payloads (as ISO 8601 strings or `null`).

The `MeetingRepository.create()` method signature SHALL accept two new optional keyword arguments `scheduled_start_at: datetime | None = None` and `scheduled_end_at: datetime | None = None`. The repository's read methods (`get_for_user`, `list_for_user`) SHALL include both columns in returned dataclasses.

#### Scenario: Create with both schedule fields persists them

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean", "scheduled_start_at": "2026-06-15T14:00:00Z", "scheduled_end_at": "2026-06-15T15:00:00Z"}`
- **THEN** the response status SHALL be HTTP 201, the response body SHALL include `scheduled_start_at = "2026-06-15T14:00:00Z"` and `scheduled_end_at = "2026-06-15T15:00:00Z"`, and the database row SHALL store those timezone-aware values

#### Scenario: Create without schedule fields stores NULL

- **WHEN** an authenticated user sends `POST /api/meetings` with body `{"title": "Q3 review", "counterparty_display_name": "林", "me_display_name": "Sean"}` (no schedule fields)
- **THEN** the response SHALL be HTTP 201 with `scheduled_start_at = null` and `scheduled_end_at = null` in the response body; the database row SHALL hold `NULL` in both columns

#### Scenario: List endpoint returns schedule fields for every row

- **GIVEN** the authenticated user owns three meetings: one with both schedule fields set, one with only `scheduled_start_at` set, and one with both null
- **WHEN** the user sends `GET /api/meetings`
- **THEN** the response SHALL include all three meetings and each item in the array SHALL contain both `scheduled_start_at` and `scheduled_end_at` keys (with values or `null`)

#### Scenario: Migration adds nullable columns without affecting existing rows

- **GIVEN** the `meeting` table holds existing rows from prior slices
- **WHEN** Alembic migration `0004_add_meeting_scheduled_times` upgrades the schema
- **THEN** both `scheduled_start_at` and `scheduled_end_at` columns SHALL exist with type `TIMESTAMP WITH TIME ZONE`, nullable, and every existing row SHALL contain `NULL` in both columns; the downgrade SHALL drop both columns

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

The `/meetings` route SHALL replace the previous auto-fill grid
(`grid-template-columns: repeat(auto-fill, minmax(320px, 1fr))`)
with a 3-column Kanban board grouped by date.

The three columns SHALL be:

- **即將到來** (upcoming) — meetings whose `status` is
  `"in_progress"` regardless of date, OR meetings whose `status` is
  `"scheduled"` and whose `scheduled_start_at` falls in
  `[startOfToday, startOfToday + 7 days)`. Column accent: primary.
- **未來** (future) — meetings whose `status` is `"scheduled"` and
  whose `scheduled_start_at` is at or beyond `startOfToday + 7
  days`, OR meetings with `status === "scheduled"` and no
  `scheduled_start_at` set. Column accent: muted-foreground.
- **已結束** (past) — meetings whose `status` is `"completed"`, OR
  meetings whose `status` is `"scheduled"` but whose
  `scheduled_start_at` is before `startOfToday` (overdue, never
  started). Column accent: secondary (the new teal token from
  `ui-design-system`).

Bucket assignment SHALL be implemented by a pure helper function
`getMeetingDateBucket(meeting, now)` exported from
`packages/web/src/lib/meetings-bucket.ts`. The helper SHALL be
called from the Kanban component during render with `now = new
Date()`.

`startOfToday` SHALL be computed in the user's local timezone:
`new Date(now.getFullYear(), now.getMonth(), now.getDate())`.

Each column SHALL render:

- A header with the bucket label and a count badge
  (e.g. "即將到來 · 3").
- A vertically-scrollable card list using the existing
  `MeetingGridCard` component shape (status bar, title,
  counterparty, time, duration).
- An empty-state hint ("此區段暫無會議" zh-TW / "No meetings in
  this bucket" en) when the bucket is empty.

The Kanban container SHALL use
`grid-template-columns: repeat(3, minmax(280px, 1fr))` so the
columns expand evenly across the page width while never collapsing
below card width. Each column body SHALL `overflow-y: auto` with a
max height of `calc(100dvh - 280px)`.

Drag-and-drop reordering / cross-column drops SHALL NOT be
supported in this iteration. Cards remain pure links to
/meetings/$id.

#### Scenario: Three-bucket distribution

- **GIVEN** the backend returns five meetings with the following shapes
  (using `now = 2026-05-12T10:00:00 local`):

  | id | status        | scheduled_start_at        |
  |----|---------------|---------------------------|
  | a  | in_progress   | 2026-04-01T09:00:00       |
  | b  | scheduled     | 2026-05-13T15:00:00       |
  | c  | scheduled     | 2026-05-25T15:00:00       |
  | d  | scheduled     | null                      |
  | e  | completed     | 2026-04-15T10:00:00       |

- **WHEN** the /meetings page renders
- **THEN** column 即將到來 SHALL contain meetings `a` and `b`
- **AND** column 未來 SHALL contain meetings `c` and `d`
- **AND** column 已結束 SHALL contain meeting `e`

#### Scenario: Overdue scheduled meeting falls into 已結束

- **GIVEN** a meeting with `status === "scheduled"` and
  `scheduled_start_at = 2026-05-01T15:00:00` and the current date
  is 2026-05-12
- **WHEN** the bucket is computed
- **THEN** the meeting SHALL land in 已結束, not 即將到來

#### Scenario: Empty bucket renders the localized empty hint

- **GIVEN** the user has no meetings in the 已結束 bucket
- **WHEN** the /meetings Kanban renders
- **THEN** the 已結束 column SHALL show its label and count badge "0"
- **AND** the column body SHALL render a centred hint reading
  "此區段暫無會議" (zh-TW)

#### Scenario: Helper handles invalid scheduled_start_at safely

- **GIVEN** a meeting where `scheduled_start_at` is a string that
  fails `Date.parse` (e.g. `"not-a-date"`)
- **WHEN** `getMeetingDateBucket` is called on that meeting
- **THEN** the helper SHALL return `"past"` as a safe default
- **AND** SHALL emit a `console.warn` in dev (when `import.meta.env.DEV`)

<!-- @trace
source: meetings-ux-revamp
updated: 2026-05-12
code:
  - packages/web/public/logo.png
  - packages/web/src/components/meeting-prev-next-nav.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/public/favicon.png
  - packages/web/src/index.css
  - packages/web/src/locales/en.json
  - packages/web/index.html
  - assets/meeting-playbook-logo-favicon.png
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/routes/meetings/new.tsx
  - assets/meeting-playbook-logo.png
  - packages/web/src/routes/login.tsx
tests:
  - packages/web/src/components/meetings-view-tabs.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
-->