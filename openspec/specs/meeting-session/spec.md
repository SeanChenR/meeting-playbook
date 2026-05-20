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


<!-- @trace
source: slice-13-voice-enrollment
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/voice_enrollment/router.py
  - packages/backend/meeting_playbook/voice_enrollment/repository.py
  - .spectra.yaml
  - packages/backend/meeting_playbook/voice_enrollment/__init__.py
  - packages/backend/uv.lock
  - packages/backend/alembic.ini
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/backend/meeting_playbook/voice_enrollment/matcher.py
  - docs/adr/README.md
  - packages/web/src/lib/wav-encoder.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/speaker/diarization.py
  - packages/backend/meeting_playbook/speaker/pyannote_provider.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - docs/adr/0029-hybrid-speaker-attribution.md
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/speaker/strategy.py
  - packages/backend/meeting_playbook/sessions/messages.py
  - packages/backend/meeting_playbook/speaker/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/lib/voice-enrollment-api.ts
  - packages/backend/alembic/versions/0010_relax_chunk_speaker_check.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/voice_enrollment/embedding.py
  - packages/backend/alembic/versions/0009_create_voice_enrollment.py
  - .env.example
  - README.md
  - packages/backend/meeting_playbook/voice_enrollment/models.py
tests:
  - packages/backend/tests/voice_enrollment/test_repository.py
  - packages/backend/tests/voice_enrollment/test_matcher.py
  - packages/backend/tests/speaker/test_diarization_protocol.py
  - packages/backend/tests/voice_enrollment/__init__.py
  - packages/web/src/lib/wav-encoder.test.ts
  - packages/backend/scripts/test_pyannote.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/speaker/test_finalize.py
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/test_alembic_voice_enrollment.py
  - packages/backend/tests/speaker/test_pyannote_provider.py
  - packages/backend/tests/speaker/test_strategy_protocol.py
  - packages/backend/tests/speaker/__init__.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/speaker/test_dual_channel_strategy.py
  - packages/web/src/routes/settings/voice.test.tsx
  - packages/backend/tests/sessions/test_messages.py
  - packages/backend/tests/speaker/test_single_channel_strategy.py
  - packages/backend/tests/speaker/test_select_strategy.py
  - packages/backend/tests/voice_enrollment/test_embedding.py
  - packages/backend/tests/voice_enrollment/test_router.py
  - packages/backend/tests/integration/__init__.py
-->

---
### Requirement: Audio capture writes one WAV file per session under RECORDINGS_DIR

The session SHALL persist each capture stream's audio as a separate mono WAV file under `{RECORDINGS_DIR}/{meeting_id}/`: the microphone stream at `me.wav` and the BlackHole stream at `counterparty.wav`. Each file MUST contain its stream's full captured content (16 kHz, mono, 16-bit PCM) and SHALL be finalized by the time the server emits `meeting_ended`. The directory SHALL be created on demand if it does not exist. The default value of `RECORDINGS_DIR` is `~/MeetingPlaybook/recordings`; deployments override via the `RECORDINGS_DIR` environment variable.

For each stream that produced any audio (even partial, after a `stream_stopped`) the session SHALL persist exactly one `recording` row whose `meeting_id` matches the session, `stream` equals `"me"` or `"counterparty"`, `file_path` equals the absolute on-disk WAV path for that stream, `bytes` equals the WAV file size on disk for that stream, and `started_at` equals the wall-clock UTC timestamp of the first sample written into that stream's WAV. A stream that produced zero bytes SHALL NOT cause a `recording` row to be written.

The `recording.started_at` column SHALL be `TIMESTAMPTZ NOT NULL`. The Alembic migration `0009_add_recording_started_at` SHALL add the column to the existing `recording` table; the up step SHALL first add the column as nullable, then backfill `started_at = created_at` for every existing row, then alter the column to `NOT NULL`. The down step SHALL drop the column. The migration MUST be reversible (up → down → up round-trip is a no-op against schema).

#### Scenario: Both WAV files exist after a successful dual-stream session

- **WHEN** a dual-stream meeting session ends successfully
- **THEN** both `{RECORDINGS_DIR}/{meeting_id}/me.wav` and `{RECORDINGS_DIR}/{meeting_id}/counterparty.wav` SHALL exist on disk, and exactly two `recording` rows SHALL exist (one with `stream = "me"`, one with `stream = "counterparty"`), each with `bytes` matching their on-disk file sizes, and each with `started_at` populated with the UTC timestamp of that stream's first captured sample

#### Scenario: One stream stopping mid-session still finalizes its partial WAV

- **GIVEN** the counterparty stream stops 90 seconds into a 5-minute session and the me stream completes normally
- **WHEN** the user ends the meeting
- **THEN** `{RECORDINGS_DIR}/{meeting_id}/counterparty.wav` SHALL contain approximately 90 seconds of audio (the partial capture), `me.wav` SHALL contain the full ~5 minutes, and two `recording` rows SHALL exist accordingly, each with its own `started_at` populated

#### Scenario: Recordings directory is created on demand

- **GIVEN** the `RECORDINGS_DIR` directory does NOT exist
- **WHEN** a meeting session starts
- **THEN** the directory SHALL be created (recursively) before any audio data is written, and the session SHALL proceed normally

