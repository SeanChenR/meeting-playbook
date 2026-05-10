# meeting-session Specification

## Purpose

Defines the realtime meeting session: how the browser establishes a WebSocket
to the backend, how audio is captured (mic in slice 6, mic plus counterparty
stream from BlackHole in a later slice), how each audio chunk is fed to a
pluggable ASR provider, and how the resulting transcript chunks are persisted
and streamed back to the UI for live display.

The session is one-shot per meeting: a meeting in `scheduled` state can be
started exactly once, advances to `in_progress`, and ends to `completed`.
Recordings are kept for the recording window (30 days) before retention
cleanup. The frontend hook `useMeetingSession` owns the connection lifecycle;
the backend `SessionService` owns the capture → transcribe → persist →
broadcast loop.

## Requirements

### Requirement: WebSocket session endpoint at /api/meetings/{id}/session is gated by meeting ownership

The endpoint `GET /api/meetings/{id}/session` SHALL upgrade to a WebSocket connection ONLY for authenticated requests that own the meeting. Authentication SHALL be verified BEFORE the upgrade handshake completes; ownership SHALL be verified through `MeetingRepository.get_for_user(user_id, meeting_id)`. Cross-user requests SHALL be rejected with HTTP 404 + envelope `error_code: meeting.not_found` (no existence leak). Unauthenticated requests SHALL be rejected with HTTP 401 + envelope `error_code: auth.gateway_bypass`.

#### Scenario: Owner upgrades to WebSocket successfully

- **GIVEN** user A owns meeting `m_abc`
- **WHEN** user A opens a WebSocket to `/api/meetings/m_abc/session` through the gateway
- **THEN** the upgrade SHALL succeed and the connection SHALL remain open until either side closes

#### Scenario: Non-owner is rejected with meeting.not_found

- **GIVEN** user B does NOT own meeting `m_abc`
- **WHEN** user B attempts to open a WebSocket to `/api/meetings/m_abc/session`
- **THEN** the upgrade SHALL fail with HTTP 404 and the response body's `error_code` SHALL be `meeting.not_found`

#### Scenario: Unauthenticated request is rejected before upgrade

- **WHEN** an unauthenticated client (no `X-User-Id` header) attempts to open a WebSocket to `/api/meetings/m_abc/session`
- **THEN** the gateway SHALL reject the request with HTTP 401 and the response body's `error_code` SHALL be `auth.gateway_bypass`; the upgrade MUST NOT complete


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
### Requirement: WebSocket message contract for the meeting session

The WebSocket connection SHALL carry JSON messages tagged by a `type` field. The contract is:

Client → server messages:
- `{"type": "start_meeting", "meeting_id": "<id>"}` — opens a new session for the meeting
- `{"type": "end_meeting", "meeting_id": "<id>"}` — finalizes the session
- `{"type": "request_advice", "request_id": "<uuid>", "locale": "zh-TW"|"en", "user_question"?: "<string>"}` — requests a tactical advisor reply for the current meeting context. `user_question` is optional and reserved for the chatbox follow-up shipped in a later slice; in the slice that introduces this frame it is always omitted.

