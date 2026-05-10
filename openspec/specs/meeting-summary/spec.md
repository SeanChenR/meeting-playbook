# meeting-summary Specification

## Purpose

TBD - created by archiving change 'slice-10-post-meeting-summary'. Update Purpose after archive.

## Requirements

### Requirement: summary table persists per-meeting markdown summary

The backend SHALL provide a `summary` table (Alembic migration `0006_create_summary`) with exactly four columns: `id` (TEXT primary key, format `sm_<token>`), `meeting_id` (TEXT, NOT NULL, UNIQUE, foreign key to `meeting.id` ON DELETE CASCADE), `markdown` (TEXT, NOT NULL), and `generated_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `now()`). The `UNIQUE (meeting_id)` constraint enforces a 1:1 relationship between meeting and summary. Deleting a `meeting` row SHALL cascade-delete the associated `summary` row.

The backend SHALL provide `SummaryRepository` at `packages/backend/meeting_playbook/summarization/repository.py` as the SOLE access path for `summary` rows. The repository SHALL expose `get_for_meeting(meeting_id) -> Summary | None`, `get_with_stale_flag(meeting_id) -> SummaryWithStale | None` (returns the row plus a computed `is_stale` boolean derived from comparing `generated_at` against the latest `transcript_chunk.created_at`, `playbook.updated_at`, and `chat_message.created_at`), and `upsert(meeting_id, markdown) -> Summary` (uses PostgreSQL `INSERT ... ON CONFLICT (meeting_id) DO UPDATE SET markdown = EXCLUDED.markdown, generated_at = now() RETURNING *`). The repository SHALL NOT expose any delete method.

#### Scenario: summary row cascade-deletes with the parent meeting

- **GIVEN** a meeting with one `summary` row
- **WHEN** the meeting row is deleted
- **THEN** the `summary` row SHALL be deleted by FK cascade

#### Scenario: upsert replaces existing markdown atomically

- **GIVEN** a meeting whose summary was generated yesterday with markdown "v1"
- **WHEN** `repo.upsert(meeting_id, markdown="v2")` runs
- **THEN** the database SHALL contain exactly one summary row for the meeting with `markdown = "v2"` and `generated_at` updated to now (within 1 second tolerance)

#### Scenario: get_with_stale_flag returns is_stale=true when transcript newer than generated_at

- **GIVEN** a meeting with a summary generated at T0 AND a transcript_chunk inserted at T0+10s
- **WHEN** `repo.get_with_stale_flag(meeting_id)` runs
- **THEN** the returned object's `is_stale` SHALL be `True`

#### Scenario: get_with_stale_flag returns is_stale=false when nothing changed after generation

- **GIVEN** a meeting with summary generated at T0 AND no transcript / playbook / chat_message rows newer than T0
- **WHEN** `repo.get_with_stale_flag(meeting_id)` runs
- **THEN** the returned object's `is_stale` SHALL be `False`

#### Scenario: get_for_meeting on missing summary returns None

- **GIVEN** a meeting that has never been summarized
- **WHEN** `repo.get_for_meeting(meeting_id)` runs
- **THEN** the call SHALL return `None`


<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: MeetingSummarizer module exposes a single coroutine summarize()

The backend SHALL provide a `MeetingSummarizer` Protocol (and a concrete `VertexProSummarizer` implementation) located at `packages/backend/meeting_playbook/summarization/`. The Protocol's single coroutine `summarize(meeting_id: str) -> str` SHALL return the full markdown summary as a single string when generation succeeds. The Protocol SHALL be the SOLE entry point used by `summarization/runtime.py` to invoke the underlying LLM; no other module MAY import any Vertex / `google-genai` symbol directly.

The concrete `VertexProSummarizer` SHALL wrap the official `google-genai` SDK against Vertex AI. The model id SHALL come from `Settings.vertex_pro_model_id` (default `gemini-2.5-pro`). The implementation SHALL apply a 90-second outer `asyncio.timeout` so a hung Vertex stream raises `asyncio.TimeoutError` rather than blocking the background task indefinitely. The implementation SHALL fetch context (transcript chunks via `SessionRepository.list_chunks_for_meeting`, playbook via `PlaybookRepository.get_or_create_for_meeting`, chat history via `ChatMessageRepository.list_for_meeting`) inside its own `async with session_factory() as ...` scope; the LLM call itself SHALL run OUTSIDE the session block (no DB connection held during the LLM round-trip).

The implementation SHALL validate that the returned markdown contains exactly four required headings (case- and trim-insensitive match) in fixed order. Missing or out-of-order headings SHALL raise `SummaryFormatError`; the runtime treats this same as a Vertex failure (no upsert).

#### Scenario: summarize returns markdown with all four required sections

- **GIVEN** a mocked Vertex client returning markdown that contains "## 重點討論", "## 決議", "## Action items", and "## 待解決問題" in order
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL return that markdown string verbatim

#### Scenario: 90-second cap on Vertex call raises TimeoutError

- **GIVEN** a mocked Vertex client that sleeps 100 seconds before returning
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL raise `asyncio.TimeoutError` between 90.0 and 92.0 seconds after invocation

#### Scenario: Missing required heading raises SummaryFormatError

- **GIVEN** a mocked Vertex client returning markdown that omits the "## 決議" heading
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL raise `SummaryFormatError` (which the runtime catches and treats as a generation failure — no upsert, log warning, pop in-flight)


<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: Summary prompt assembles 4 fixed sections with locale-aware headings

The summarizer's prompt builder SHALL produce a system instruction that explicitly enumerates the four required heading texts in the requested locale and forbids the model from changing heading text or order, skipping a heading, inventing facts beyond the supplied context, or wrapping the four sections in additional summary paragraphs. The user message SHALL include four labeled sections in fixed order: meeting metadata (title, counterparty / me display names), playbook (only non-empty structured fields plus `free_form_markdown` if non-empty; whole playbook absent renders the locale's `(尚未填寫)` / `(empty playbook)` placeholder), full transcript (every `transcript_chunk` ordered ascending by `started_at` formatted as `{display_name}：{text} ({HH:mm:ss})`), and chat history (slice-9 `chat_message` rows ordered ascending by `created_at`; rendered as `{me_display_name}: {content}` for user role and `Advisor: {content}` for advisor role; empty renders the locale's `(無)` / `(none)` placeholder).

The four heading texts per locale are EXACTLY:
- zh-TW: `## 重點討論`, `## 決議`, `## Action items`, `## 待解決問題`
- en: `## Key discussion points`, `## Decisions`, `## Action items`, `## Open questions`

