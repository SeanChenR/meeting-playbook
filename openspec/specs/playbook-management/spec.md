# playbook-management Specification

## Purpose

TBD - created by archiving change 'slice-04-playbook-editor'. Update Purpose after archive.

## Requirements

### Requirement: Each meeting has at most one playbook scoped to that meeting

A playbook record SHALL carry a non-nullable foreign key to `meeting.id` and a UNIQUE constraint on `meeting_id`, enforcing a one-to-one relationship. The playbook lifecycle MUST be tied to the meeting via `ON DELETE CASCADE`: deleting the meeting removes the playbook, and no orphan playbook rows can exist.

#### Scenario: Inserting a second playbook for the same meeting fails

- **GIVEN** a meeting with id `m_xyz` already has a playbook
- **WHEN** the system attempts to insert another playbook row with `meeting_id = m_xyz`
- **THEN** the database SHALL reject the insert due to the UNIQUE constraint

#### Scenario: Deleting a meeting cascades to its playbook

- **GIVEN** meeting `m_xyz` exists with a non-empty playbook
- **WHEN** the meeting row is deleted
- **THEN** the playbook row for `m_xyz` SHALL no longer exist in the database


<!-- @trace
source: slice-04-playbook-editor
updated: 2026-05-08
code:
  - packages/backend/alembic/versions/0002_create_playbook.py
  - packages/web/src/locales/en.json
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/backend/meeting_playbook/playbooks/__init__.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - docs/agents/meetings.md
tests:
  - packages/backend/tests/playbooks/test_validation.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/web/src/lib/playbook-api.mutations.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/playbooks/__init__.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/backend/tests/playbooks/test_repository.py
-->

---
### Requirement: Playbook access is gated by meeting ownership

The playbook endpoints `GET /api/meetings/{id}/playbook` and `PUT /api/meetings/{id}/playbook` MUST resolve the requesting user via the `X-User-Id` header (the gateway-injected identity) and MUST verify that the user owns the meeting via the `MeetingRepository` ownership check before any playbook read or write. When the meeting does not exist OR exists but is owned by another user, the response SHALL be HTTP 404 with `error_code: meeting.not_found` and the body MUST NOT distinguish between the two cases. The playbook itself SHALL NOT carry a separate user_id column or ACL.

#### Scenario: Reading another user's playbook returns 404

- **GIVEN** a meeting with id `m_xyz` owned by user B and a playbook for that meeting
- **WHEN** user A sends `GET /api/meetings/m_xyz/playbook`
- **THEN** the response status SHALL be HTTP 404 with `error_code: meeting.not_found` and the response body MUST NOT reveal that the playbook exists

#### Scenario: Writing another user's playbook returns 404 and persists nothing

- **GIVEN** meeting `m_xyz` is owned by user B
- **WHEN** user A sends `PUT /api/meetings/m_xyz/playbook` with a non-empty body
- **THEN** the response status SHALL be HTTP 404 and the playbook for `m_xyz` MUST be unchanged

#### Scenario: Owner can read and write their playbook

- **GIVEN** meeting `m_own` is owned by user A
- **WHEN** user A sends `GET /api/meetings/m_own/playbook` followed by `PUT /api/meetings/m_own/playbook` with a payload
- **THEN** the GET SHALL return HTTP 200 and the PUT SHALL return HTTP 200 with the persisted playbook reflecting the payload


<!-- @trace
source: slice-04-playbook-editor
updated: 2026-05-08
code:
  - packages/backend/alembic/versions/0002_create_playbook.py
  - packages/web/src/locales/en.json
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/backend/meeting_playbook/playbooks/__init__.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - docs/agents/meetings.md
tests:
  - packages/backend/tests/playbooks/test_validation.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/web/src/lib/playbook-api.mutations.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/playbooks/__init__.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/backend/tests/playbooks/test_repository.py
-->

---
### Requirement: GET auto-creates an empty playbook on first read

The `GET /api/meetings/{id}/playbook` endpoint SHALL return HTTP 200 with a complete playbook record on every authorized read, including the very first read for a meeting that has never had a playbook stored. When no playbook row exists for the meeting, the backend MUST insert a fresh row with the seven content fields set to the empty string and return that row, rather than responding with HTTP 404. This ensures the editor UI always has an editable surface.

#### Scenario: First GET returns a fully-formed empty playbook