Server → client messages:
- `{"type": "meeting_started", "meeting_id": "<id>"}` — sent immediately after the server accepts a `start_meeting` message and transitions the meeting to `in_progress`
- `{"type": "transcript_chunk", "meeting_id": "<id>", "speaker": "me"|"counterparty", "text": "<string>", "started_at": "<iso8601>", "ended_at": "<iso8601>", "asr_provider_used": "<string>", "confidence": <float|null>}` — one per ~10-second audio chunk per stream; `speaker` value reflects the source stream
- `{"type": "silence_warning", "meeting_id": "<id>", "stream": "me"|"counterparty", "since": "<iso8601>"}` — emitted when one stream has been silent for more than 30 seconds; the `stream` field identifies which stream is silent so the client can update only that capture indicator
- `{"type": "stream_stopped", "meeting_id": "<id>", "stream": "me"|"counterparty", "reason": "<string>"}` — emitted when one capture stream fails mid-session and stops; the WebSocket SHALL remain open until both streams have stopped
- `{"type": "advice_chunk", "request_id": "<uuid>", "token": "<string>"}` — emitted per Vertex Flash SDK chunk during a streaming advice request; multiple frames make up one advice reply
- `{"type": "advice_done", "request_id": "<uuid>"}` — terminal frame for a successful advice stream; the client uses it to flip the corresponding card from `streaming` to `done` and re-enable the Get Advice button
- `{"type": "advisor_failed", "request_id": "<uuid>", "error_code": "<code>", "message": "<string>"}` — emitted when the advisor coroutine raises; `error_code` is one of `advisor.timeout`, `advisor.quota`, `advisor.auth`, `advisor.unknown`. Receiving this frame MUST NOT cause the WebSocket to close — the meeting session continues, only the failing advice card is marked
- `{"type": "meeting_ended", "meeting_id": "<id>"}` — sent after the server finalizes the WAV file(s) and transitions the meeting to `completed`
- `{"type": "error", "error_code": "<code>", "message": "<string>"}` — emitted when an unrecoverable failure occurs; the connection SHALL be closed by the server immediately afterward

Unknown message types from the client SHALL cause the server to respond with `{"type": "error", "error_code": "session.unknown_message"}` and close the connection.

#### Scenario: First client message must be start_meeting matching the path id

- **GIVEN** a WebSocket connected to `/api/meetings/m_abc/session`
- **WHEN** the client sends `{"type": "start_meeting", "meeting_id": "m_xyz"}` (id mismatch)
- **THEN** the server SHALL send `{"type": "error", "error_code": "session.bad_start"}` and close the connection

#### Scenario: Successful dual-stream session emits the expected message sequence

- **GIVEN** an authenticated owner connects, sends `start_meeting`, both streams capture three audio chunks each, the user sends `end_meeting`
- **WHEN** the session runs to completion
- **THEN** the server SHALL emit `meeting_started` first, then six `transcript_chunk` messages (three with `speaker = "me"`, three with `speaker = "counterparty"`) ordered by their `started_at` timestamps, then `meeting_ended`, then close the connection

#### Scenario: silence_warning carries the affected stream

- **GIVEN** a dual-stream session in progress where the counterparty stream produces silence for 30 seconds while the me stream produces audio
- **WHEN** the silence threshold is crossed for the counterparty stream
- **THEN** the server SHALL emit exactly one `silence_warning` message whose `stream` field equals `"counterparty"` and SHALL NOT emit a `silence_warning` for the me stream

#### Scenario: request_advice triggers a streamed reply terminated by advice_done

- **GIVEN** an `in_progress` meeting WebSocket session
- **WHEN** the client sends `{"type": "request_advice", "request_id": "abc-123", "locale": "zh-TW"}` and the advisor produces three SDK chunks `"建議一"`, `"建議二"`, `"建議三"`
- **THEN** the server SHALL emit exactly three `advice_chunk` frames with the corresponding `token` values then exactly one `advice_done` frame all carrying `request_id = "abc-123"`, in that order

#### Scenario: advisor_failed leaves the WebSocket open

- **GIVEN** an `in_progress` meeting WebSocket session
- **WHEN** the advisor raises a `ResourceExhausted` (HTTP 429) during a `request_advice` handling
- **THEN** the server SHALL emit `{"type": "advisor_failed", "request_id": ..., "error_code": "advisor.quota", "message": ...}`; the WebSocket connection MUST NOT close; subsequent `transcript_chunk` and other server-side frames SHALL continue arriving normally

#### Scenario: end_meeting cancels an in-flight advice task without emitting further chunks

- **GIVEN** an in-flight `request_advice` whose stream is mid-emission (`advice_chunk` frames have been arriving)
- **WHEN** the client sends `{"type": "end_meeting", ...}`
- **THEN** the server SHALL cancel the in-flight advice task within 1 second; no further `advice_chunk` or `advice_done` SHALL be emitted for that `request_id`; the normal `meeting_ended` finalization SHALL proceed

##### Example: minimum required keys per server-side message type

