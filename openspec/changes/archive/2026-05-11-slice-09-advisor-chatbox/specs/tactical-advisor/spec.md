## ADDED Requirements

### Requirement: chat_message table persists per-meeting conversation history

The backend SHALL provide a `chat_message` table (Alembic migration `0005_create_chat_message`) with exactly five columns: `id` (TEXT primary key, format `cm_<token>`), `meeting_id` (TEXT, foreign key to `meeting.id` ON DELETE CASCADE, NOT NULL), `role` (TEXT, NOT NULL, CHECK constraint `role IN ('user', 'advisor')`), `content` (TEXT, NOT NULL), and `created_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `now()`). The table SHALL have a composite index `chat_message_meeting_created_idx` on `(meeting_id, created_at)`. Deleting a `meeting` row SHALL cascade-delete all associated `chat_message` rows.

The backend SHALL provide `ChatMessageRepository` at `packages/backend/meeting_playbook/chat/repository.py` as the SOLE access path for `chat_message` rows. The repository SHALL expose `list_for_meeting(meeting_id) -> list[ChatMessage]` (ordered by `created_at` ASC) and `insert_pair_after_advice(meeting_id, user_content, advisor_content) -> tuple[ChatMessage, ChatMessage]` (writes both rows in a single transaction). The repository SHALL NOT expose any update or delete method.

#### Scenario: chat_message rows cascade-delete with the parent meeting

- **GIVEN** a meeting with three `chat_message` rows (one user, two advisor)
- **WHEN** the meeting row is deleted
- **THEN** all three `chat_message` rows SHALL be deleted by FK cascade

#### Scenario: insert_pair_after_advice writes both rows atomically

- **GIVEN** a meeting and a successful advise stream that produced advisor content `"建議 X..."`
- **WHEN** `insert_pair_after_advice(meeting_id, user_content="請給出戰術建議。", advisor_content="建議 X...")` runs
- **THEN** the database SHALL contain exactly two new rows for the meeting: one with `role='user'` and `content='請給出戰術建議。'`, one with `role='advisor'` and `content='建議 X...'`; the user row's `created_at` SHALL be earlier than or equal to the advisor row's `created_at`

#### Scenario: list_for_meeting returns rows in chronological order

- **GIVEN** a meeting with five `chat_message` rows inserted out of order
- **WHEN** `list_for_meeting(meeting_id)` runs
- **THEN** the returned list SHALL be ordered by `created_at` ASC (oldest first)

### Requirement: chat_message WS frame triggers advice with chatbox content as user_question

The WebSocket contract SHALL accept a new client→server frame `chat_message` with shape `{type: "chat_message", request_id: str, content: str, locale: "zh-TW" | "en"}`. The `content` field SHALL be a non-empty string; an empty `content` SHALL be rejected as `session.unknown_message`. The frame SHALL be modeled as `ChatMessageRequestMessage` Pydantic class and added to the `ClientMessage` discriminated union.

When the router's `_client_listener` receives a `chat_message` frame, the router SHALL cancel any in-flight advice task (same defensive pattern as `request_advice`), then spawn a new `_run_advice` task passing `user_question = content`, `chat_history = await ChatMessageRepository.list_for_meeting(meeting_id)`. The advisor stream response SHALL flow back via the existing `advice_chunk` / `advice_done` / `advisor_failed` server frames; no new server frame is introduced.

The legacy `request_advice` frame (slice 8) SHALL continue to function for the `Get Advice` button path; when received, the router SHALL fill the user_question with the locale's default prompt string (`"請給出戰術建議。"` for `zh-TW`, `"Please give tactical advice."` for `en`) and pass it through `_run_advice` identically to the chatbox path.

#### Scenario: chat_message frame with empty content is rejected

- **GIVEN** an active WS session in `in_progress`
- **WHEN** the client sends `{"type": "chat_message", "request_id": "r1", "content": "", "locale": "zh-TW"}`
- **THEN** the server SHALL respond with an `error` frame whose `error_code` is `session.unknown_message`; no advice task SHALL spawn

#### Scenario: chat_message frame triggers advice stream identical to chatbox path

- **GIVEN** an active WS session and a previously persisted exchange (one user row + one advisor row)
- **WHEN** the client sends `{"type": "chat_message", "request_id": "r2", "content": "如果他繼續砍價呢", "locale": "zh-TW"}`
- **THEN** the server SHALL spawn `_run_advice` with `user_question="如果他繼續砍價呢"` and `chat_history` containing the prior two rows; the response SHALL stream as `advice_chunk` × N then `advice_done`

#### Scenario: request_advice frame still works and writes default-prompt user content

- **GIVEN** an active WS session
- **WHEN** the client sends `{"type": "request_advice", "request_id": "r3", "locale": "zh-TW"}` (no user_question)
- **THEN** on `advice_done`, the database SHALL have a new user row with `content="請給出戰術建議。"` followed by the advisor row with the streamed content

### Requirement: Advise stream success persists user + advisor rows in a single transaction

When `_run_advice` completes successfully (i.e., the advisor stream finishes and `advice_done` is sent), the router SHALL call `ChatMessageRepository.insert_pair_after_advice(meeting_id, user_content, advisor_content)` BEFORE the session-level cleanup, where `user_content` is the chatbox content (chatbox path) or the locale default prompt (button path) and `advisor_content` is the concatenation of all `advice_chunk` tokens emitted during the stream. Both rows SHALL be inserted in a single SQLAlchemy transaction and committed atomically.

When `_run_advice` fails with any exception path (`asyncio.TimeoutError`, `asyncio.CancelledError`, `ResourceExhausted`, `Unauthenticated`, generic `Exception`), the router SHALL NOT call `insert_pair_after_advice`. No `chat_message` row SHALL be written for failed, cancelled, or interrupted advice streams.

#### Scenario: Successful stream writes both rows; refresh shows them

- **GIVEN** a chatbox send with content `"X"` that completes successfully with advisor output `"Y"`
- **WHEN** `advice_done` is sent and the response settles
- **THEN** the database SHALL contain a user row with `content="X"` and an advisor row with `content="Y"`; both rows SHALL have the same `meeting_id`; `GET /api/meetings/{id}/chat_messages` SHALL return both in `created_at` order

#### Scenario: Vertex timeout writes nothing

- **GIVEN** a chatbox send whose advise stream raises `asyncio.TimeoutError` after 15s
- **WHEN** the router emits `advisor_failed` with `error_code="advisor.timeout"`
- **THEN** the database SHALL have zero new `chat_message` rows for this meeting

#### Scenario: Cancelled stream (new chat_message arrives mid-flight) writes nothing

- **GIVEN** an in-flight advise stream
- **WHEN** the client sends a new `chat_message` frame and the prior task is cancelled
- **THEN** the cancelled stream SHALL NOT write any `chat_message` row; the new stream's success SHALL still write its own user + advisor pair

### Requirement: Advisor prompt assembly includes a chat_history section between transcript and question

The advisor's `build_user_message(playbook, recent_chunks, me_display_name, counterparty_display_name, user_question, locale, chat_history)` SHALL accept a new keyword argument `chat_history: list[ChatMessage]`. When `chat_history` is non-empty, the assembled user message SHALL include a `## 對話紀錄` (zh-TW) / `## Chat history` (en) section between the `## 最近 60 秒對話` section and the final question line. Each historical message SHALL render as `{me_display_name}: {content}` for `role='user'` rows and `Advisor: {content}` for `role='advisor'` rows, ordered by `created_at` ASC. When `chat_history` is empty, the section heading SHALL NOT be rendered (no empty headings). The literal string `Advisor` (not the meeting's `counterparty_display_name`) SHALL identify advisor rows.