- **GIVEN** meeting `m_fresh` is owned by user A and has no playbook row
- **WHEN** user A sends `GET /api/meetings/m_fresh/playbook`
- **THEN** the response status SHALL be HTTP 200 and the body SHALL contain `free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, and `red_lines` all equal to the empty string

#### Scenario: Subsequent GET returns the same row id, not a new one

- **GIVEN** meeting `m_fresh` had its playbook auto-created in a prior GET
- **WHEN** user A sends a second `GET /api/meetings/m_fresh/playbook`
- **THEN** the response body SHALL contain the same playbook `id` as the first response


<!-- @trace
source: slice-04-playbook-editor
updated: 2026-05-08
code:
  - packages/backend/alembic/versions/0002_create_playbook.py
  - packages/web/src/locales/en.json
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/backend/meeting_playbook/playbooks/__init__.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - docs/agents/meetings.md
tests:
  - packages/backend/tests/playbooks/test_validation.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/web/src/lib/playbook-api.mutations.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/playbooks/__init__.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/backend/tests/playbooks/test_repository.py
-->

---
### Requirement: PUT performs a full upsert with seven content fields

The `PUT /api/meetings/{id}/playbook` endpoint SHALL accept a JSON body with up to seven optional string fields: `free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`. Each missing field MUST be treated as the empty string. The endpoint MUST persist the supplied values as a complete replacement of the row's content fields (full upsert, no PATCH semantics) and MUST update `updated_at` to the current server time on every successful write. The response SHALL be HTTP 200 with the persisted playbook.

#### Scenario: Full payload persists and returns the same values

- **WHEN** user A sends `PUT /api/meetings/m_own/playbook` with body `{"free_form_markdown": "# Brief", "objective": "Close Q3 deal", "counterparty_profile": "林經理", "anticipated_topics": "pricing", "anticipated_objections": "budget", "talking_points": "value prop", "red_lines": "no discount below 30%"}`
- **THEN** the response status SHALL be HTTP 200 and the response body SHALL contain those seven values verbatim

#### Scenario: Missing fields are persisted as empty strings

- **GIVEN** the playbook for `m_own` previously had `objective = "old goal"`
- **WHEN** user A sends `PUT /api/meetings/m_own/playbook` with body `{"free_form_markdown": "new body"}` (other six fields omitted)
- **THEN** the persisted playbook SHALL have `free_form_markdown` equal to `"new body"` and the other six fields equal to the empty string

##### Example: full upsert vs missing-field replacement

| Body sent on PUT | Resulting `objective` | Resulting `red_lines` |
| ----- | ----- | ----- |
| `{"objective": "X", "red_lines": "Y"}` | `"X"` | `"Y"` |
| `{"objective": "X"}` (no red_lines key) | `"X"` | `""` |
| `{}` (empty object) | `""` | `""` |

#### Scenario: updated_at advances on each PUT

- **GIVEN** the playbook for `m_own` was last written at time T1 with `updated_at = T1`
- **WHEN** user A sends `PUT /api/meetings/m_own/playbook` at time T2 (T2 > T1)
- **THEN** the response body's `updated_at` SHALL be greater than or equal to T2 and strictly greater than T1


<!-- @trace
source: slice-04-playbook-editor
updated: 2026-05-08
code:
  - packages/backend/alembic/versions/0002_create_playbook.py
  - packages/web/src/locales/en.json
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/backend/meeting_playbook/playbooks/__init__.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - docs/agents/meetings.md
tests:
  - packages/backend/tests/playbooks/test_validation.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/web/src/lib/playbook-api.mutations.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/playbooks/__init__.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/backend/tests/playbooks/test_repository.py
-->

---
### Requirement: Playbook content fields accept arbitrary markdown including Chinese-English mix

Each of the seven content fields SHALL accept any UTF-8 string up to a backend-imposed maximum reasonable for application use (no hard upper bound below 100KB per field). Storage and retrieval MUST preserve the bytes verbatim, including markdown syntax (headings, bullet lists, code fences), CJK characters, emoji, and inline mixed-language passages.

#### Scenario: Mixed-language markdown round-trips

- **WHEN** user A sends `PUT /api/meetings/m_own/playbook` with `objective` set to a 200-character string containing zh-TW characters, English words, and a markdown list
- **THEN** a subsequent GET SHALL return the same `objective` byte-for-byte

#### Scenario: Long markdown body persists

- **WHEN** user A sends a `free_form_markdown` value containing 60+ lines of mixed text, headings, and bullet lists
- **THEN** the GET response SHALL return the full body unchanged


<!-- @trace
source: slice-04-playbook-editor
updated: 2026-05-08
code:
  - packages/backend/alembic/versions/0002_create_playbook.py
  - packages/web/src/locales/en.json
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/backend/meeting_playbook/playbooks/__init__.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - docs/agents/meetings.md
tests:
  - packages/backend/tests/playbooks/test_validation.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/web/src/lib/playbook-api.mutations.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/playbooks/__init__.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/backend/tests/playbooks/test_repository.py
-->

---
### Requirement: PlaybookPane UI exposes a free-form view, a structured view, and a save action

The web UI SHALL provide a `PlaybookPane` component that the meeting detail page mounts. The component SHALL render a top-level view-mode toggle with two states: a free-form view that exposes a single editor for `free_form_markdown`, and a structured view that exposes six labeled editors, one per structured field (`objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`).

The free-form view's primary editor SHALL be a plain `<textarea>` containing the markdown source. Inside the free-form view, a SECOND smaller toggle SHALL switch between two sub-modes:
- **Edit** (default): the `<textarea>` is shown for editing markdown source.
- **Preview**: a read-only rendered view powered by `react-markdown` + `remark-gfm` + `rehype-sanitize`. Switching to Preview MUST NOT mutate the `<textarea>` value; switching back to Edit MUST restore the user's caret position to the beginning of the textarea (or an acceptable default — caret restoration is not strictly required).

The DB storage format for `free_form_markdown` SHALL remain markdown text (no schema change); the textarea writes the value verbatim, and Preview never mutates it. Switching between free-form and structured views MUST NOT discard any unsaved edits in either view. A save action MUST send a single PUT request carrying the current values of all seven fields and MUST refresh the displayed content after the response succeeds.

The free-form view MUST NOT render a TipTap WYSIWYG editor or any toolbar of formatting buttons. Markdown is typed directly in the textarea using standard markdown syntax (`**bold**`, `# Heading`, `- bullet`, etc.).