| `type`              | Required keys                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `meeting_started`   | `type`, `meeting_id`                                                                                       |
| `transcript_chunk`  | `type`, `meeting_id`, `speaker`, `text`, `started_at`, `ended_at`, `asr_provider_used`, `confidence`       |
| `silence_warning`   | `type`, `meeting_id`, `stream`, `since`                                                                    |
| `stream_stopped`    | `type`, `meeting_id`, `stream`, `reason`                                                                   |
| `advice_chunk`      | `type`, `request_id`, `token`                                                                              |
| `advice_done`       | `type`, `request_id`                                                                                       |
| `advisor_failed`    | `type`, `request_id`, `error_code`, `message`                                                              |
| `meeting_ended`     | `type`, `meeting_id`                                                                                       |
| `error`             | `type`, `error_code`, `message`                                                                            |


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
### Requirement: Audio capture writes one WAV file per session under RECORDINGS_DIR

The session SHALL persist each capture stream's audio as a separate mono WAV file under `{RECORDINGS_DIR}/{meeting_id}/`: the microphone stream at `me.wav` and the BlackHole stream at `counterparty.wav`. Each file MUST contain its stream's full captured content (16 kHz, mono, 16-bit PCM) and SHALL be finalized by the time the server emits `meeting_ended`. The directory SHALL be created on demand if it does not exist. The default value of `RECORDINGS_DIR` is `~/MeetingPlaybook/recordings`; deployments override via the `RECORDINGS_DIR` environment variable.

For each stream that produced any audio (even partial, after a `stream_stopped`) the session SHALL persist exactly one `recording` row whose `meeting_id` matches the session, `stream` equals `"me"` or `"counterparty"`, `file_path` equals the absolute on-disk WAV path for that stream, and `bytes` equals the WAV file size on disk for that stream. A stream that produced zero bytes SHALL NOT cause a `recording` row to be written.

#### Scenario: Both WAV files exist after a successful dual-stream session

- **WHEN** a dual-stream meeting session ends successfully
- **THEN** both `{RECORDINGS_DIR}/{meeting_id}/me.wav` and `{RECORDINGS_DIR}/{meeting_id}/counterparty.wav` SHALL exist on disk, and exactly two `recording` rows SHALL exist (one with `stream = "me"`, one with `stream = "counterparty"`), each with `bytes` matching their on-disk file sizes

#### Scenario: One stream stopping mid-session still finalizes its partial WAV

- **GIVEN** the counterparty stream stops 90 seconds into a 5-minute session and the me stream completes normally
- **WHEN** the user ends the meeting
- **THEN** `{RECORDINGS_DIR}/{meeting_id}/counterparty.wav` SHALL contain approximately 90 seconds of audio (the partial capture), `me.wav` SHALL contain the full ~5 minutes, and two `recording` rows SHALL exist accordingly

#### Scenario: Recordings directory is created on demand

- **GIVEN** the `RECORDINGS_DIR` directory does NOT exist
- **WHEN** a meeting session starts
- **THEN** the directory SHALL be created (recursively) before any audio data is written, and the session SHALL proceed normally


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
### Requirement: Transcript chunks are persisted in chronological order

For every `transcript_chunk` message emitted to the client, the server SHALL FIRST persist a row to the `transcript_chunk` table whose columns match the message body (`meeting_id`, `speaker`, `text`, `started_at`, `ended_at`, `asr_provider_used`, `confidence`). The row's `started_at` and `ended_at` SHALL be timezone-aware UTC timestamps. Rows for the same meeting SHALL have non-decreasing `started_at` values; the server MUST NOT emit a chunk to the client if the database write fails.

#### Scenario: Database write precedes client emission

- **GIVEN** a meeting session is in progress
- **WHEN** the ASR provider returns a transcribed chunk
- **THEN** the server SHALL insert a row into `transcript_chunk` first, and only after the insert succeeds SHALL it send the corresponding `transcript_chunk` message to the client

#### Scenario: Failed insert prevents client emission

