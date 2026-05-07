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