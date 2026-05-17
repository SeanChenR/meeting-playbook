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

The free-form view's primary editor SHALL be a plain `<textarea>` containing the markdown source. Inside the free-form view, a sub-mode toggle SHALL switch between **two or three** sub-modes:

- **Edit** (default): the `<textarea>` is shown for editing markdown source.
- **Preview**: a read-only rendered view powered by `react-markdown` + `remark-gfm` + `rehype-sanitize`. Switching to Preview MUST NOT mutate the `<textarea>` value; switching back to Edit MUST restore the user's caret position to the beginning of the textarea (or an acceptable default — caret restoration is not strictly required).
- **Diff** (slice-23, conditional): a third sub-mode that SHALL render the line-level visual difference between `previous_free_form_markdown` and the current `free_form_markdown`, plus action buttons that map to the discard-previous / restore-previous / cherry-pick endpoints. The Diff toggle button SHALL appear in the sub-mode group only when `query.data?.has_previous_version === true`. When `has_previous_version === false`, the sub-mode toggle SHALL render exactly two buttons (Edit and Preview), matching the slice-7 / slice-20a contract.

Switching out of Diff mode SHALL NOT mutate the textarea value or the snapshot columns; only the explicit action buttons inside Diff mode mutate state.

#### Scenario: Two sub-mode buttons when no snapshot exists

- **GIVEN** a playbook detail page mounted for a row where `has_previous_version === false`
- **WHEN** the pane renders
- **THEN** the sub-mode toggle SHALL contain exactly two buttons: Edit and Preview

#### Scenario: Three sub-mode buttons when snapshot exists

- **GIVEN** a playbook detail page mounted for a row where `has_previous_version === true`
- **WHEN** the pane renders
- **THEN** the sub-mode toggle SHALL contain three buttons: Edit, Preview, and Diff

#### Scenario: Switching between sub-modes does not mutate state

- **GIVEN** the pane is in Diff mode with cherry-pick decisions made by the user
- **WHEN** the user clicks the Edit sub-mode toggle
- **THEN** the textarea value SHALL be the row's current `free_form_markdown` (unchanged from before entering Diff mode)
- **AND** the row's `previous_*` columns SHALL be unchanged


<!-- @trace
source: slice-23-playbook-versioning-and-diff
updated: 2026-05-17
code:
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - bun.lock
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/playbook-api.ts
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/web/package.json
  - packages/backend/meeting_playbook/calendar/schemas.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/lib/calendar-api.ts
  - docs/adr/0027-calendar-scope-link.md
  - packages/backend/meeting_playbook/playbooks/repository.py
tests:
  - packages/backend/tests/playbooks/test_router.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/backend/tests/calendar/test_get_event_endpoint.py
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
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

---
### Requirement: `PlaybookRead` schema exposes the previous-version snapshot

The `PlaybookRead` Pydantic schema returned by every playbook-bearing
endpoint (`GET /api/meetings/{meeting_id}/playbook`, regenerate response,
discard/restore response, and any future read) SHALL include three new
fields introduced by slice-23:

- `previous_free_form_markdown: str | None`
- `previous_updated_at: datetime | None`
- `has_previous_version: bool` (derived: `previous_free_form_markdown is not None`)

The full row shape SHALL be returned on every call so the frontend never
has to fetch a second time to learn the snapshot state.

#### Scenario: GET on row without snapshot returns null previous fields

- **GIVEN** a freshly-created playbook row (no regenerate has happened)
- **WHEN** `GET /api/meetings/{meeting_id}/playbook` is called
- **THEN** the JSON response includes `"previous_free_form_markdown": null`,
  `"previous_updated_at": null`, and `"has_previous_version": false`

#### Scenario: GET on row with snapshot returns full previous fields

- **GIVEN** a row whose `previous_free_form_markdown = "draft v1"` and
  `previous_updated_at = "2026-05-17T10:00:00+00:00"`
- **WHEN** `GET /api/meetings/{meeting_id}/playbook` is called
- **THEN** the JSON response includes
  `"previous_free_form_markdown": "draft v1"`,
  `"previous_updated_at": "2026-05-17T10:00:00+00:00"`, and
  `"has_previous_version": true`


<!-- @trace
source: slice-23-playbook-versioning-and-diff
updated: 2026-05-17
code:
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - bun.lock
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/playbook-api.ts
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/web/package.json
  - packages/backend/meeting_playbook/calendar/schemas.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/lib/calendar-api.ts
  - docs/adr/0027-calendar-scope-link.md
  - packages/backend/meeting_playbook/playbooks/repository.py
tests:
  - packages/backend/tests/playbooks/test_router.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/backend/tests/calendar/test_get_event_endpoint.py
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
-->

---
### Requirement: User-save upsert preserves the previous-version snapshot

`PlaybookRepository.upsert_for_meeting(meeting_id, payload)` — the
user-save path invoked by `PUT /api/meetings/{meeting_id}/playbook` —
SHALL NOT modify the three `previous_*` columns introduced by slice-23.
Only the regenerate path (`snapshot_then_upsert`) and the explicit
`discard_previous` / `restore_previous` endpoints SHALL touch them.

This separation guarantees the snapshot always refers to the version
that existed immediately before the last AI regeneration — never an
arbitrary middle save.

#### Scenario: Save after regenerate keeps snapshot intact

- **GIVEN** a row where `free_form_markdown = "v2"` and
  `previous_free_form_markdown = "v1"`
- **WHEN** the user edits the freeform text and PUTs an upsert with
  `free_form_markdown = "v2-edited"`
- **THEN** the row's `free_form_markdown` is `"v2-edited"`
- **AND** the row's `previous_free_form_markdown` is still `"v1"`
- **AND** the row's `previous_updated_at` is unchanged

<!-- @trace
source: slice-23-playbook-versioning-and-diff
updated: 2026-05-17
code:
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - bun.lock
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/lib/playbook-api.ts
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/web/package.json
  - packages/backend/meeting_playbook/calendar/schemas.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/lib/calendar-api.ts
  - docs/adr/0027-calendar-scope-link.md
  - packages/backend/meeting_playbook/playbooks/repository.py
tests:
  - packages/backend/tests/playbooks/test_router.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/backend/tests/calendar/test_get_event_endpoint.py
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
-->