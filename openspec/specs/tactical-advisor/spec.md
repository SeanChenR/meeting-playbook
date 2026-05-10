# tactical-advisor Specification

## Purpose

TBD - created by archiving change 'slice-08-tactical-advisor'. Update Purpose after archive.

## Requirements

### Requirement: TacticalAdvisor module exposes a streaming advise() coroutine

The backend SHALL provide a `TacticalAdvisor` Protocol (and a concrete `VertexFlashAdvisor` implementation) located at `packages/backend/meeting_playbook/advisor/`. The Protocol's single coroutine `advise(meeting_id, recent_chunks, playbook, me_display_name, counterparty_display_name, user_question, locale) -> AsyncIterator[str]` SHALL yield text segments as they arrive from the underlying LLM stream. The Protocol SHALL be the SOLE entry point used by `sessions/router.py` to invoke the advisor; the router MUST NOT import any Vertex / `google-genai` symbol directly.

The concrete `VertexFlashAdvisor` SHALL wrap the official `google-genai` SDK's `aio.models.generate_content_stream(...)` call. Each SDK chunk's `chunk.text` SHALL be yielded verbatim as one string. The model id SHALL come from `Settings.vertex_flash_model_id` (default `gemini-2.0-flash-001`). Generation parameters SHALL be `temperature=0.4`, `max_output_tokens=400`, default `top_p`. The provider SHALL apply a 15-second outer `asyncio.timeout` so a hung Vertex stream raises `asyncio.TimeoutError` rather than blocking the WebSocket session indefinitely.

#### Scenario: advise yields one string per SDK chunk

- **GIVEN** a mocked Vertex stream that produces three chunks with `chunk.text` equal to `"建議一"`, `"建議二"`, `"建議三"`
- **WHEN** the caller iterates `async for token in advisor.advise(...)`
- **THEN** the iterator SHALL yield exactly the three strings in that order

#### Scenario: 15-second cap on the outer stream raises TimeoutError

- **GIVEN** a mocked Vertex stream that sleeps 20 seconds before yielding
- **WHEN** the caller iterates `async for token in advisor.advise(...)`
- **THEN** the iterator SHALL raise `asyncio.TimeoutError` between 15.0 and 16.0 seconds after the call begins


<!-- @trace
source: slice-08-tactical-advisor
updated: 2026-05-10
code:
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/meeting_playbook/advisor/__init__.py
  - packages/backend/meeting_playbook/advisor/base.py
  - .env.example
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/advisor/dependencies.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - docs/agents/advisor.md
  - packages/web/src/components/advisor-pane.tsx
tests:
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/backend/tests/meetings/test_dependencies.py
  - packages/backend/tests/sessions/test_repository.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/__init__.py
  - packages/backend/tests/advisor/test_dependencies.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Advice context assembly uses the last 60 seconds of transcript and non-empty playbook fields

The advisor SHALL receive (a) all `transcript_chunk` rows for the meeting whose `started_at` falls within the last 60 seconds (`started_at >= now() - INTERVAL '60 seconds'`), ordered by `started_at` ascending, and (b) the meeting's `playbook` row with all 7 content fields available. The user-message portion of the prompt SHALL render the chunks as a dialogue (`{display_name}：{text} ({HH:mm:ss})`) using the meeting's `me_display_name` and `counterparty_display_name`. Only NON-EMPTY playbook structured fields SHALL be interpolated as Markdown headings; the `free_form_markdown` field SHALL be appended after the structured headings only when non-empty. When the transcript window contains zero chunks, the prompt SHALL render `(無對話內容)` (or its English equivalent when locale is `en`). When all 7 playbook fields are empty, the prompt SHALL render `(尚未填寫)`.

The `SessionRepository` SHALL expose `list_chunks_last_60s(meeting_id) -> list[TranscriptChunk]` as the single SQL access path for this window.

#### Scenario: 60-second window excludes older chunks

