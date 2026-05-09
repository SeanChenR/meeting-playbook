# playbook-generation Specification

## Purpose

TBD - created by archiving change 'slice-05-calendar-llm-playbook'. Update Purpose after archive.

## Requirements

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


<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->

---
### Requirement: Generator uses Vertex AI Gemini 2.5 Pro through the official SDK

The generator SHALL invoke the Gemini 2.5 Pro model on Vertex AI through the `google-genai` SDK with structured-output mode (response schema enforcing the seven string fields). The generator SHALL NOT call any non-Vertex-AI provider, and SHALL NOT bypass the SDK by issuing raw HTTP requests. Authentication MUST flow through Application Default Credentials so deployments can swap service accounts without code changes.

#### Scenario: Non-Vertex provider is forbidden

- **WHEN** the generator code is reviewed
- **THEN** there MUST be no import of, nor HTTP call to, providers other than Vertex AI's Gemini family

#### Scenario: Structured-output schema is enforced

- **WHEN** the generator builds its request to Gemini 2.5 Pro
- **THEN** the request SHALL include a JSON response schema with exactly the seven string keys defined by `playbook-management`


<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->

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


<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->

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

<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->