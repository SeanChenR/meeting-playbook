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