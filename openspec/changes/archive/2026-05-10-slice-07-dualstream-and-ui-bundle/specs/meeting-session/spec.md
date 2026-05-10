## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: WebSocket message contract for the meeting session

The WebSocket connection SHALL carry JSON messages tagged by a `type` field. The contract is:

Client → server messages:
- `{"type": "start_meeting", "meeting_id": "<id>"}` — opens a new session for the meeting
- `{"type": "end_meeting", "meeting_id": "<id>"}` — finalizes the session

Server → client messages:
- `{"type": "meeting_started", "meeting_id": "<id>"}` — sent immediately after the server accepts a `start_meeting` message and transitions the meeting to `in_progress`
- `{"type": "transcript_chunk", "meeting_id": "<id>", "speaker": "me"|"counterparty", "text": "<string>", "started_at": "<iso8601>", "ended_at": "<iso8601>", "asr_provider_used": "<string>", "confidence": <float|null>}` — one per ~10-second audio chunk per stream; `speaker` value reflects the source stream
- `{"type": "silence_warning", "meeting_id": "<id>", "stream": "me"|"counterparty", "since": "<iso8601>"}` — emitted when one stream has been silent for more than 30 seconds; the `stream` field identifies which stream is silent so the client can update only that capture indicator
- `{"type": "stream_stopped", "meeting_id": "<id>", "stream": "me"|"counterparty", "reason": "<string>"}` — emitted when one capture stream fails mid-session and stops; the WebSocket SHALL remain open until both streams have stopped
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

##### Example: minimum required keys per server-side message type

| `type`              | Required keys                                                                                              |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| `meeting_started`   | `type`, `meeting_id`                                                                                       |
| `transcript_chunk`  | `type`, `meeting_id`, `speaker`, `text`, `started_at`, `ended_at`, `asr_provider_used`, `confidence`       |
| `silence_warning`   | `type`, `meeting_id`, `stream`, `since`                                                                    |
| `stream_stopped`    | `type`, `meeting_id`, `stream`, `reason`                                                                   |
| `meeting_ended`     | `type`, `meeting_id`                                                                                       |
| `error`             | `type`, `error_code`, `message`                                                                            |

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