- **GIVEN** a meeting with five transcript chunks at `now()-30s`, `-50s`, `-70s`, `-90s`, `-120s`
- **WHEN** `list_chunks_last_60s(meeting_id)` runs
- **THEN** it SHALL return exactly the two chunks at `now()-30s` and `now()-50s`, ordered ascending by `started_at`

#### Scenario: Dialogue uses the meeting's display names

- **GIVEN** chunks with `speaker = "me"` and `speaker = "counterparty"`, with the meeting's `me_display_name = "Sean"` and `counterparty_display_name = "林經理"`
- **WHEN** the prompt's user-message section is built
- **THEN** the section SHALL contain a `Sean：...` line for each `me` chunk and a `林經理：...` line for each `counterparty` chunk, ordered by `started_at` ascending

#### Scenario: Empty fields are omitted, not rendered as empty headings

- **GIVEN** a playbook where only `objective` and `free_form_markdown` are non-empty
- **WHEN** the prompt's user-message section is built
- **THEN** the section SHALL contain a `## 目標` heading with the objective text and the free-form text below; it SHALL NOT contain headings for `對方輪廓`, `預期主題`, `預期反對`, `談話要點`, or `紅線`

#### Scenario: Empty inputs render explicit placeholders

- **GIVEN** a meeting with zero chunks in the last 60 seconds AND a fully empty playbook
- **WHEN** the prompt's user-message section is built (locale `zh-TW`)
- **THEN** the section SHALL contain the literal `(無對話內容)` and `(尚未填寫)` strings so the model is signalled to respond honestly rather than hallucinate


<!-- @trace
source: slice-08-tactical-advisor
updated: 2026-05-10
code:
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/meeting_playbook/advisor/__init__.py
  - packages/backend/meeting_playbook/advisor/base.py
  - .env.example
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/advisor/dependencies.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - docs/agents/advisor.md
  - packages/web/src/components/advisor-pane.tsx
tests:
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/backend/tests/meetings/test_dependencies.py
  - packages/backend/tests/sessions/test_repository.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/__init__.py
  - packages/backend/tests/advisor/test_dependencies.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Advice output language follows the request_advice frame's locale field

The `request_advice` WebSocket frame SHALL include a required `locale` field of type `Literal["zh-TW", "en"]` (default `"zh-TW"`). The advisor's `system_instruction` SHALL include a per-locale directive: `請用繁體中文（zh-TW）回答。` for `zh-TW` or `Reply in English.` for `en`. The frontend SHALL set `locale` from `i18n.language` at the moment of click.

#### Scenario: locale=en yields an English directive in system_instruction

- **WHEN** `advise(..., locale="en")` is called
- **THEN** the `system_instruction` argument passed to Vertex SHALL contain the substring `Reply in English.`

#### Scenario: locale=zh-TW yields a Mandarin directive

- **WHEN** `advise(..., locale="zh-TW")` is called
- **THEN** the `system_instruction` argument passed to Vertex SHALL contain the substring `請用繁體中文`


<!-- @trace
source: slice-08-tactical-advisor
updated: 2026-05-10
code:
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/meeting_playbook/advisor/__init__.py
  - packages/backend/meeting_playbook/advisor/base.py
  - .env.example
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/advisor/dependencies.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - docs/agents/advisor.md
  - packages/web/src/components/advisor-pane.tsx
tests:
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/backend/tests/meetings/test_dependencies.py
  - packages/backend/tests/sessions/test_repository.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/__init__.py
  - packages/backend/tests/advisor/test_dependencies.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Advisor exposes a process-scoped FastAPI dependency

A FastAPI dependency `get_tactical_advisor_dependency() -> TacticalAdvisor` SHALL return a process-scoped singleton instance (memoised via `functools.lru_cache` or equivalent) so the underlying Vertex SDK client is reused across requests. Tests SHALL be able to override the dependency to inject a mock advisor.