`TacticalAdvisor.advise(...)` Protocol SHALL accept `chat_history: list[ChatMessage]` as a new keyword parameter. The router's `_run_advice` SHALL fetch chat_history via `ChatMessageRepository.list_for_meeting(meeting_id)` BEFORE invoking the advisor.

#### Scenario: Empty chat_history omits the section heading entirely

- **GIVEN** a first-turn advise call with `chat_history=[]`
- **WHEN** `build_user_message(...)` runs
- **THEN** the returned string SHALL NOT contain `## 對話紀錄` or `## Chat history`

#### Scenario: Multi-turn chat_history renders in order with role labels

- **GIVEN** `chat_history` containing 4 rows in order: user "問題A", advisor "回答A", user "問題B", advisor "回答B", with `me_display_name="Sean"`
- **WHEN** `build_user_message(..., locale="zh-TW", chat_history=...)` runs
- **THEN** the returned string SHALL contain a `## 對話紀錄` section with these four lines in order: `Sean: 問題A`, `Advisor: 回答A`, `Sean: 問題B`, `Advisor: 回答B`

#### Scenario: chat_history section sits between transcript and question

- **GIVEN** non-empty playbook, non-empty recent_chunks, non-empty chat_history, and `user_question="新問題"`
- **WHEN** `build_user_message(...)` runs
- **THEN** the returned string SHALL have these sections in order: `## 會議 playbook`, `## 最近 60 秒對話`, `## 對話紀錄`, then the question line containing `"新問題"`

