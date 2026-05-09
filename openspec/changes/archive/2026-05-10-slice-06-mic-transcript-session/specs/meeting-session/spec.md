## ADDED Requirements

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

---

### Requirement: WebSocket message contract for the meeting session

The WebSocket connection SHALL carry JSON messages tagged by a `type` field. The contract is:

Client → server messages:
- `{"type": "start_meeting", "meeting_id": "<id>"}` — opens a new session for the meeting
- `{"type": "end_meeting", "meeting_id": "<id>"}` — finalizes the session

Server → client messages:
- `{"type": "meeting_started", "meeting_id": "<id>"}` — sent immediately after the server accepts a `start_meeting` message and transitions the meeting to `in_progress`
- `{"type": "transcript_chunk", "meeting_id": "<id>", "speaker": "me", "text": "<string>", "started_at": "<iso8601>", "ended_at": "<iso8601>", "asr_provider_used": "<string>", "confidence": <float|null>}` — one per ~10-second audio chunk
- `{"type": "silence_warning", "meeting_id": "<id>", "since": "<iso8601>"}` — emitted when the audio stream has been silent for more than 30 seconds
- `{"type": "meeting_ended", "meeting_id": "<id>"}` — sent after the server finalizes the WAV file and transitions the meeting to `completed`
- `{"type": "error", "error_code": "<code>", "message": "<string>"}` — emitted when an unrecoverable failure occurs; the connection SHALL be closed by the server immediately afterward

Unknown message types from the client SHALL cause the server to respond with `{"type": "error", "error_code": "session.unknown_message"}` and close the connection.

#### Scenario: First client message must be start_meeting matching the path id

- **GIVEN** a WebSocket connected to `/api/meetings/m_abc/session`
- **WHEN** the client sends `{"type": "start_meeting", "meeting_id": "m_xyz"}` (id mismatch)
- **THEN** the server SHALL send `{"type": "error", "error_code": "session.bad_start"}` and close the connection

#### Scenario: Successful session emits the expected message sequence

- **GIVEN** an authenticated owner connects, sends `start_meeting`, the session captures three audio chunks, the user sends `end_meeting`
- **WHEN** the session runs to completion
- **THEN** the server SHALL emit `meeting_started` first, then exactly three `transcript_chunk` messages in chronological order, then `meeting_ended`, then close the connection

##### Example: minimum required keys per server-side message type

| `type`              | Required keys                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `meeting_started`   | `type`, `meeting_id`                                                                                       |
| `transcript_chunk`  | `type`, `meeting_id`, `speaker`, `text`, `started_at`, `ended_at`, `asr_provider_used`, `confidence`       |
| `silence_warning`   | `type`, `meeting_id`, `since`                                                                              |
| `meeting_ended`     | `type`, `meeting_id`                                                                                       |
| `error`             | `type`, `error_code`, `message`                                                                            |

---

### Requirement: Audio capture writes one WAV file per session under RECORDINGS_DIR

The session SHALL persist the captured microphone audio as a single WAV file at `{RECORDINGS_DIR}/{meeting_id}/me.wav`. The file MUST contain the entire captured stream (16 kHz, mono, 16-bit PCM) and SHALL be finalized by the time the server emits `meeting_ended`. The directory SHALL be created on demand if it does not exist. The default value of `RECORDINGS_DIR` is `~/MeetingPlaybook/recordings`; deployments override via the `RECORDINGS_DIR` environment variable.

The session SHALL also persist a `recording` row whose `meeting_id` matches the session, `stream` equals `"me"`, `file_path` equals the absolute on-disk WAV path, and `bytes` equals the WAV file size on disk.

#### Scenario: WAV file exists after meeting_ended

- **WHEN** a meeting session ends successfully
- **THEN** the file `{RECORDINGS_DIR}/{meeting_id}/me.wav` SHALL exist on disk and a corresponding row SHALL exist in the `recording` table with `stream = "me"` and `bytes` matching the on-disk file size

#### Scenario: Recordings directory is created on demand

- **GIVEN** the `RECORDINGS_DIR` directory does NOT exist
- **WHEN** a meeting session starts
- **THEN** the directory SHALL be created (recursively) before any audio data is written, and the session SHALL proceed normally

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

---

### Requirement: Silence in the audio stream is reported within 30 seconds

When the captured audio stream's RMS amplitude stays below the silence threshold for more than 30 consecutive seconds, the server SHALL emit a `silence_warning` message with a `since` timestamp marking when the silence began. Subsequent `silence_warning` messages MAY be sent at most once per 30-second silence window so the client is not spammed. When audio resumes (RMS rises above threshold), no clearance message is sent — the client infers resumption from the next `transcript_chunk`.

#### Scenario: 30-second silence triggers a warning

- **GIVEN** a session is in progress and the input device produces silence for 30 consecutive seconds
- **WHEN** the silence threshold is crossed
- **THEN** the server SHALL emit one `silence_warning` message with `since` equal to the timestamp at which silence began

#### Scenario: Continuing silence does not flood the client

- **GIVEN** silence has already triggered one `silence_warning`
- **WHEN** silence continues for another 60 seconds
- **THEN** the server SHALL emit at most one additional `silence_warning` (not three), preserving the original `since` timestamp

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

---

### Requirement: TranscriptPane renders chunks with the meeting's me display name

The component `TranscriptPane(chunks, meDisplayName)` SHALL render every chunk in chronological order. Each rendered chunk SHALL display the speaker's display name; for slice-6 every chunk SHALL be shown with the meeting's `me_display_name` (already populated by slice-05 from the Better Auth user.name). The component layout SHALL accommodate a future `counterparty` speaker without code changes (slice-7), by reading speaker from the chunk shape.

#### Scenario: Empty chunks renders an empty state

- **GIVEN** an empty `chunks` array
- **WHEN** the component renders
- **THEN** it SHALL render a placeholder element (not crash and not render an empty list element)

#### Scenario: Chunks attributed to me_display_name

- **GIVEN** `meDisplayName = "Sean Chen"` and three chunks with `speaker = "me"`
- **WHEN** the component renders
- **THEN** each rendered chunk SHALL include the visible string `"Sean Chen"` as its speaker attribution