A second dependency `get_session_factory_dependency() -> async_sessionmaker[AsyncSession]` SHALL return the application-wide session factory so handlers can spawn isolated sessions for sub-tasks (advisor, future ASR rerun) without sharing the request-scoped session.

#### Scenario: Two requests share one TacticalAdvisor instance

- **GIVEN** the FastAPI app started fresh
- **WHEN** two HTTP requests resolve `Depends(get_tactical_advisor_dependency)`
- **THEN** the returned object identity SHALL be the same (`is`) for both requests


<!-- @trace
source: slice-08-tactical-advisor
updated: 2026-05-10
code:
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/meeting_playbook/advisor/__init__.py
  - packages/backend/meeting_playbook/advisor/base.py
  - .env.example
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/advisor/dependencies.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - docs/agents/advisor.md
  - packages/web/src/components/advisor-pane.tsx
tests:
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/backend/tests/meetings/test_dependencies.py
  - packages/backend/tests/sessions/test_repository.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/__init__.py
  - packages/backend/tests/advisor/test_dependencies.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: Advisor errors surface as typed advisor_failed frames without closing the session

When the advisor's coroutine raises an exception during a session-level `request_advice` handling, the WebSocket router SHALL emit an `advisor_failed` frame mapping the exception to one of the documented error codes (`advisor.timeout`, `advisor.quota`, `advisor.auth`, `advisor.unknown`) and continue serving the meeting WebSocket. The router SHALL NOT close the WebSocket as a result of an advisor failure.

#### Scenario: Vertex 429 quota error becomes advisor.quota and the session continues

- **GIVEN** an active meeting WebSocket session
- **WHEN** the advisor raises a `google.api_core.exceptions.ResourceExhausted` (HTTP 429) during a `request_advice` handling
- **THEN** the server SHALL send `{"type": "advisor_failed", "request_id": ..., "error_code": "advisor.quota", "message": ...}` and the WebSocket SHALL remain open and continue receiving subsequent transcript chunks

#### Scenario: 15-second outer timeout becomes advisor.timeout

- **GIVEN** the advisor never produces a token within 15 seconds
- **WHEN** the outer `asyncio.timeout` fires
- **THEN** the server SHALL send `advisor_failed` with `error_code = "advisor.timeout"` and the WebSocket SHALL remain open


<!-- @trace
source: slice-08-tactical-advisor
updated: 2026-05-10
code:
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/meeting_playbook/advisor/__init__.py
  - packages/backend/meeting_playbook/advisor/base.py
  - .env.example
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/advisor/dependencies.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - docs/agents/advisor.md
  - packages/web/src/components/advisor-pane.tsx
tests:
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/backend/tests/meetings/test_dependencies.py
  - packages/backend/tests/sessions/test_repository.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/__init__.py
  - packages/backend/tests/advisor/test_dependencies.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: AdvisorPane renders chat-style cards with streaming markdown and inline retry

The web UI SHALL provide an `AdvisorPane(meetingId, session)` component that renders inside the meeting detail page's third (right) column. The component SHALL render a vertical list of advice cards, oldest at top, newest at bottom, each card containing a small header (`{HH:mm} • 戰術建議`) and a body rendered via `<MarkdownPreview source={tokens} />`. Cards in `streaming` status SHALL show a localised "思考中…" indicator next to their timestamp; cards in `failed` status SHALL show the localised error message and a `重試 / Retry` button that sends a fresh `request_advice` with a new `request_id`.

The pane SHALL include a `Get Advice` button at the bottom; the button SHALL be disabled whenever the most-recent card's status is `streaming`. When `session.state.phase` is not `in_progress`, the pane SHALL render an empty-state hint and SHALL NOT render the `Get Advice` button.

The advice list SHALL automatically scroll to keep the latest card visible as new tokens arrive (smooth scroll, debounced).

#### Scenario: Two consecutive Get Advice clicks render two cards in order