### Requirement: GET /api/meetings/{id}/chat_messages returns persisted chat history

The backend SHALL expose `GET /api/meetings/{meeting_id}/chat_messages` (mounted by `chat/router.py`) requiring the gateway-injected `X-User-Id` header. The endpoint SHALL verify that `meeting_id` belongs to `user_id` via `MeetingRepository.get_for_user`; non-owner or non-existent meeting SHALL return HTTP 404 with the standard flat envelope `{"error_code": "meeting.not_found", "message": "Meeting not found"}` produced by the application-wide `_http_exception_handler` in `server.py`. Missing `X-User-Id` SHALL return HTTP 401 with `{"error_code": "auth.gateway_bypass", ...}`. On success, the endpoint SHALL return a JSON array of objects with shape `{id, meeting_id, role, content, created_at}` ordered by `created_at` ASC. Empty history SHALL return `[]` not 404.

#### Scenario: Owner GET returns chronological history

- **GIVEN** a meeting belonging to user `u_a` with three `chat_message` rows
- **WHEN** `u_a` issues `GET /api/meetings/{meeting_id}/chat_messages`
- **THEN** the response SHALL be HTTP 200 with a JSON array of three objects ordered by `created_at` ASC; each object SHALL have keys `id`, `meeting_id`, `role`, `content`, `created_at`

#### Scenario: Non-owner GET returns 404 not_found

- **GIVEN** a meeting belonging to user `u_a` with chat history
- **WHEN** user `u_b` issues `GET /api/meetings/{meeting_id}/chat_messages`
- **THEN** the response SHALL be HTTP 404 with body `{"error_code": "meeting.not_found", "message": "Meeting not found"}` (flat envelope, NOT wrapped in `detail`)

#### Scenario: Empty history returns 200 with empty array

- **GIVEN** a meeting belonging to user `u_a` with zero `chat_message` rows
- **WHEN** `u_a` issues `GET /api/meetings/{meeting_id}/chat_messages`
- **THEN** the response SHALL be HTTP 200 with body `[]`

## MODIFIED Requirements

### Requirement: TacticalAdvisor module exposes a streaming advise() coroutine

The backend SHALL provide a `TacticalAdvisor` Protocol (and a concrete `VertexFlashAdvisor` implementation) located at `packages/backend/meeting_playbook/advisor/`. The Protocol's single coroutine `advise(meeting_id, recent_chunks, playbook, me_display_name, counterparty_display_name, user_question, locale, chat_history) -> AsyncIterator[str]` SHALL yield text segments as they arrive from the underlying LLM stream. The `chat_history` parameter SHALL accept a `list[ChatMessage]` ordered ascending by `created_at`; an empty list SHALL be valid and represent a first-turn call. The Protocol SHALL be the SOLE entry point used by `sessions/router.py` to invoke the advisor; the router MUST NOT import any Vertex / `google-genai` symbol directly.

The concrete `VertexFlashAdvisor` SHALL wrap the official `google-genai` SDK's `aio.models.generate_content_stream(...)` call. Each SDK chunk's `chunk.text` SHALL be yielded verbatim as one string. The model id SHALL come from `Settings.vertex_flash_model_id` (default `gemini-2.5-flash`). Generation parameters SHALL be `temperature=0.4`, `max_output_tokens=400`, default `top_p`. The provider SHALL apply a 15-second outer `asyncio.timeout` so a hung Vertex stream raises `asyncio.TimeoutError` rather than blocking the WebSocket session indefinitely.

#### Scenario: advise yields one string per SDK chunk