#### Scenario: Migration backfills existing recording rows with started_at = created_at

- **GIVEN** a database at revision `0008_asr_default_qwen3` containing 4 existing `recording` rows (no `started_at` column)
- **WHEN** `alembic upgrade head` runs through `0009_add_recording_started_at`
- **THEN** all 4 rows SHALL have a non-NULL `started_at` value equal to their pre-migration `created_at`; the `recording.started_at` column SHALL have `is_nullable = NO` after the migration completes

#### Scenario: Migration down step drops the column

- **GIVEN** a database currently at revision `0009_add_recording_started_at`
- **WHEN** `alembic downgrade -1` runs
- **THEN** the `recording` table SHALL no longer have a `started_at` column; all existing `recording` rows SHALL otherwise be unchanged


<!-- @trace
source: slice-16-transcript-edit-and-playback
updated: 2026-05-15
code:
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/speaker/finalize.py
  - bun.lock
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/calendar/router.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - .env.example
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/components/ui/dialog.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/sessions/repository.py
tests:
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/audio_playback/__init__.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
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

Before opening any capture stream the session SHALL inspect the `mode` field of the accepted `start_meeting` frame and invoke a device-discovery routine accordingly.

When `mode == "dual"` the session SHALL locate a BlackHole device by name pattern. The routine SHALL match any input device whose `name` contains the substring `BlackHole` and whose `max_input_channels` is at least 2, OR the device whose name exactly equals the value of the optional `BLACKHOLE_DEVICE_NAME` environment variable when that variable is set. If no matching device exists, the session SHALL emit `{"type": "error", "error_code": "session.no_blackhole_device", "message": "<localized>"}` and close the WebSocket connection without writing any `recording` row, without transitioning the meeting status, and without spawning any capture task. The localized message SHALL include a hint that the user can switch to `single` mode as an alternative.

When `mode == "single"` the session MUST NOT invoke the BlackHole discovery routine and MUST NOT emit `session.no_blackhole_device` regardless of whether a BlackHole device is present, absent, or misconfigured. The microphone discovery routine SHALL still run in both modes; a missing microphone SHALL emit `error_code: session.no_audio_device` and abort the session in both modes.

The pre-flight SHALL NOT attempt to verify that the system audio output is routed through a Multi-Output Device in either mode.

#### Scenario: Missing BlackHole device aborts a dual-mode session

- **GIVEN** the host machine has no input device whose name contains `BlackHole`
- **WHEN** an authenticated owner sends `{"type": "start_meeting", "meeting_id": "m_abc", "mode": "dual"}`
- **THEN** the server SHALL respond with `{"type": "error", "error_code": "session.no_blackhole_device"}` and close the connection; the meeting row SHALL retain `status = "scheduled"` and no `recording` row SHALL be written

#### Scenario: Missing BlackHole device does NOT abort a single-mode session

- **GIVEN** the host machine has no input device whose name contains `BlackHole` and the microphone is available
- **WHEN** an authenticated owner sends `{"type": "start_meeting", "meeting_id": "m_abc", "mode": "single"}`
- **THEN** the server MUST NOT emit `session.no_blackhole_device`; the BlackHole discovery routine MUST NOT be invoked; the session SHALL proceed to open the microphone stream and emit `meeting_started`

#### Scenario: Missing microphone aborts both modes

- **GIVEN** the host has no system default input device and no `MIC_DEVICE_NAME` override that resolves
- **WHEN** an authenticated owner sends `start_meeting` in either `dual` or `single` mode
- **THEN** the server SHALL respond with `{"type": "error", "error_code": "session.no_audio_device"}` and close the connection; the meeting row SHALL retain `status = "scheduled"`

#### Scenario: BLACKHOLE_DEVICE_NAME env override locates a non-default device in dual mode

- **GIVEN** the host has two BlackHole-related devices and `BLACKHOLE_DEVICE_NAME=BlackHole 16ch` is set
- **WHEN** the dual-mode session pre-flight runs
- **THEN** the routine SHALL select the device named exactly `BlackHole 16ch` rather than the auto-detected `BlackHole 2ch` device

#### Scenario: BLACKHOLE_DEVICE_NAME env override is ignored in single mode

- **GIVEN** `BLACKHOLE_DEVICE_NAME=BlackHole 16ch` is set but no such device exists
- **WHEN** the user starts a session with `mode = "single"`
- **THEN** the env override SHALL NOT be consulted and the session SHALL start successfully on the microphone stream


<!-- @trace
source: single-channel-recording-entry
updated: 2026-05-19
code:
  - DESIGN.md
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/audio_playback/mixer.py
  - UI-OVERHAUL-DECISIONS.md
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/hooks/use-mini-player.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-mode-selector.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/sessions/messages.py
tests:
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/audio_playback/test_router_mixed.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/recording-mode-selector.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/audio_playback/test_mixer.py
  - packages/backend/tests/audio/test_capture_factory_single_mode.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/hooks/use-mini-player.test.ts
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
-->

---
### Requirement: Session captures BlackHole and microphone as two parallel streams with independent failure domains