#### Scenario: Toggle preserves unsaved edits in both views

- **GIVEN** the user has typed text into the free-form `<textarea>` and into the structured `objective` field, neither saved
- **WHEN** the user toggles to the structured view, then back to free-form
- **THEN** both the free-form text (in the textarea) and the structured `objective` text SHALL still be present

#### Scenario: Save dispatches a PUT and refreshes the displayed content

- **GIVEN** the user has typed values into all seven fields (free-form value typed directly as markdown into the textarea)
- **WHEN** the user clicks the save button
- **THEN** the component SHALL issue exactly one `PUT /api/meetings/{id}/playbook` request whose body contains all seven fields with the typed values; the `free_form_markdown` field's value SHALL equal the textarea's current `value` property byte-for-byte; the component SHALL display those values after the response resolves

#### Scenario: Preview sub-toggle renders rendered markdown without mutating the source

- **GIVEN** the meeting's `free_form_markdown` field is stored in the database as `"# Goals\n\n- Discuss Q3 numbers\n- **Confirm deadlines**"`
- **WHEN** the playbook detail loads, the user opens the free-form view, and clicks the Preview sub-toggle
- **THEN** the rendered output SHALL contain an H1 reading "Goals", followed by an unordered list with two items, the second of which contains a bold "Confirm deadlines" run; the underlying `<textarea>`'s `value` MUST remain the original markdown source unchanged

#### Scenario: Free-form view exposes Edit/Preview sub-toggle (no formatting toolbar)

- **GIVEN** the free-form view is visible
- **WHEN** the page renders
- **THEN** the view SHALL contain a sub-toggle with exactly two options labeled via `playbook.freeform.editTab` and `playbook.freeform.previewTab` i18n keys; the view MUST NOT render any TipTap editor instance, formatting toolbar, or `playbook.toolbar.*` i18n keys


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
### Requirement: All UI strings live in both locale files

Every user-visible string introduced by the playbook editor (view-toggle labels, field labels, save button label, save-status indicator, error fallback messages) MUST exist in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json` under a `playbook.*` namespace. The deep-equal locale mirror test enforces that no key may live in only one file.

#### Scenario: Adding a field label to only one locale fails CI

- **GIVEN** a developer adds `playbook.fields.objective` to `zh-TW.json` only
- **WHEN** the locale-mirror test in `locales.test.ts` runs
- **THEN** the test SHALL fail with a key-tree mismatch

<!-- @trace
source: slice-04-playbook-editor
updated: 2026-05-08
code:
  - packages/backend/alembic/versions/0002_create_playbook.py
  - packages/web/src/locales/en.json
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/backend/meeting_playbook/playbooks/__init__.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - docs/agents/meetings.md
tests:
  - packages/backend/tests/playbooks/test_validation.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/web/src/lib/playbook-api.mutations.test.tsx
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/playbooks/__init__.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/backend/tests/playbooks/test_repository.py
-->