- **GIVEN** the database is unavailable when a chunk is ready to be sent
- **WHEN** the insert fails
- **THEN** the server MUST NOT send the `transcript_chunk` message; instead it SHALL emit `{"type": "error", "error_code": "session.persist_failed"}` and close the connection


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
### Requirement: ASRProvider interface enables multiple ASR engines (per ADR-0005)

The backend SHALL define an `ASRProvider` Protocol with at least:
- A `name` property returning a stable string identifier (e.g. `"whisper"`, `"vibevoice"`)
- An async `transcribe_chunk(audio_bytes: bytes, sample_rate_hz: int, language_hint: str | None = None) -> TranscriptChunk` method

The Protocol SHALL be the only contract that the session orchestrator depends on; any new ASR engine SHALL be drop-in by implementing this Protocol without modifying `AudioCaptureService` or the session router. The session SHALL set `transcript_chunk.asr_provider_used` to the provider's `name`.

#### Scenario: WhisperProvider satisfies the contract

- **GIVEN** an audio fixture containing a short Chinese utterance
- **WHEN** `WhisperProvider.transcribe_chunk(audio_bytes, sample_rate_hz=16000, language_hint="zh")` is invoked
- **THEN** the return value SHALL be a `TranscriptChunk` with non-empty `text`, `asr_provider_used == "whisper"`, and `ended_at > started_at`

#### Scenario: Session router does not import any concrete provider

- **WHEN** the session router source is reviewed
- **THEN** it MUST import only the `ASRProvider` Protocol and the configured provider via dependency injection; it MUST NOT import `WhisperProvider` (or any other concrete provider) directly


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
### Requirement: Silence in the audio stream is reported within 30 seconds

For each active capture stream, when its RMS amplitude stays below the silence threshold for more than 30 consecutive seconds, the server SHALL emit a `silence_warning` message identifying which stream is silent (`stream` field set to `"me"` or `"counterparty"`) with a `since` timestamp marking when that stream's silence began. Subsequent `silence_warning` messages for the same stream MAY be sent at most once per 30-second silence window so the client is not spammed. Silence on one stream MUST NOT trigger warnings for the other stream. When audio resumes on a silent stream (RMS rises above threshold), no clearance message is sent — the client infers resumption from the next `transcript_chunk` for that stream.

#### Scenario: 30-second silence on one stream triggers a stream-specific warning

- **GIVEN** a dual-stream session in progress where the counterparty stream is silent for 30 consecutive seconds while the me stream produces audio
- **WHEN** the silence threshold is crossed for the counterparty stream
- **THEN** the server SHALL emit one `silence_warning` message with `stream = "counterparty"` and `since` equal to when counterparty silence began, and SHALL NOT emit any `silence_warning` for the me stream

#### Scenario: Continuing silence on one stream does not flood the client

- **GIVEN** the me stream has already triggered one `silence_warning`
- **WHEN** that stream's silence continues for another 60 seconds
- **THEN** the server SHALL emit at most one additional `silence_warning` for the me stream (not three), preserving the original `since` timestamp; the counterparty stream's status SHALL remain unaffected


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
### Requirement: useMeetingSession hook owns the WebSocket lifecycle and reducer state

The frontend SHALL provide a deep React hook `useMeetingSession(meetingId: string)` that:
- Owns the WebSocket connection in a ref
- Manages session state via a `useReducer` over a discriminated union of phases: `idle | connecting | in_progress | ended | error`
- Exposes `start()` and `end()` methods that the UI calls
- Translates inbound WS messages into reducer actions:
  - `meeting_started` → phase becomes `in_progress` with `chunks: []`
  - `transcript_chunk` → appended to `chunks` (chronological)
  - `silence_warning` → records `silenceSince`
  - `meeting_ended` → phase becomes `ended`
  - `error` → phase becomes `error` carrying `errorCode` and message
- On unexpected close during `in_progress` SHALL attempt one reconnect with 1-second backoff, then transition to `error` if the reconnect fails

#### Scenario: Receiving transcript_chunk appends to chunks in order