For dual-mode sessions, the `SessionService` SHALL hold two `AudioCaptureService` instances: one for the microphone (stream label `me`, device resolved via `MIC_DEVICE_NAME` env override or `sounddevice.default.device[0]`) and one for BlackHole (stream label `counterparty`, device resolved per the pre-flight routine above). The two instances SHALL produce `AudioChunk` events independently, each labelled with its stream identifier. At session start both streams MUST successfully open their respective `RawInputStream` before the server emits `meeting_started`; if either fails to open the server SHALL emit `{"type": "error", "error_code": "session.stream_failed_at_start"}` and close the connection. Once the session is running, an exception in one stream's capture task SHALL stop only that stream — the other stream MUST continue producing chunks until the user ends the meeting OR the second stream also stops.

For single-mode sessions, the `SessionService` SHALL hold exactly ONE `AudioCaptureService` instance for the microphone (stream label `me`). No `counterparty` capture instance SHALL be constructed and the `providers` mapping SHALL contain only the `me` entry so the per-stream ASR routing invariant from the warmup requirement is preserved. The microphone stream MUST open successfully before the server emits `meeting_started`; if it fails to open the server SHALL emit `{"type": "error", "error_code": "session.stream_failed_at_start"}` and close the connection. At finalize, single-mode sessions SHALL produce at most ONE recording row with `stream = "me"`; no `counterparty` recording row SHALL be inserted.

#### Scenario: Both streams open and produce parallel chunks in dual mode

- **GIVEN** the host has both a working BlackHole device and a working microphone, and a meeting `m_abc` is in `scheduled` status
- **WHEN** the user starts the session in `dual` mode via WebSocket
- **THEN** the server SHALL emit `meeting_started` followed by `transcript_chunk` messages for both `speaker = "me"` and `speaker = "counterparty"`, each chunk derived only from its corresponding source stream

#### Scenario: One stream failing at start aborts the whole dual-mode session

- **GIVEN** the BlackHole device is present but the microphone open call raises (e.g., system permission revoked)
- **WHEN** the dual-mode session pre-flight plus `start()` runs
- **THEN** the server SHALL emit `{"type": "error", "error_code": "session.stream_failed_at_start"}` and close the connection without producing any `recording` row

#### Scenario: Single-mode session opens exactly one microphone stream

- **GIVEN** the host has a working microphone (BlackHole may or may not be present)
- **WHEN** the user starts the session in `single` mode via WebSocket
- **THEN** the server SHALL construct exactly one `AudioCaptureService` with `stream_label = "me"`, emit `meeting_started`, and emit `transcript_chunk` messages only for `speaker = "me"`; no `counterparty` chunk SHALL be sent

#### Scenario: Single-mode session writes exactly one recording row at finalize

- **GIVEN** a single-mode session has run and the user has ended the meeting
- **WHEN** the router runs the finalize block
- **THEN** the database SHALL contain exactly one new `recording` row for the meeting with `stream = "me"`, file path `{recordings_dir}/{meeting_id}/me.wav`, and no `counterparty` recording row


<!-- @trace
source: single-channel-recording-entry
updated: 2026-05-19
code:
  - DESIGN.md
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/audio_playback/mixer.py
  - UI-OVERHAUL-DECISIONS.md
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/hooks/use-mini-player.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-mode-selector.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/sessions/messages.py
tests:
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/audio_playback/test_router_mixed.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/recording-mode-selector.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/audio_playback/test_mixer.py
  - packages/backend/tests/audio/test_capture_factory_single_mode.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/hooks/use-mini-player.test.ts
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
-->

---
### Requirement: ASR runs through one ASRProvider instance per stream with parallel warmup

The `SessionService` SHALL maintain a mapping from stream identifier (`me` / `counterparty`) to an `ASRProvider` instance. After the asr-runtime extraction the concrete implementation SHALL be `RemoteAsrRuntimeClient` (one per stream) rather than an in-process model class — each stream owns its own WebSocket connection to the standalone ASR runtime so per-stream inference can proceed concurrently without sharing a single back-pressure queue.

Each `ASRProvider` SHALL expose an idempotent `warmup()` async method. For `RemoteAsrRuntimeClient`, `warmup()` SHALL poll `GET /healthz` against the runtime until `status == "ready"` (with a configurable timeout). During the connecting phase the session SHALL invoke both providers' `warmup()` calls in parallel via `asyncio.gather` so the first chunks are available without serial cold-start delay. Each captured `AudioChunk` SHALL be transcribed only by the provider mapped to that chunk's stream label.

#### Scenario: Warmup runs both providers in parallel

- **GIVEN** the session is starting and the runtime reports `status: loading` on first poll
- **WHEN** the session enters the connecting phase
- **THEN** both `provider.warmup()` calls SHALL be awaited via `asyncio.gather` (concurrently) and each provider SHALL stop polling as soon as the runtime reports `status: ready`

#### Scenario: Per-stream chunk routing

- **GIVEN** an active dual-stream session with provider A mapped to `me` and provider B mapped to `counterparty`
- **WHEN** the `me` capture emits five chunks and the `counterparty` capture emits five chunks
- **THEN** provider A SHALL receive exactly the five `me` chunks (and zero `counterparty` chunks) and provider B SHALL receive exactly the five `counterparty` chunks (and zero `me` chunks)