Action items inside section 3 SHALL render as bullet items in the format `- [{owner_or_TBD}] {action}`; owner extraction is the model's responsibility based on transcript content; unknown owners default to literal `TBD`.

#### Scenario: System instruction lists the 4 zh-TW headings verbatim

- **WHEN** `build_system_instruction(locale="zh-TW")` runs
- **THEN** the returned string SHALL contain the literal substrings `## 重點討論`, `## 決議`, `## Action items`, and `## 待解決問題` AND SHALL contain a phrase forbidding the model from changing heading text or order

#### Scenario: System instruction lists the 4 en headings verbatim

- **WHEN** `build_system_instruction(locale="en")` runs
- **THEN** the returned string SHALL contain the literal substrings `## Key discussion points`, `## Decisions`, `## Action items`, and `## Open questions`

#### Scenario: User message includes meeting metadata, playbook, transcript, and chat history sections in order

- **GIVEN** a meeting with non-empty playbook, 3 transcript chunks, and 1 chat exchange
- **WHEN** `build_user_message(meeting, playbook, chunks, chat_history, locale="zh-TW")` runs
- **THEN** the returned string SHALL contain `## 會議基本資料`, `## Playbook`, `## 整場 Transcript`, and `## In-meeting Advisor 對話` in that order

#### Scenario: Empty chat_history renders the localised placeholder

- **GIVEN** a first-time-summarized meeting with zero `chat_message` rows
- **WHEN** `build_user_message(..., chat_history=[], locale="zh-TW")` runs
- **THEN** the `## In-meeting Advisor 對話` section's body SHALL be the literal `(無)`


<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: Summary generation runtime serializes per-meeting work via in-process registry

The backend SHALL provide `summarization/runtime.py` exposing `spawn_summary_task(meeting_id) -> bool` and `is_pending(meeting_id) -> bool`. The module SHALL maintain a process-scoped `dict[str, asyncio.Task]` mapping meeting_id to the in-flight summary task; access SHALL be guarded by an `asyncio.Lock` to prevent races between concurrent spawn calls. `spawn_summary_task` SHALL return `True` and create a new task when no in-flight task exists for the meeting; SHALL return `False` (no new task created) when an in-flight task is present and not done. `is_pending` SHALL return `True` iff the registry holds an unfinished task for the meeting.

The spawned task SHALL invoke `MeetingSummarizer.summarize(meeting_id)`, then `SummaryRepository.upsert(...)` on success. On any exception (`asyncio.TimeoutError`, `SummaryFormatError`, generic `Exception`) the task SHALL log the full traceback via `logger.exception` and SHALL NOT call `upsert`. The task's `finally` clause SHALL pop the meeting_id from the registry regardless of outcome.