- **GIVEN** the hook is in `in_progress` phase with one chunk already received
- **WHEN** a new `transcript_chunk` message arrives
- **THEN** the new chunk SHALL be appended to `chunks` and the array order MUST match WS arrival order

#### Scenario: error message transitions to error phase and closes the WebSocket

- **GIVEN** the hook is in `in_progress` phase
- **WHEN** an `error` message with `error_code: session.persist_failed` arrives
- **THEN** the hook's state SHALL transition to `{phase: "error", errorCode: "session.persist_failed", chunks: <previous chunks>}` and the WebSocket SHALL be closed


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
### Requirement: TranscriptPane renders chunks with the meeting's me display name

The component `TranscriptPane(chunks, meDisplayName, counterpartyDisplayName)` SHALL render every chunk in chronological order regardless of speaker. Each rendered chunk SHALL display the speaker's localized display name and a timestamp prefix line, plus the chunk text. Chunks SHALL be visually differentiated by speaker via a 4-pixel left accent border whose color is theme-token `--color-primary` for `speaker = "counterparty"` and `--color-secondary` (or `--color-muted-foreground` if `--color-secondary` is too saturated) for `speaker = "me"`. The chunk body text SHALL use the default `text-foreground` color (NOT colored). The display name shown SHALL be `meDisplayName` for `me` chunks and `counterpartyDisplayName` for `counterparty` chunks.

#### Scenario: Empty chunks renders an empty state

- **GIVEN** an empty `chunks` array
- **WHEN** the component renders
- **THEN** it SHALL render a placeholder element (not crash and not render an empty list element)

#### Scenario: Mixed-speaker chunks render with distinct accent colors

- **GIVEN** `meDisplayName = "Sean"`, `counterpartyDisplayName = "林經理"`, and a chunks list `[A(speaker=me), B(speaker=counterparty), C(speaker=me)]` ordered by `started_at`
- **WHEN** the component renders
- **THEN** the three chunks SHALL render in source order A, B, C; chunk A and chunk C SHALL include the visible string `"Sean"` and SHALL apply the me accent border; chunk B SHALL include the visible string `"林經理"` and SHALL apply the counterparty accent border


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
### Requirement: Pre-flight check rejects session start when BlackHole device is missing

Before opening either capture stream the session SHALL invoke a device-discovery routine that locates a BlackHole device by name pattern. The routine SHALL match any input device whose `name` contains the substring `BlackHole` and whose `max_input_channels` is at least 2, OR the device whose name exactly equals the value of the optional `BLACKHOLE_DEVICE_NAME` environment variable when that variable is set. If no matching device exists, the session SHALL emit `{"type": "error", "error_code": "session.no_blackhole_device", "message": "<localized>"}` and close the WebSocket connection without writing any `recording` row, without transitioning the meeting status, and without spawning any capture task. The pre-flight SHALL NOT attempt to verify that the system audio output is routed through a Multi-Output Device.

#### Scenario: Missing BlackHole device aborts the session

- **GIVEN** the host machine has no input device whose name contains `BlackHole`
- **WHEN** an authenticated owner opens a WebSocket to `/api/meetings/m_abc/session` and sends `{"type": "start_meeting", "meeting_id": "m_abc"}`
- **THEN** the server SHALL respond with `{"type": "error", "error_code": "session.no_blackhole_device"}` and close the connection; the meeting row SHALL retain `status = "scheduled"` and no `recording` row SHALL be written

#### Scenario: BLACKHOLE_DEVICE_NAME env override locates a non-default device

- **GIVEN** the host has two BlackHole-related devices and `BLACKHOLE_DEVICE_NAME=BlackHole 16ch` is set
- **WHEN** the session pre-flight runs
- **THEN** the routine SHALL select the device named exactly `BlackHole 16ch` rather than the auto-detected `BlackHole 2ch` device

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
### Requirement: Session captures BlackHole and microphone as two parallel streams with independent failure domains