#### Scenario: Runtime unavailable during connecting phase aborts session start

- **GIVEN** the runtime process is not running (no listener on `ASR_RUNTIME_URL`)
- **WHEN** the WebSocket handler enters the connecting phase and calls `warmup()` on either provider
- **THEN** the provider SHALL raise `AsrRuntimeUnavailableError` within its configured warmup timeout
- **AND** the session handler SHALL emit a final `{"type": "error", "error_code": "asr.runtime_unavailable", ...}` frame and close the WebSocket cleanly
- **AND** no `transcript_chunk` frames SHALL be sent

#### Scenario: Runtime failure on a single chunk does not tear down the session

- **GIVEN** an active in-progress session with both providers warm
- **WHEN** the runtime returns `error_code: asr.runtime_unavailable` for one specific chunk (e.g. transient model error)
- **THEN** the session handler SHALL drop the failing chunk, emit a structlog warning carrying the chunk's `sequence`, and continue accepting subsequent chunks
- **AND** the WebSocket SHALL remain open


<!-- @trace
source: asr-runtime-extraction
updated: 2026-05-20
code:
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/server.py
  - packages/asr-runtime/uv.lock
  - packages/asr-runtime/meeting_playbook_asr_runtime/__init__.py
  - packages/backend/meeting_playbook/asr/factory.py
  - docs/adr/0030-asr-runtime-extraction.md
  - packages/backend/meeting_playbook/asr/remote_runtime_client.py
  - packages/web/src/components/meeting-detail-action-bar.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/schemas.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/asr-runtime/pyproject.toml
  - packages/asr-runtime/meeting_playbook_asr_runtime/errors.py
  - packages/asr-runtime/meeting_playbook_asr_runtime/routes/transcribe.py
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - package.json
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/backend/meeting_playbook/sessions/router.py
  - README.md
  - packages/asr-runtime/meeting_playbook_asr_runtime/qwen3_runner.py
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/routes/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - .env.example
tests:
  - packages/backend/tests/asr/test_factory.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/asr-runtime/tests/test_transcribe_http.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/asr-runtime/tests/test_transcribe_ws.py
  - packages/asr-runtime/tests/__init__.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/asr-runtime/tests/test_health.py
  - packages/backend/tests/asr/test_remote_runtime_client.py
  - packages/asr-runtime/tests/test_schemas.py
  - packages/asr-runtime/tests/test_qwen3_runner.py
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

---
### Requirement: Meeting end finalize spawns a fire-and-forget summary generation task

When the WebSocket session handler `meeting_session_endpoint` finishes its finalize block (recording rows persisted, meeting status transitioned to `completed`, `meeting_ended` frame sent, WebSocket closed), the handler SHALL invoke `summarization.runtime.spawn_summary_task(meeting_id)` BEFORE returning. The call SHALL be fire-and-forget — the handler MUST NOT `await` the spawned task. The spawned task runs in the background, and its outcome (success or failure) is observable only via `GET /api/meetings/{id}/summary` and the backend log.