Process restart loses the in-flight registry entirely; this is acceptable because the task itself dies with the process and no row was written, leaving a consistent "no summary, can regenerate" UI state.

#### Scenario: Concurrent spawn calls — second returns False without creating a task

- **GIVEN** an empty registry
- **WHEN** two coroutines call `spawn_summary_task("m_x")` simultaneously
- **THEN** exactly one call SHALL return `True` and create a task; the other call SHALL return `False`

#### Scenario: Successful generation upserts then pops registry

- **GIVEN** a registered task running `summarizer.summarize("m_x")` that returns valid markdown
- **WHEN** the task completes
- **THEN** the database SHALL contain a `summary` row for "m_x" AND `is_pending("m_x")` SHALL return `False`

#### Scenario: Failed generation skips upsert but still pops registry

- **GIVEN** a registered task whose `summarize` raises `asyncio.TimeoutError`
- **WHEN** the task's exception path runs
- **THEN** the database SHALL have ZERO new `summary` rows for the meeting AND `is_pending("m_x")` SHALL return `False` AND the backend log SHALL contain the traceback


<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: POST /api/meetings/{id}/summary triggers regeneration with busy-aware response

The backend SHALL expose `POST /api/meetings/{meeting_id}/summary` (mounted by `summarization/router.py`) requiring the gateway-injected `X-User-Id` header. The endpoint SHALL verify ownership via `MeetingRepository.get_for_user`; non-owner / non-existent meeting SHALL return HTTP 404 with the standard flat envelope `{error_code: "meeting.not_found", message: "Meeting not found"}`. Missing `X-User-Id` SHALL return HTTP 401 with `{error_code: "auth.gateway_bypass", ...}`.

When a summary task is already in-flight for the meeting (`runtime.is_pending(meeting_id) == True`), the endpoint SHALL return HTTP 409 with `{error_code: "summary.busy", message: "A summary generation is already running for this meeting"}` and SHALL NOT spawn a second task. When no in-flight task exists, the endpoint SHALL call `runtime.spawn_summary_task(meeting_id)` and return HTTP 202 with body `{status: "pending"}`.

#### Scenario: Owner POST on idle meeting spawns task and returns 202

- **GIVEN** a meeting belonging to user `u_a` with no in-flight summary
- **WHEN** `u_a` issues `POST /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 202 with body `{"status": "pending"}` AND `runtime.is_pending(meeting_id)` SHALL return `True`

#### Scenario: POST while summary already in-flight returns 409 summary.busy

- **GIVEN** a meeting whose summary task is already in-flight
- **WHEN** the owner POSTs again
- **THEN** the response SHALL be HTTP 409 with body `{"error_code": "summary.busy", ...}` AND no second task SHALL be spawned

#### Scenario: Non-owner POST returns 404 meeting.not_found

- **GIVEN** a meeting belonging to user `u_a`
- **WHEN** user `u_b` issues `POST /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 404 with body `{"error_code": "meeting.not_found", ...}`


<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: GET /api/meetings/{id}/summary returns three states (present / pending / not_found)

The backend SHALL expose `GET /api/meetings/{meeting_id}/summary` requiring the gateway-injected `X-User-Id` header. Ownership / auth gates match the POST endpoint. The response shape SHALL be one of:

(a) Summary row exists → HTTP 200 with body `{id, meeting_id, markdown, generated_at, is_stale}` where `is_stale` is the boolean computed by `SummaryRepository.get_with_stale_flag` (see scenario 3 of the chat_message persistence requirement).

(b) Summary row absent BUT `runtime.is_pending(meeting_id) == True` → HTTP 200 with body `{status: "pending", generated_at: null}`.

(c) Summary row absent AND no in-flight task → HTTP 404 with body `{error_code: "summary.not_found", message: "No summary has been generated for this meeting"}`.

The response SHALL never embed transcript / playbook / chat_message data; clients fetch those separately if needed.

#### Scenario: Owner GET on completed meeting returns the persisted summary

- **GIVEN** a meeting belonging to user `u_a` with a persisted summary row
- **WHEN** `u_a` issues `GET /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 200 with body keys `id`, `meeting_id`, `markdown`, `generated_at`, `is_stale`

#### Scenario: Owner GET while generation is in-flight returns the pending shape

- **GIVEN** a meeting whose summary task is in-flight AND no row exists yet
- **WHEN** `u_a` issues `GET /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 200 with body `{"status": "pending", "generated_at": null}`

#### Scenario: Owner GET on never-summarized meeting returns 404 summary.not_found

- **GIVEN** a meeting with no summary row and no in-flight task
- **WHEN** `u_a` issues `GET /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 404 with body `{"error_code": "summary.not_found", ...}`

<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->