The `SessionService` SHALL hold two `AudioCaptureService` instances on every dual-stream session: one for the microphone (stream label `me`, device resolved via `MIC_DEVICE_NAME` env override or `sounddevice.default.device[0]`) and one for BlackHole (stream label `counterparty`, device resolved per the pre-flight routine above). The two instances SHALL produce `AudioChunk` events independently, each labelled with its stream identifier. At session start both streams MUST successfully open their respective `RawInputStream` before the server emits `meeting_started`; if either fails to open the server SHALL emit `{"type": "error", "error_code": "session.stream_failed_at_start"}` and close the connection. Once the session is running, an exception in one stream's capture task SHALL stop only that stream — the other stream MUST continue producing chunks until the user ends the meeting OR the second stream also stops.

#### Scenario: Both streams open and produce parallel chunks

- **GIVEN** the host has both a working BlackHole device and a working microphone, and a meeting `m_abc` is in `scheduled` status
- **WHEN** the user starts the session via WebSocket
- **THEN** the server SHALL emit `meeting_started` followed by `transcript_chunk` messages for both `speaker = "me"` and `speaker = "counterparty"`, each chunk derived only from its corresponding source stream

#### Scenario: One stream failing at start aborts the whole session

- **GIVEN** the BlackHole device is present but the microphone open call raises (e.g., system permission revoked)
- **WHEN** the session pre-flight + `start()` runs
- **THEN** the server SHALL emit `{"type": "error", "error_code": "session.stream_failed_at_start"}` and close the connection without producing any `recording` row

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
### Requirement: ASR runs through one ASRProvider instance per stream with parallel warmup

The `SessionService` SHALL maintain a mapping from stream identifier (`me` / `counterparty`) to an `ASRProvider` instance, with a separate `WhisperProvider` instance per stream so model inference for the two streams can proceed concurrently. Each `WhisperProvider` SHALL expose an idempotent `warmup()` async method that loads its underlying model. During the connecting phase the session SHALL invoke both providers' `warmup()` calls in parallel via `asyncio.gather` so the first chunks are available without serial cold-start delay. Each captured `AudioChunk` SHALL be transcribed only by the provider mapped to that chunk's stream label.

#### Scenario: Warmup runs both providers in parallel

- **GIVEN** the session is starting and both providers report `_model is None` initially
- **WHEN** the session enters the connecting phase
- **THEN** both `provider.warmup()` calls SHALL be awaited via `asyncio.gather` (concurrently) and each provider SHALL load its model exactly once

#### Scenario: Per-stream chunk routing

- **GIVEN** an active dual-stream session with provider A mapped to `me` and provider B mapped to `counterparty`
- **WHEN** the `me` capture emits five chunks and the `counterparty` capture emits five chunks
- **THEN** provider A SHALL receive exactly the five `me` chunks (and zero `counterparty` chunks) and provider B SHALL receive exactly the five `counterparty` chunks (and zero `me` chunks)

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
### Requirement: Session emits stream_stopped when one capture stream fails mid-session