- **GIVEN** an `in_progress` meeting and an empty AdvisorPane
- **WHEN** the user clicks `Get Advice`, the server completes the first stream, then the user clicks again and the server completes the second stream
- **THEN** the pane SHALL render two cards; in document source order the first card SHALL precede the second card; both card statuses SHALL be `done`

#### Scenario: advice_chunk appends to the active card body

- **GIVEN** an active streaming advice request
- **WHEN** three `advice_chunk` frames arrive with `token` values `"a"`, `"b"`, `"c"` for the same `request_id`
- **THEN** the streaming card's rendered MarkdownPreview SHALL receive `source="abc"`

#### Scenario: advisor_failed renders a retry button that fires a new request

- **GIVEN** a card whose stream errored with `advisor.timeout`
- **WHEN** the user clicks the card's `重試` button
- **THEN** the hook SHALL send a new `request_advice` frame whose `request_id` differs from the failed card's `request_id`

#### Scenario: Get Advice button is disabled while streaming

- **GIVEN** an in-flight advice request whose status is `streaming`
- **WHEN** the AdvisorPane re-renders
- **THEN** the `Get Advice` button SHALL have its disabled attribute set; clicking SHALL produce no new `request_advice` frame

#### Scenario: AdvisorPane shows an empty state when not in_progress

- **GIVEN** the session phase is `idle` (the meeting has not started)
- **WHEN** the AdvisorPane renders
- **THEN** the pane SHALL render an element with `data-testid="advisor-pane-empty"` containing the localised hint, and SHALL NOT render a `Get Advice` button


<!-- @trace
source: slice-08-tactical-advisor
updated: 2026-05-10
code:
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/meeting_playbook/advisor/__init__.py
  - packages/backend/meeting_playbook/advisor/base.py
  - .env.example
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/advisor/dependencies.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - docs/agents/advisor.md
  - packages/web/src/components/advisor-pane.tsx
tests:
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/backend/tests/meetings/test_dependencies.py
  - packages/backend/tests/sessions/test_repository.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/__init__.py
  - packages/backend/tests/advisor/test_dependencies.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/routes/meetings/detail.test.tsx
-->

---
### Requirement: PlaybookPane remains read-write during in_progress without contending the session lock

The PlaybookPane component SHALL be editable in all meeting statuses including `in_progress`. The Slice 4 PUT endpoint `/api/meetings/{id}/playbook` SHALL NOT gate on `meeting.status`. A playbook PUT during an active session SHALL NOT contend the session WebSocket's `_write_lock` because the PUT runs in a separate FastAPI request scope with its own AsyncSession.

The advisor's prompt context SHALL fetch the playbook from the database at the moment of the advice request, so an unsaved textarea draft is invisible to the model. Pressing `Save` is the user's commit gate to make edits influence the next advice.

#### Scenario: Playbook PUT during in_progress succeeds without affecting the WS

- **GIVEN** a meeting in `in_progress` with an active WebSocket session producing transcript chunks
- **WHEN** the frontend sends `PUT /api/meetings/{id}/playbook` with a new `free_form_markdown` body
- **THEN** the PUT SHALL return HTTP 200 within normal latency; the active WebSocket SHALL continue receiving transcript chunks without interruption; the next `request_advice` issued after the PUT SHALL include the saved value in the prompt's playbook section

<!-- @trace
source: slice-08-tactical-advisor
updated: 2026-05-10
code:
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/meeting_playbook/advisor/__init__.py
  - packages/backend/meeting_playbook/advisor/base.py
  - .env.example
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/backend/meeting_playbook/advisor/dependencies.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - docs/agents/advisor.md
  - packages/web/src/components/advisor-pane.tsx
tests:
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/backend/tests/meetings/test_dependencies.py
  - packages/backend/tests/sessions/test_repository.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/__init__.py
  - packages/backend/tests/advisor/test_dependencies.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/routes/meetings/detail.test.tsx
-->