- **GIVEN** a mocked Vertex stream that produces three chunks with `chunk.text` equal to `"建議一"`, `"建議二"`, `"建議三"`
- **WHEN** the caller iterates `async for token in advisor.advise(..., chat_history=[])`
- **THEN** the iterator SHALL yield exactly the three strings in that order

#### Scenario: 15-second cap on the outer stream raises TimeoutError

- **GIVEN** a mocked Vertex stream that sleeps 20 seconds before yielding
- **WHEN** the caller iterates `async for token in advisor.advise(..., chat_history=[])`
- **THEN** the iterator SHALL raise `asyncio.TimeoutError` between 15.0 and 16.0 seconds after the call begins

#### Scenario: advise accepts non-empty chat_history without changing yield behavior

- **GIVEN** a mocked Vertex stream that produces two chunks AND a `chat_history` of 4 rows (2 user / 2 advisor)
- **WHEN** the caller iterates `async for token in advisor.advise(..., chat_history=...)`
- **THEN** the iterator SHALL yield exactly the two chunk strings; the `chat_history` SHALL have been embedded in the prompt's `build_user_message` output (verified separately by the prompt builder tests)

### Requirement: AdvisorPane renders chat-style cards with streaming markdown and inline retry

The web UI SHALL provide an `AdvisorPane(session)` component that renders inside the meeting detail page's third (right) column. The component SHALL render in three vertical sections: (1) a scrolling history list at the top showing all persisted `chat_message` rows from the React Query cache plus any in-flight advice card, (2) a `Get Advice` button in the middle, (3) a chatbox with a textarea and `Send` button at the bottom. User-role messages SHALL render right-aligned with one visual treatment; advisor-role messages SHALL render left-aligned with `<MarkdownPreview source={content} />` for body. In-flight advice cards SHALL show a localised "思考中…" indicator next to their timestamp.

The `Get Advice` button SHALL be disabled whenever any in-flight advice is streaming. The `Send` button SHALL be disabled when the textarea is empty OR an in-flight advice is streaming. The textarea SHALL accept `Cmd+Enter` (macOS) / `Ctrl+Enter` as a send shortcut. When `session.state.phase` is not `in_progress`, the pane SHALL render the history list (still visible across phases for review) but SHALL NOT render the `Get Advice` button, the textarea, or the `Send` button.

The history list SHALL automatically scroll to keep the latest message visible as new messages arrive (smooth scroll, debounced).

#### Scenario: History list renders persisted chat_message rows from React Query cache

- **GIVEN** a meeting whose `GET /api/meetings/{id}/chat_messages` returns 4 rows (user/advisor/user/advisor)
- **WHEN** the AdvisorPane mounts and the React Query cache is populated
- **THEN** the pane SHALL render four message bubbles in `created_at` ASC order; user rows SHALL have `data-role="user"` and advisor rows SHALL have `data-role="advisor"`

#### Scenario: Send button is disabled when textarea is empty

- **GIVEN** an `in_progress` meeting and an empty textarea
- **WHEN** the AdvisorPane renders
- **THEN** the `Send` button SHALL have its disabled attribute set

#### Scenario: Cmd+Enter in textarea sends a chat_message frame

- **GIVEN** the user has typed `"如果他繼續砍價呢"` into the textarea AND the meeting is `in_progress`
- **WHEN** the user presses `Cmd+Enter` (or `Ctrl+Enter` on non-macOS)
- **THEN** the hook SHALL send a WS frame `{"type": "chat_message", "request_id": <uuid>, "content": "如果他繼續砍價呢", "locale": "zh-TW"}`; the textarea SHALL be cleared

#### Scenario: Get Advice button is disabled while any advice is streaming

- **GIVEN** an in-flight advice request whose status is `streaming`
- **WHEN** the AdvisorPane re-renders
- **THEN** the `Get Advice` button SHALL have its disabled attribute set; the `Send` button SHALL also have its disabled attribute set

#### Scenario: AdvisorPane outside in_progress hides input controls but keeps history visible

- **GIVEN** the session phase is `ended` AND the meeting has 4 persisted chat_message rows
- **WHEN** the AdvisorPane renders
- **THEN** the pane SHALL render the four message bubbles; the pane SHALL NOT render a `Get Advice` button, a textarea, or a `Send` button