The spawn SHALL run only when the meeting actually transitioned to `completed` during this session (not when status was already `completed` from a prior session, and not when finalize raised partway through). If `runtime.spawn_summary_task` returns `False` (a prior session's task is still running), the handler SHALL log an info-level message and proceed to return without raising.

The fire-and-forget invocation SHALL NOT introduce any new WebSocket frame, SHALL NOT delay the WebSocket close handshake, and SHALL NOT change the existing `meeting_ended` semantics.

#### Scenario: Successful end_meeting spawns a summary task without blocking the response

- **GIVEN** an `in_progress` WebSocket session
- **WHEN** the client sends `end_meeting` and the finalize block completes (status → completed, `meeting_ended` sent)
- **THEN** `runtime.is_pending(meeting_id)` SHALL return `True` immediately after the WebSocket closes AND the WebSocket close handshake SHALL NOT have been delayed by waiting on the summary generation

#### Scenario: end_meeting on an already-completed session does not double-spawn

- **GIVEN** a meeting whose status was already `completed` from a prior aborted attempt AND a summary task already running for it
- **WHEN** the WebSocket finalize block runs (which is a no-op for status transition because it's already completed)
- **THEN** `runtime.spawn_summary_task` SHALL return `False` AND the handler SHALL log an info message AND no second background task SHALL be created

#### Scenario: WebSocket close timing is independent of summary generation duration

- **GIVEN** a stub `MeetingSummarizer` whose `summarize` sleeps 30 seconds
- **WHEN** the client sends `end_meeting`
- **THEN** the WebSocket SHALL receive `meeting_ended` and close within 5 seconds (the same upper bound as without the summary spawn) AND the summary task SHALL still be running in the background

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
### Requirement: WebSocket connect resolves ASR providers via factory using meeting.asr_provider

The WS endpoint handler at `packages/backend/meeting_playbook/sessions/ws.py` (the `meeting_session_ws` route from slice-7) SHALL replace its current FastAPI `Depends(get_whisper_singleton_*)` dependency injection with a runtime call to `get_asr_providers_for_meeting(meeting.asr_provider)` from `packages/backend/meeting_playbook/asr/factory.py`. The call SHALL happen ONCE per WS connection, after the meeting row is loaded but before any audio frames are accepted.

The factory return value SHALL be a tuple `(me_provider: ASRProvider, counterparty_provider: ASRProvider)` — two independent provider instances so per-stream state (warmup status, sample-rate cache) does not leak across streams. The handler SHALL use these provider instances throughout the session lifetime; no second factory call SHALL fire for the same connection.

If the factory returns `None` providers (defensive — the fallback path means this SHALL NOT occur in practice), the handler SHALL close the WebSocket with code `1011` and an envelope `{error_code: "session.asr_unavailable", message: ...}`. This case is reserved for future providers that fail at construction time (e.g., model missing on disk).

#### Scenario: Connect to a qwen3-flagged meeting wires Qwen3 providers

- **GIVEN** a meeting with `asr_provider = "qwen3"`
- **WHEN** the client opens a WS connection to `/api/meetings/{id}/session`
- **THEN** the handler SHALL call `get_asr_providers_for_meeting("qwen3")` exactly once; the returned providers SHALL both be instances of `Qwen3ASRProvider`; the WS SHALL accept frames normally

#### Scenario: Connect to a whisper-flagged meeting wires Whisper providers

- **GIVEN** a meeting with `asr_provider = "whisper"`
- **WHEN** the client opens a WS connection
- **THEN** the handler SHALL call `get_asr_providers_for_meeting("whisper")` exactly once; the returned providers SHALL both be instances of `WhisperASRProvider`; the WS SHALL accept frames normally

#### Scenario: Connect to an unknown asr_provider value falls back to Whisper

- **GIVEN** a meeting whose `asr_provider` was somehow set to `"experimental_xyz"` (legacy value or admin override)
- **WHEN** the client opens a WS connection
- **THEN** the factory SHALL log a warning `unknown asr_provider 'experimental_xyz', falling back to whisper`; the providers SHALL be `WhisperASRProvider` instances; the WS SHALL accept frames normally

#### Scenario: Existing WS contract from slice-7..10 is preserved (no message-shape changes)

- **GIVEN** a connected WS session
- **WHEN** the client sends `audio_chunk_me` / `audio_chunk_counterparty` frames at 100ms cadence
- **THEN** the handler SHALL invoke the resolved provider's `transcribe_chunk` exactly as before; outgoing `transcript_chunk_me` / `transcript_chunk_counterparty` frames SHALL retain their slice-7 shape (`{type, started_at, ended_at, text}`) — slice-11 introduces NO changes to wire-level frame names or fields


<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->

---
### Requirement: Switching meeting.asr_provider mid-session has no effect on the live WS

A user switching the AsrProviderSelector dropdown (slice-11 detail-page UI) issues a PUT to `/api/meetings/{id}` that updates `meeting.asr_provider`. The WS session for that same meeting SHALL NOT pick up the change while still connected — the providers resolved at WS connect time SHALL remain in use until the WS closes. The new value takes effect on the NEXT WS connect (typically the user's next meeting).

This intentionally avoids tearing down the live providers mid-meeting (would drop in-flight chunks) and matches the AsrProviderSelector hint "切換下一場會議生效" / "Takes effect on the next meeting" (see meeting-detail-layout delta).

#### Scenario: Mid-session provider switch is ignored by the live WS

- **GIVEN** an active WS session for a meeting whose connect-time `asr_provider` was `"whisper"` (so both providers are WhisperASRProvider instances)
- **WHEN** the user PUTs `/api/meetings/{id}` with `{asr_provider: "qwen3"}` while the WS is still open
- **THEN** the persisted row SHALL update to `qwen3`; the live WS session SHALL continue using the WhisperASRProvider instances; subsequent `audio_chunk_*` frames SHALL still be transcribed by Whisper

#### Scenario: Reconnecting after a switch picks up the new provider

- **GIVEN** the previous scenario's switched-but-still-using-whisper session
- **WHEN** the WS closes and the user reconnects
- **THEN** the factory SHALL be called again; the returned providers SHALL be `Qwen3ASRProvider` instances reflecting the new `asr_provider = "qwen3"`

<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->

---
### Requirement: TranscriptPane SHALL render speaker contrast via all four visual cues simultaneously

The `TranscriptPane` component in `packages/web/src/components/transcript-pane.tsx` SHALL render each transcript chunk with the four visual cues from `ui-design-system` (3px left border, tinted background, speaker dot, semibold coloured name) — not the slice-7 single-border-only treatment.

The `data-speaker` attribute on each chunk wrapper SHALL be preserved (`"me"` | `"counterparty"`) so existing e2e selectors continue to resolve. The CSS class names that drove the slice-7 styling (e.g. `border-l-(--color-muted-foreground)`, `border-l-(--color-primary)`) SHALL be replaced by `border-l-(--color-me)` / `border-l-(--color-them)` tokens introduced in `ui-design-system`.

A `data-testid="speaker-dot"` element SHALL be inserted before each speaker name. Speaker names SHALL render with `font-weight: 600` in `--color-me` / `--color-them` (not the slice-7 muted-foreground).

The pane SHALL accept a new optional `contrastLevel?: "subtle" | "strong"` prop driven by the design-system tweak panel; when `"strong"` (default for production), the tint alphas SHALL come from the `[data-transcript-contrast="strong"]` overrides (`--me-tint-alpha: 0.14`, `--them-tint-alpha: 0.20`) declared in `ui-design-system`.

#### Scenario: Counterparty chunk renders all four cues plus data-testid speaker-dot

- **GIVEN** the transcript pane renders a chunk with `speaker = "counterparty"`, `name = "林經理"`, `text = "..."`
- **WHEN** the rendered DOM is inspected
- **THEN** the chunk wrapper SHALL have `data-speaker="counterparty"` AND `border-left-color` SHALL resolve to `--color-them` AND the inner content SHALL contain `[data-testid="speaker-dot"]` with background `--color-them` AND the speaker name element SHALL have `font-weight: 600` and colour `--color-them`

#### Scenario: Existing data-speaker selectors keep working

- **GIVEN** the e2e harness queries `[data-speaker="counterparty"]` to locate counterparty chunks
- **WHEN** the new TranscriptPane renders after this overhaul
- **THEN** the query SHALL still resolve to the same chunk wrapper elements (selector stability preserved across the visual rewrite)


<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: TranscriptPane re-run overlay SHALL animate in with framer-motion

The slice-11 re-run progress overlay (the skeleton + `重新轉錄中… (n/m chunks)` panel that appears while `meeting.rerun_asr_pending === true` OR polled `rerunStatus.status === "pending"`) SHALL animate in via framer-motion's `AnimatePresence` using the shared `paneEnter` preset (4px translateY + opacity, 180ms ease-out). When the polled status transitions to `idle`, the overlay SHALL animate out (reverse) before unmounting.

The progress counter inside the overlay SHALL use `magicui` `NumberTicker` for the `chunks_processed` numeral so the count change feels alive (tick from previous value to new value). The denominator (`chunks_total`) SHALL render as plain text since it changes at most once per task.

`data-testid="transcript-rerun-overlay"` SHALL remain on the overlay root element so existing component tests resolve it.

#### Scenario: Overlay animates in on rerun pending

- **GIVEN** the meeting is `rerun_asr_pending = false` AND the user has just clicked `重新轉錄`
- **WHEN** the meeting GET refetch returns `rerun_asr_pending = true`
- **THEN** the transcript pane SHALL render `[data-testid="transcript-rerun-overlay"]` with an enter animation (opacity 0 → 1, y 4 → 0 over ~180ms); without `prefers-reduced-motion` this SHALL be visible to the eye

#### Scenario: NumberTicker animates the chunks_processed numeral

- **GIVEN** the overlay is visible AND polled status reports `chunks_processed = 3, chunks_total = 10`
- **WHEN** the next poll reports `chunks_processed = 4`
- **THEN** the rendered numeral 3 SHALL animate up to 4 via `magicui` NumberTicker (not flash-replace) AND the slash + total `/10 chunks` SHALL re-render unchanged


<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: ChatBubble component SHALL replace flat advisor message list

The advisor pane (`packages/web/src/components/advisor-pane.tsx`) SHALL render the chat history using a new `ChatBubble` component supporting `role: "user" | "assistant"`:

- `role="user"`: right-aligned, background `--color-primary`, foreground `--color-primary-foreground`, border-radius `var(--radius-lg) var(--radius-lg) 4px var(--radius-lg)`, max-width 85%.
- `role="assistant"`: left-aligned, background `--color-surface-2`, foreground `--color-foreground`, border-radius `var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px`, 1px border in `--color-border`, max-width 85%.

Below the message list, a row of suggestion `Chip` buttons SHALL appear when the advisor is idle (`下一步該說什麼？` / `對方真正在意什麼？` / `幫我準備 closing` — pulled from the new `meetings.advisor.suggestions.*` i18n group). Clicking a chip SHALL prefill the input with that text and focus the input.

The input row SHALL stick to the bottom of the pane (matching the design bundle), with a single-line `<input>` flanked by a `Button` variant=`primary` size=`sm` icon=`Send` that submits on click or Enter keydown.

#### Scenario: User message renders right-aligned with primary background

- **GIVEN** the advisor pane has a message with `role = "user"` and `text = "如果他壓我先給 7% 怎麼辦？"`
- **WHEN** the message is rendered
- **THEN** the bubble SHALL have `align-self: flex-end` (or equivalent flex container property) AND background colour resolving to `--color-primary` AND foreground resolving to `--color-primary-foreground` AND `max-width: 85%`

#### Scenario: Suggestion chips prefill the input

- **GIVEN** the advisor pane is idle (no in-flight `request_advice`)
- **WHEN** the user clicks the chip labelled `下一步該說什麼？`
- **THEN** the input element SHALL receive focus AND its value SHALL be set to the chip text (allowing the user to edit before submitting)

<!-- @trace
source: ui-overhaul-claude-design
updated: 2026-05-12
code:
  - packages/web/src/components/chat-bubble.tsx
  - packages/web/src/components/animate-ui/route-transition.tsx
  - packages/web/src/components/advisor-pane.tsx
  - packages/web/src/components/ui/select.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - .agents/skills/shadcn/assets/shadcn.png
  - .agents/skills/shadcn/rules/base-vs-radix.md
  - skills-lock.json
  - .agents/skills/shadcn/evals/evals.json
  - .agents/skills/shadcn/SKILL.md
  - packages/web/src/components/capture-indicator.tsx
  - .agents/skills/framer-motion-animator/SKILL.md
  - packages/web/src/components/chat-input.tsx
  - .agents/skills/shadcn/rules/styling.md
  - packages/web/src/components/magicui/number-ticker.tsx
  - packages/web/src/routes/signup.tsx
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/locale-toggle.tsx
  - .agents/skills/shadcn/mcp.md
  - packages/web/src/components/ui/tooltip.tsx
  - packages/web/src/routes/totp/verify.tsx
  - .agents/skills/shadcn/assets/shadcn-small.png
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/routes/login.tsx
  - packages/web/src/components/ui/dropdown-menu.tsx
  - .agents/skills/shadcn/cli.md
  - .agents/skills/shadcn/agents/openai.yml
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/package.json
  - packages/web/src/components/pane.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/routes/meetings/list.tsx
  - .agents/skills/shadcn/customization.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/web/src/components/ui/skeleton.tsx
  - packages/web/src/locales/zh-TW.json
  - .agents/skills/frontend-design/LICENSE.txt
  - packages/web/src/components/chat-message-list.tsx
  - packages/web/src/components/auth-shell.tsx
  - packages/web/src/components/layout-switcher.tsx
  - .agents/skills/frontend-design/SKILL.md
  - packages/web/src/routes/meetings/calendar.tsx
  - bun.lock
  - .agents/skills/shadcn/rules/forms.md
  - .agents/skills/shadcn/rules/composition.md
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/components/theme-toggle.tsx
  - packages/web/src/components/back-link.tsx
  - packages/web/src/lib/theme-provider.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/locales/en.json
  - packages/web/src/components/workspace.tsx
  - packages/web/src/index.css
  - packages/web/src/App.tsx
  - packages/web/src/routes/totp/enroll.tsx
  - .agents/skills/shadcn/rules/icons.md
  - packages/web/src/components/ui/sonner.tsx
  - packages/web/src/lib/motion-presets.ts
tests:
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/components/protected-shell.test.tsx
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/web/src/hooks/use-meeting-session.test.tsx
  - packages/web/src/components/ui/primitives-smoke.test.tsx
  - packages/web/src/components/summary-pane.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/lib/auth-client.test.ts
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/test/fixtures/router.tsx
  - packages/web/src/components/advisor-pane.test.tsx
  - packages/web/src/routes/totp/enroll.test.tsx
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/playbook-api.queries.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/theme-toggle.test.tsx
  - packages/web/src/components/back-link.test.tsx
  - packages/web/src/routes/login.test.tsx
  - packages/web/src/components/workspace.test.tsx
  - packages/web/src/lib/theme-provider.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/routes/signup.test.tsx
  - packages/web/src/components/locale-toggle-integration.test.tsx
  - packages/web/src/components/magicui/number-ticker.test.tsx
  - packages/web/src/components/layout-switcher.test.tsx
  - packages/web/src/routes/totp/verify.test.tsx
  - packages/web/src/lib/motion-presets.test.ts
  - packages/web/src/components/chat-input.test.tsx
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/capture-indicator.test.tsx
  - packages/web/src/components/locale-toggle.test.tsx
  - packages/web/src/components/auth-shell.test.tsx
-->

---
### Requirement: transcript_chunk gains text_edited_at column tracking user edits

The `transcript_chunk` table SHALL gain a column `text_edited_at TIMESTAMPTZ NULL` (default NULL). The Alembic migration `0010_add_transcript_chunk_text_edited_at` SHALL add the column. New rows created during ASR transcription SHALL have `text_edited_at IS NULL`. Whenever the user successfully invokes `PATCH /api/meetings/{id}/transcript_chunks/{chunk_id}` (per the `transcript-edit` capability) the row's `text_edited_at` SHALL be set to the server's current UTC time. The column SHALL never be modified by any code path other than the transcript edit endpoint.

#### Scenario: Newly inserted ASR chunks have text_edited_at NULL

- **GIVEN** an in-progress meeting session running ASR
- **WHEN** the session writes a fresh `transcript_chunk` row
- **THEN** the row's `text_edited_at` SHALL be NULL

#### Scenario: Successful PATCH stamps text_edited_at with the server time

- **GIVEN** a chunk `c_1` with `text_edited_at IS NULL`
- **WHEN** the owner successfully PATCHes `c_1.text` to a new value
- **THEN** the row's `text_edited_at` SHALL become non-NULL and equal the server time at the moment of the successful update; the row's `text` SHALL equal the new value

<!-- @trace
source: slice-16-transcript-edit-and-playback
updated: 2026-05-15
code:
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/speaker/finalize.py
  - bun.lock
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/calendar/router.py
  - CONTEXT.md
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - .env.example
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/lib/transcripts-api.ts
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/components/ui/dialog.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/pyproject.toml
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/sessions/repository.py
tests:
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/audio_playback/__init__.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
-->

---
### Requirement: Pre-flight recording mode selector chooses dual-channel or single-channel capture

The meeting detail page SHALL render a Recording Mode selector while the meeting `status` is `scheduled`. The selector SHALL present exactly two mutually-exclusive options labelled per locale as Dual-channel capture (me + counterparty) and Single-channel (mic only). The default selection SHALL be `dual` for every new session and SHALL NOT be persisted across sessions or to server-side state. The selector SHALL be hidden (not just disabled) once `status` advances to `in_progress` or `completed`. The `HeadphonesHint` callout SHALL render ONLY when the selector value is `dual`.

The client SHALL include the selected mode in the `start_meeting` WebSocket frame as the field `mode` with the literal value `"dual"` or `"single"`. The backend Pydantic model for `StartMeetingMessage` SHALL accept `mode` with default `"dual"` when the field is absent (backwards compatibility for older clients), accept the literal values `"dual"` and `"single"`, and reject any other value with a `ValidationError` that the router maps to `error_code: session.unknown_message`. Once `start_meeting` has been accepted the mode SHALL be immutable for the lifetime of that WebSocket; no client frame, server frame, or REST endpoint SHALL mutate the live session's mode.

#### Scenario: Default mode is dual on a freshly opened scheduled meeting

- **GIVEN** a meeting `m_abc` with `status = "scheduled"`
- **WHEN** the user navigates to `/meetings/m_abc`
- **THEN** the Recording Mode selector SHALL be visible with `dual` selected and the `HeadphonesHint` callout SHALL be visible

#### Scenario: Switching to single hides the HeadphonesHint callout

- **GIVEN** the Recording Mode selector is visible with value `dual`
- **WHEN** the user picks the Single-channel option
- **THEN** the selector value SHALL change to `single` and the `HeadphonesHint` callout SHALL no longer render

#### Scenario: Selector value is sent with the start_meeting frame

- **GIVEN** the user has chosen Single-channel mode for meeting `m_abc`
- **WHEN** the user clicks Start Meeting
- **THEN** the WebSocket client SHALL send `{"type": "start_meeting", "meeting_id": "m_abc", "mode": "single"}` as the first frame after WS open

#### Scenario: Selector is hidden once the session starts

- **GIVEN** a meeting whose `status` has just advanced to `in_progress`
- **WHEN** the meeting detail page re-renders
- **THEN** the Recording Mode selector SHALL NOT be rendered and the user MUST NOT have any UI affordance to change `mode` mid-session

#### Scenario: Backwards-compatible start frame with no mode field defaults to dual

- **GIVEN** an older client that has not been updated
- **WHEN** the server receives `{"type": "start_meeting", "meeting_id": "m_abc"}` (no `mode` field)
- **THEN** the backend Pydantic parser SHALL accept the frame and treat `mode` as `"dual"`; the dual-channel pre-flight path (BlackHole + microphone) SHALL run unchanged

#### Scenario: Invalid mode value is rejected before any session state changes

- **WHEN** the server receives `{"type": "start_meeting", "meeting_id": "m_abc", "mode": "invalid"}`
- **THEN** the server SHALL emit `{"type": "error", "error_code": "session.unknown_message"}` and close the WebSocket; the meeting row SHALL retain `status = "scheduled"` and no `recording` row SHALL be written

#### Scenario: Mode does not persist across sessions

- **GIVEN** a meeting `m_abc` whose previous session ran in `single` mode and ended
- **WHEN** the user starts a new session on a different meeting OR re-opens `/meetings/m_abc` after `m_abc` has been re-scheduled
- **THEN** the Recording Mode selector SHALL default to `dual` for the new session

##### Example: mode field boundary cases

| Incoming start_meeting frame | Parsed `mode` | Pre-flight check | Outcome |
| ---------------------------- | ------------- | ---------------- | ------- |
| `{"type":"start_meeting","meeting_id":"x"}` | `"dual"` (default) | BlackHole + mic | dual-channel session starts |
| `{"type":"start_meeting","meeting_id":"x","mode":"dual"}` | `"dual"` | BlackHole + mic | dual-channel session starts |
| `{"type":"start_meeting","meeting_id":"x","mode":"single"}` | `"single"` | mic only (NO BlackHole check) | single-channel session starts |
| `{"type":"start_meeting","meeting_id":"x","mode":"both"}` | rejected | n/a | `session.unknown_message`; status stays `scheduled` |
| `{"type":"start_meeting","meeting_id":"x","mode":null}` | rejected | n/a | `session.unknown_message`; status stays `scheduled` |

<!-- @trace
source: single-channel-recording-entry
updated: 2026-05-19
code:
  - DESIGN.md
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/audio_playback/mixer.py
  - UI-OVERHAUL-DECISIONS.md
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/hooks/use-meeting-session.ts
  - packages/web/src/hooks/use-mini-player.ts
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-mode-selector.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/sessions/messages.py
tests:
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/audio_playback/test_router_mixed.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/lib/session-ws.test.ts
  - packages/web/src/components/recording-mode-selector.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/audio_playback/test_mixer.py
  - packages/backend/tests/audio/test_capture_factory_single_mode.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/hooks/use-mini-player.test.ts
  - packages/backend/tests/sessions/test_messages.py
  - packages/web/src/hooks/use-meeting-session.test.tsx
-->