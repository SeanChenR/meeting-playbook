## MODIFIED Requirements

### Requirement: WebSocket message contract for the meeting session

The WebSocket connection SHALL carry JSON messages tagged by a `type` field. The contract is:

Client → server messages:
- `{"type": "start_meeting", "meeting_id": "<id>"}` — opens a new session for the meeting
- `{"type": "end_meeting", "meeting_id": "<id>"}` — finalizes the session
- `{"type": "request_advice", "request_id": "<uuid>", "locale": "zh-TW"|"en", "user_question"?: "<string>"}` — requests a tactical advisor reply for the current meeting context. `user_question` is optional and reserved for the chatbox follow-up shipped in a later slice; in the slice that introduces this frame it is always omitted.

Server → client messages:
- `{"type": "meeting_started", "meeting_id": "<id>"}` — sent immediately after the server accepts a `start_meeting` message and transitions the meeting to `in_progress`
- `{"type": "transcript_chunk", "meeting_id": "<id>", "speaker": "<speaker_label>", "text": "<string>", "started_at": "<iso8601>", "ended_at": "<iso8601>", "asr_provider_used": "<string>", "confidence": <float|null>}` — one per ~10-second audio chunk per stream. The `speaker` value SHALL be one of: `"me"`, `"counterparty"`, `"speaker_cluster_<N>"` where `<N>` is a 1-based integer assigned by `SingleChannelStrategy`, or `"speaker_cluster_unknown"` when no diarization segment overlaps the chunk window. Dual-channel sessions SHALL produce only `"me"` and `"counterparty"` values. Single-channel sessions SHALL produce only `"speaker_cluster_*"` values when the current user has NO voice enrollment row; when an enrollment exists and a single-channel cluster matches the enrolled embedding above threshold, the matching cluster's chunks MAY carry `"me"` in place of `"speaker_cluster_<N>"` (the matching is applied at finalize time per the `voice-enrollment` capability).
- `{"type": "silence_warning", "meeting_id": "<id>", "stream": "me"|"counterparty", "since": "<iso8601>"}` — emitted when one stream has been silent for more than 30 seconds; the `stream` field identifies which stream is silent so the client can update only that capture indicator. This frame SHALL NOT be emitted in single-channel sessions.
- `{"type": "stream_stopped", "meeting_id": "<id>", "stream": "me"|"counterparty", "reason": "<string>"}` — emitted when one capture stream fails mid-session and stops; the WebSocket SHALL remain open until both streams have stopped. This frame SHALL NOT be emitted in single-channel sessions.
- `{"type": "advice_chunk", "request_id": "<uuid>", "token": "<string>"}` — emitted per Vertex Flash SDK chunk during a streaming advice request; multiple frames make up one advice reply
- `{"type": "advice_done", "request_id": "<uuid>"}` — terminal frame for a successful advice stream; the client uses it to flip the corresponding card from `streaming` to `done` and re-enable the Get Advice button
- `{"type": "advisor_failed", "request_id": "<uuid>", "error_code": "<code>", "message": "<string>"}` — emitted when the advisor coroutine raises; `error_code` is one of `advisor.timeout`, `advisor.quota`, `advisor.auth`, `advisor.unknown`. Receiving this frame MUST NOT cause the WebSocket to close — the meeting session continues, only the failing advice card is marked
- `{"type": "meeting_ended", "meeting_id": "<id>"}` — sent after the server finalizes the WAV file(s) and transitions the meeting to `completed`
- `{"type": "error", "error_code": "<code>", "message": "<string>"}` — emitted when an unrecoverable failure occurs; the connection SHALL be closed by the server immediately afterward

Unknown message types from the client SHALL cause the server to respond with `{"type": "error", "error_code": "session.unknown_message"}` and close the connection.

The server SHALL select the speaker attribution strategy at session finalize time by calling `select_strategy(recordings)` on the meeting's persisted recordings, then `assign_speakers(...)` to determine the `speaker` value written to each `transcript_chunk` row before the chunk is emitted to the client. For single-channel sessions where a `voice_enrollment` row exists for the current user, the finalize step SHALL additionally consult `VoiceEnrollmentMatcher` and rename the matching cluster's chunks from `"speaker_cluster_<N>"` to `"me"` before the meeting transitions to `completed`. A session whose recording configuration is neither dual-channel (`{me, counterparty}`) nor single-channel (exactly one recording) SHALL cause the server to emit `{"type": "error", "error_code": "session.invalid_speaker_configuration"}` and close the connection.

#### Scenario: First client message must be start_meeting matching the path id

- **GIVEN** a WebSocket connected to `/api/meetings/m_abc/session`
- **WHEN** the client sends `{"type": "start_meeting", "meeting_id": "m_xyz"}` (id mismatch)
- **THEN** the server SHALL send `{"type": "error", "error_code": "session.bad_start"}` and close the connection

#### Scenario: Successful dual-stream session emits the expected message sequence

- **GIVEN** an authenticated owner connects, sends `start_meeting`, both streams capture three audio chunks each, the user sends `end_meeting`
- **WHEN** the session runs to completion
- **THEN** the server SHALL emit `meeting_started` first, then six `transcript_chunk` messages (three with `speaker = "me"`, three with `speaker = "counterparty"`) ordered by their `started_at` timestamps, then `meeting_ended`, then close the connection

#### Scenario: Successful single-channel session without enrollment emits speaker_cluster labels

- **GIVEN** an authenticated owner with NO `voice_enrollment` row connects, sends `start_meeting`, only the microphone stream captures audio over a five-minute session containing two speakers, the user sends `end_meeting`
- **WHEN** the session runs to completion and the diarization pass produces two clusters
- **THEN** every `transcript_chunk` server message SHALL carry `speaker` matching the regex `^speaker_cluster_(\d+|unknown)$`; no message SHALL carry `speaker = "me"` or `speaker = "counterparty"`

#### Scenario: Single-channel session with enrollment renames the matching cluster to me

- **GIVEN** an authenticated owner WITH a `voice_enrollment` row connects, sends `start_meeting`, only the microphone stream captures audio in a five-minute session containing two speakers (one of whom is the enrolled user), the user sends `end_meeting`
- **WHEN** the session runs to completion, the diarization pass produces two clusters, and the matcher identifies cluster 1 as the enrolled user above threshold
- **THEN** every `transcript_chunk` row originating from cluster 1 SHALL carry `speaker = "me"` in DB; the other cluster's chunks SHALL retain `speaker = "speaker_cluster_<N>"`; no chunk SHALL carry `speaker = "counterparty"`

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

#### Scenario: Invalid recording configuration aborts session finalize with explicit error

- **GIVEN** a meeting session about to finalize whose recordings contain three rows (neither dual-channel nor single-channel)
- **WHEN** the server invokes `select_strategy(recordings)` and receives `InvalidSpeakerConfiguration`
- **THEN** the server SHALL emit `{"type": "error", "error_code": "session.invalid_speaker_configuration"}` and close the connection without emitting `meeting_ended`

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