When a capture task for one stream raises an unhandled exception while the meeting is `in_progress`, the `SessionService` SHALL: (a) stop transcription for that stream, (b) finalize the partial WAV file already written for that stream, (c) record the corresponding `recording` row capturing whatever bytes were written, and (d) broadcast `{"type": "stream_stopped", "meeting_id": "<id>", "stream": "me"|"counterparty", "reason": "<short string>"}` to the client. The other stream SHALL continue producing transcript chunks and writing its own WAV. When BOTH streams have stopped (either via individual failure or via the user's `end_meeting`), the session SHALL transition the meeting to `completed` and emit `meeting_ended` exactly once.

#### Scenario: Counterparty capture failure preserves me-stream operation

- **GIVEN** a session is in `in_progress` and producing chunks for both streams
- **WHEN** the counterparty capture task raises an exception (e.g., BlackHole driver crash) at time T
- **THEN** the server SHALL emit exactly one `{"type": "stream_stopped", "stream": "counterparty"}` message; subsequent `transcript_chunk` messages SHALL still be emitted for `speaker = "me"`; no `error` frame SHALL be sent and the WebSocket SHALL remain open

#### Scenario: Both streams stopped triggers meeting_ended automatically

- **GIVEN** the counterparty stream has already stopped and the me stream subsequently fails
- **WHEN** both active capture tasks have ended
- **THEN** the server SHALL emit `meeting_ended`, transition the meeting to `completed`, and close the connection (without waiting for an explicit `end_meeting` from the client)

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
### Requirement: Detail page shows a use-headphones hint above Start Meeting (slice-7 round 2)

The meeting detail page SHALL render a permanent informational callout immediately above the Start Meeting button whenever `meeting.status` equals `"scheduled"`. The callout content SHALL be localized via the i18n key `meetings.session.headphonesHint` (zh-TW + en) and explain that the user SHOULD wear headphones during the meeting because the system audio routed through the Multi-Output Device is also picked up by the microphone, which causes both capture streams to contain near-identical content. The callout MUST NOT be dismissible; it disappears only when the meeting transitions out of `scheduled` status.

The callout SHALL NOT block the user from starting the session — it is informational, not gating. Slice-7 explicitly declines to implement DSP echo cancellation; the headphones hint is the entire user-facing mitigation.

#### Scenario: Scheduled meeting renders the headphones callout above Start

- **GIVEN** a meeting with `status = "scheduled"`
- **WHEN** the detail page renders
- **THEN** an element with `data-testid="headphones-hint"` containing the localized `meetings.session.headphonesHint` string SHALL appear in the DOM directly above the Start Meeting button

#### Scenario: In-progress meeting hides the callout

- **GIVEN** a meeting whose `status = "in_progress"` (a session is running)
- **WHEN** the detail page renders
- **THEN** the element with `data-testid="headphones-hint"` SHALL NOT exist in the DOM

#### Scenario: Completed meeting hides the callout

- **GIVEN** a meeting whose `status = "completed"`
- **WHEN** the detail page renders
- **THEN** the element with `data-testid="headphones-hint"` SHALL NOT exist in the DOM

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


<!-- @trace
source: slice-09-advisor-chatbox
updated: 2026-05-11
code:
  - packages/web/src/lib/session-ws.ts
  - docs/agents/advisor.md
  - packages/backend/meeting_playbook/chat/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/web/src/locales/en.json
  - packages/backend/alembic/versions/0005_create_chat_message.py
  - packages/web/src/lib/chat-api.ts
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/components/chat-input.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/backend/meeting_playbook/advisor/base.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - packages/backend/meeting_playbook/chat/__init__.py
  - packages/backend/meeting_playbook/chat/repository.py
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/meeting_playbook/chat/router.py
tests:
  - packages/web/src/lib/chat-api.test.ts
  - packages/web/src/lib/session-ws.test.ts
  - packages/backend/tests/chat/test_repository.py
  - packages/web/src/components/chat-message-list.test.tsx
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/test_alembic_chat_message.py
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/chat/test_router.py
  - packages/backend/tests/chat/__init__.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/backend/tests/conftest.py
-->

---
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

<!-- @trace
source: slice-09-advisor-chatbox
updated: 2026-05-11
code:
  - packages/web/src/lib/session-ws.ts
  - docs/agents/advisor.md
  - packages/backend/meeting_playbook/chat/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/advisor/prompts.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/web/src/locales/en.json
  - packages/backend/alembic/versions/0005_create_chat_message.py
  - packages/web/src/lib/chat-api.ts
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/components/chat-input.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/backend/meeting_playbook/advisor/base.py
  - packages/backend/meeting_playbook/advisor/vertex_advisor.py
  - packages/backend/meeting_playbook/chat/__init__.py
  - packages/backend/meeting_playbook/chat/repository.py
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/meeting_playbook/chat/router.py
tests:
  - packages/web/src/lib/chat-api.test.ts
  - packages/web/src/lib/session-ws.test.ts
  - packages/backend/tests/chat/test_repository.py
  - packages/web/src/components/chat-message-list.test.tsx
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/backend/tests/test_alembic_chat_message.py
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/chat/test_router.py
  - packages/backend/tests/chat/__init__.py
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/advisor/test_vertex_advisor.py
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/backend/tests/advisor/test_prompts.py
  - packages/backend/tests/conftest.py
-->