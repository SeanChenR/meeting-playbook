## ADDED Requirements

### Requirement: WebSocket contract accepts chat_message client frame for chatbox follow-ups

The WebSocket contract SHALL accept a new client→server frame `chat_message` (in addition to the existing `start_meeting`, `end_meeting`, `request_advice` frames) with the shape `{type: "chat_message", request_id: str, content: str, locale: "zh-TW" | "en"}`. The frame SHALL be modeled as `ChatMessageRequestMessage` Pydantic class with `model_config = {"extra": "forbid"}` and added to the `ClientMessage` discriminated union via the `type` field discriminator. The `content` field SHALL be a non-empty string; the `request_id` field SHALL be a client-generated identifier used to correlate response frames.

When the router's `_client_listener` receives a `chat_message` frame, it SHALL apply the same cancel-previous policy as `request_advice`: if `advice_task is not None and not advice_task.done()`, cancel the prior task and await its completion (suppressing `CancelledError`) before spawning the new advice task. The new advice task SHALL run via `_run_advice` with `user_question = msg.content` and `chat_history = await ChatMessageRepository(advice_session).list_for_meeting(meeting_id)`.

#### Scenario: chat_message frame validates required fields

- **WHEN** the server receives `{"type": "chat_message", "request_id": "r1", "content": "X", "locale": "zh-TW"}`
- **THEN** `parse_client_message(raw)` SHALL return a `ChatMessageRequestMessage` instance with those values

#### Scenario: chat_message frame with empty content fails validation

- **WHEN** the server receives `{"type": "chat_message", "request_id": "r1", "content": "", "locale": "zh-TW"}`
- **THEN** `parse_client_message(raw)` SHALL raise a Pydantic `ValidationError`; the router SHALL emit an `error` frame with `error_code="session.unknown_message"`

#### Scenario: chat_message frame cancels prior in-flight advice and spawns a new task

- **GIVEN** an active WS session with an in-flight advice task spawned by a prior `chat_message`
- **WHEN** a new `chat_message` frame arrives
- **THEN** the prior task SHALL be cancelled and awaited; a new advice task SHALL be created via `asyncio.create_task` with `name=f"advice-{new_request_id}"`; the prior task's stream SHALL NOT emit any further `advice_chunk` frames

### Requirement: Advise stream success persists chat_message pair before final advice_done acknowledgment

When the router's `_run_advice` completes successfully (advisor stream finished without exception), the router SHALL accumulate every yielded token into a single `advisor_content` string AND call `ChatMessageRepository(advice_session).insert_pair_after_advice(meeting_id, user_content, advisor_content)` BEFORE returning. The `user_content` SHALL be the chatbox content (chatbox path) or the locale-default prompt string `"請給出戰術建議。"` / `"Please give tactical advice."` (button path). The INSERT SHALL run inside the same `session_factory()` AsyncSession scope as the chunk fetch / playbook fetch / chat_history fetch, in a single transaction.

When `_run_advice` raises any exception (`asyncio.TimeoutError`, `asyncio.CancelledError`, generic `Exception`), the router SHALL NOT call `insert_pair_after_advice`. The router SHALL log a warning if `insert_pair_after_advice` itself raises after a successful stream; the WebSocket connection SHALL stay open and the user-facing `advice_done` frame SHALL still have been sent.

#### Scenario: Successful advice stream writes user + advisor pair

- **GIVEN** a chatbox `chat_message` frame with `content="X"` and an advisor stream that yields three tokens `["a", "b", "c"]`
- **WHEN** the stream completes and `advice_done` is sent
- **THEN** the database SHALL contain a new user row with `content="X"` and a new advisor row with `content="abc"`; both rows' `meeting_id` SHALL match the WS session's meeting

#### Scenario: Failed advice stream writes nothing

- **GIVEN** an advisor that raises `ResourceExhausted("quota")` mid-stream
- **WHEN** the router emits `advisor_failed` with `error_code="advisor.quota"`
- **THEN** the database SHALL have zero new `chat_message` rows for the meeting

#### Scenario: request_advice button path also writes a chat_message pair

- **GIVEN** a `request_advice` frame (no user_question) and a successful stream yielding `"建議"`
- **WHEN** `advice_done` is sent
- **THEN** the database SHALL have a user row with `content="請給出戰術建議。"` (locale `zh-TW` default) AND an advisor row with `content="建議"`
