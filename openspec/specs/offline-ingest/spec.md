# offline-ingest Specification

## Purpose

TBD - created by archiving change 'slice-14-offline-ingest'. Update Purpose after archive.

## Requirements

### Requirement: recording table tracks live vs offline source

The backend SHALL persist `Recording.source` as a `TEXT NOT NULL DEFAULT 'live' CHECK (source IN ('live','offline'))` column. Existing rows SHALL be back-filled to `'live'`. The backend SHALL persist `Recording.started_at` as a `TIMESTAMPTZ NULL` column carrying the wall-clock moment that audio was captured (live capture writes the moment capture started; offline ingest writes the user-supplied "actual started at"). Migration `0011_recording_source_and_started_at.py` SHALL be reversible: `downgrade` SHALL drop the CHECK constraint, `source`, and `started_at` columns in that order.

#### Scenario: Existing live recordings back-fill as live source

- **GIVEN** a `recording` row written before migration 0011 has no `source` value
- **WHEN** alembic upgrade to 0011 runs
- **THEN** the row's `source` SHALL equal `'live'` AND the `started_at` column SHALL be NULL until live capture is updated to populate it

#### Scenario: Source column rejects values outside live or offline

- **GIVEN** the recording table after migration 0011
- **WHEN** an `INSERT` with `source = 'streamed'` runs
- **THEN** the database SHALL reject the row with a CHECK constraint violation referencing `recording_source_check`


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: POST /api/meetings/{id}/recordings/offline_upload speaks tus 1.0 creation protocol

The backend SHALL expose a tus 1.0.0 protocol endpoint at `POST /api/meetings/{id}/recordings/offline_upload` honouring the `Tus-Resumable: 1.0.0` header. `OPTIONS` SHALL advertise `Tus-Resumable: 1.0.0`, `Tus-Version: 1.0.0`, `Tus-Max-Size: <OFFLINE_UPLOAD_MAX_BYTES>`, and `Tus-Extension: creation,termination`. `POST` SHALL create a new upload session, require headers `Upload-Length` (bytes) and `Upload-Metadata` (base64 key-value pairs including `filename`, `mimetype`, and `actual_started_at`), and respond with HTTP 201 carrying `Location: /api/meetings/{id}/recordings/offline_upload/{upload_id}`. The endpoint SHALL reject the upload with HTTP 422 `offline_ingest.unsupported_format` when the `mimetype` is outside the allowed set (`audio/wav`, `audio/mpeg`, `audio/mp4`, `audio/aac`, `audio/flac`, `audio/ogg`), HTTP 413 `offline_ingest.too_large` when `Upload-Length` exceeds `OFFLINE_UPLOAD_MAX_BYTES`, HTTP 422 `offline_ingest.invalid_started_at` when `actual_started_at` is not ISO 8601 or is in the future, and HTTP 409 `offline_ingest.conditions_not_met` when the meeting's status is not `scheduled` or `now < scheduled_end_at` or the meeting already has a recording.

#### Scenario: Valid creation returns 201 with upload Location

- **GIVEN** a meeting `m_a` owned by the caller with `status = "scheduled"` and `scheduled_end_at` already in the past and no recording rows
- **WHEN** the caller POSTs with `Upload-Length: 5242880`, `Upload-Metadata: filename d2hhdGV2ZXIubXAz,mimetype YXVkaW8vbXBlZw==,actual_started_at MjAyNi0wNS0xNVQwOTowMDowMFo=`
- **THEN** the response SHALL be HTTP 201 with a `Location` header matching `/api/meetings/m_a/recordings/offline_upload/[a-zA-Z0-9_-]+` AND `Tus-Resumable: 1.0.0`

#### Scenario: Upload-Length over the max returns 413

- **GIVEN** `OFFLINE_UPLOAD_MAX_BYTES = 524288000`
- **WHEN** the caller POSTs with `Upload-Length: 800000000`
- **THEN** the response SHALL be HTTP 413 with `error_code = "offline_ingest.too_large"` and NO upload session SHALL be created

#### Scenario: Unsupported mimetype returns 422

- **GIVEN** a valid meeting
- **WHEN** the caller POSTs with `Upload-Metadata` containing `mimetype: video/mp4`
- **THEN** the response SHALL be HTTP 422 with `error_code = "offline_ingest.unsupported_format"`

#### Scenario: Banner conditions no longer met returns 409

- **GIVEN** a meeting whose `status` flipped to `in_progress` after the user opened the upload dialog but before submission
- **WHEN** the caller POSTs to create an upload session
- **THEN** the response SHALL be HTTP 409 with `error_code = "offline_ingest.conditions_not_met"`


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: PATCH and HEAD endpoints honour tus resumable chunk semantics

The backend SHALL accept `HEAD /api/meetings/{id}/recordings/offline_upload/{upload_id}` and reply with `Upload-Offset` (the number of bytes already received) plus `Upload-Length` and `Tus-Resumable: 1.0.0`. The backend SHALL accept `PATCH /api/meetings/{id}/recordings/offline_upload/{upload_id}` with `Content-Type: application/offset+octet-stream` and `Upload-Offset` matching the server's current offset; the body bytes SHALL be appended to the staging file at `{OFFLINE_UPLOAD_DIR}/{upload_id}.partial`. After PATCH succeeds the response SHALL be HTTP 204 with the new `Upload-Offset` echoed. When `Upload-Offset` from the client does not match the server's current offset, the response SHALL be HTTP 409 with `Tus-Resumable: 1.0.0`. When PATCH brings the staging file size up to `Upload-Length`, the backend SHALL trigger the post-upload pipeline (transcode → ASR background task) and respond 204.

#### Scenario: HEAD before any PATCH returns offset zero

- **GIVEN** a newly created upload session
- **WHEN** the caller HEADs `/api/meetings/{id}/recordings/offline_upload/{upload_id}`
- **THEN** the response SHALL include `Upload-Offset: 0` and `Upload-Length: <the original length>` and `Tus-Resumable: 1.0.0`

#### Scenario: PATCH appends bytes and advances offset

- **GIVEN** a session with current offset 0 and `Upload-Length: 1048576`
- **WHEN** the caller PATCHes with `Upload-Offset: 0` and a 524288-byte body
- **THEN** the response SHALL be HTTP 204 with `Upload-Offset: 524288` AND the staging file size SHALL be 524288 bytes

#### Scenario: Mismatched offset rejected for resume safety

- **GIVEN** a session with current offset 524288
- **WHEN** the caller PATCHes with `Upload-Offset: 0`
- **THEN** the response SHALL be HTTP 409 and the staging file SHALL remain at 524288 bytes (no truncation)

#### Scenario: Completing PATCH triggers downstream pipeline

- **GIVEN** a session with offset = `Upload-Length` - 1 byte
- **WHEN** the caller PATCHes the final byte
- **THEN** the response SHALL be HTTP 204 AND the offline ingest pipeline SHALL be invoked (transcode → recording row write → ASR background task spawn) AND a subsequent `GET /api/meetings/{id}/offline_ingest_progress` SHALL return `state` matching one of `"transcoding"|"asr_running"|"completed"`


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: ffmpeg subprocess normalises to 16kHz mono WAV

After the staging file is complete, the backend SHALL invoke ffmpeg via `asyncio.create_subprocess_exec("ffmpeg", "-i", staging_path, "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", "-f", "wav", output_path)`. When ffmpeg exits with a non-zero return code, the pipeline SHALL unlink the staging file, leave any partial output file removed, raise `OfflineIngestTranscodeError` carrying the ffmpeg stderr tail, and set the progress endpoint state to `"failed"` with `error_code = "offline_ingest.transcode_failed"`. When ffmpeg succeeds, the staging file SHALL be unlinked and the WAV file SHALL be persisted under `{OFFLINE_UPLOAD_DIR}/{meeting_id}/source.wav`.

#### Scenario: Successful transcode writes the canonical WAV path

- **GIVEN** a completed upload of a 30-second valid MP3
- **WHEN** the pipeline runs ffmpeg
- **THEN** the file at `{OFFLINE_UPLOAD_DIR}/{meeting_id}/source.wav` SHALL exist, SHALL be a 16kHz mono 16-bit PCM WAV (verifiable via `wave.open` header), AND the staging `.partial` file SHALL be deleted

#### Scenario: ffmpeg failure surfaces transcode error

- **GIVEN** a staging file that is not a valid audio container (e.g., truncated MP3)
- **WHEN** the pipeline invokes ffmpeg
- **THEN** ffmpeg SHALL exit with non-zero return code AND the pipeline SHALL raise `OfflineIngestTranscodeError` AND the progress endpoint SHALL return `state = "failed"` with `error_code = "offline_ingest.transcode_failed"`


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: Post-transcode duration enforcement

After ffmpeg produces the canonical WAV, the pipeline SHALL inspect duration via `wave.open(...).getnframes() / .getframerate()`. When duration exceeds `OFFLINE_UPLOAD_MAX_DURATION_SECONDS`, the pipeline SHALL unlink the WAV, NOT write a `recording` row, set progress endpoint state to `"failed"` with `error_code = "offline_ingest.too_long"`, and surface the duration in the error message.

#### Scenario: Duration over budget rejects without recording row

- **GIVEN** `OFFLINE_UPLOAD_MAX_DURATION_SECONDS = 10800` and a transcoded WAV whose duration is 14400 seconds (4 hours)
- **WHEN** the duration check runs
- **THEN** the WAV file SHALL be deleted AND no `recording` row SHALL be inserted for the meeting AND `GET /api/meetings/{id}/offline_ingest_progress` SHALL return `state = "failed"` with `error_code = "offline_ingest.too_long"`


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: Pipeline writes a single offline recording row and spawns ASR task

When transcode succeeds and duration is within budget, the pipeline SHALL insert exactly one `recording` row with `source = "offline"`, `stream = "me"`, `started_at` set from the user-supplied `actual_started_at`, `file_path` equal to `{OFFLINE_UPLOAD_DIR}/{meeting_id}/source.wav`, and `bytes` equal to the WAV file size on disk. The pipeline SHALL set the meeting's `status` to `in_progress`. Then the pipeline SHALL spawn an async ASR background task following the `meeting_playbook.rerun.runtime` pattern (in-flight registry keyed by `meeting_id`, `ChunksProgress(processed, total)` map, idempotent spawn).

The ASR task SHALL invoke `RemoteAsrRuntimeClient.transcribe_chunk` against the standalone ASR runtime over its HTTP endpoint (`POST /v1/transcribe/chunk`) for each segmented chunk; the backend SHALL NOT load the Qwen3 model in-process. When the runtime returns `error_code: asr.runtime_unavailable` for a chunk, the task SHALL retry that chunk up to 3 times with exponential backoff (2s → 4s → 8s) before marking the task `failed` and writing `error_code = "asr.runtime_unavailable"` into the `offline_ingest_progress` row. On task completion (no retriable failures) the meeting status SHALL transition to `completed` and `transcript_chunk` rows SHALL exist whose `speaker` values match `^speaker_cluster_(\d+|unknown)$` per the `speaker-attribution-strategy` capability.

#### Scenario: Pipeline writes exactly one offline recording row

- **GIVEN** a meeting `m_b` that just completed transcode of a 60-second WAV
- **WHEN** the pipeline runs the recording-write step
- **THEN** `SELECT COUNT(*) FROM recording WHERE meeting_id = 'm_b'` SHALL equal 1 AND the row SHALL have `source = 'offline'`, `stream = 'me'`, `started_at IS NOT NULL`, `bytes > 0`, AND the meeting's `status` SHALL be `in_progress`

#### Scenario: ASR task spawns with single-channel strategy via remote runtime

- **GIVEN** a fresh offline recording row written for meeting `m_b`
- **WHEN** the ASR background task runs to completion
- **THEN** each chunk SHALL be transcribed via an HTTP POST to the standalone ASR runtime
- **AND** `transcript_chunk` rows SHALL exist for `m_b` whose `speaker` values match `^speaker_cluster_(\d+|unknown)$`
- **AND** the meeting's `status` SHALL be `completed`

#### Scenario: Concurrent spawn returns busy error

- **GIVEN** an ASR task already in-flight for meeting `m_b`
- **WHEN** a second offline upload completes for the same meeting before the first ASR task finishes
- **THEN** the second spawn SHALL be rejected and `GET /api/meetings/{id}/offline_ingest_progress` SHALL return `state = "failed"` with `error_code = "offline_ingest.busy"`

#### Scenario: Runtime unavailable triggers bounded retry then job-level failure

- **GIVEN** the standalone ASR runtime is unreachable for chunk N
- **WHEN** the offline ingest ASR task hits the failure for chunk N
- **THEN** the task SHALL retry the chunk 3 times with exponential backoff (2s, 4s, 8s)
- **AND** if all retries fail, the task SHALL mark the ingest progress row `state = "failed"` with `error_code = "asr.runtime_unavailable"`
- **AND** the meeting `status` SHALL NOT be set to `completed`


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
### Requirement: GET /api/meetings/{id}/offline_ingest_progress reports pipeline state

The backend SHALL expose `GET /api/meetings/{id}/offline_ingest_progress` returning JSON `{state, chunks_processed?, chunks_total?, error_code?}` where `state` is one of `"uploading"`, `"transcoding"`, `"asr_running"`, `"completed"`, `"failed"`. The endpoint SHALL return `chunks_processed` and `chunks_total` only when `state = "asr_running"` or `state = "completed"`; `error_code` SHALL appear only when `state = "failed"`. Access SHALL be restricted to the meeting owner; non-owners SHALL receive HTTP 404 (no information leak about meeting existence).

#### Scenario: Progress while ASR is running

- **GIVEN** an offline ingest in `asr_running` state having processed 12 of 20 chunks
- **WHEN** the owner GETs `/api/meetings/{id}/offline_ingest_progress`
- **THEN** the response SHALL be HTTP 200 with body `{"state": "asr_running", "chunks_processed": 12, "chunks_total": 20}`

#### Scenario: Progress on failed ingest reports error_code

- **GIVEN** an offline ingest that failed during transcode
- **WHEN** the owner GETs the progress endpoint
- **THEN** the response SHALL be HTTP 200 with body containing `"state": "failed"` and `"error_code": "offline_ingest.transcode_failed"`

#### Scenario: Non-owner gets 404

- **GIVEN** a meeting `m_c` owned by user `u_owner`
- **WHEN** user `u_other` GETs `/api/meetings/m_c/offline_ingest_progress`
- **THEN** the response SHALL be HTTP 404 without revealing whether `m_c` exists


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: Meeting detail conditional banner offers upload entry

The frontend SHALL render `<OfflineIngestBanner>` near the top of `/meetings/{id}` when ALL of the following are true: `meeting.status === "scheduled"` AND `new Date() > new Date(meeting.scheduled_end_at)` AND `meeting.recordings.length === 0`. The banner SHALL show a localized heading, a localized helper line, and an "上傳音檔" / "Upload audio" button that opens `<OfflineIngestUploadDialog>`. All visible strings SHALL exist in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json` under the `offline_ingest.banner.*` key namespace (per project i18n mirror invariant).

#### Scenario: Banner appears for past-end meetings with no recordings

- **GIVEN** the user opens `/meetings/m_d` whose `status = "scheduled"`, `scheduled_end_at = "2026-05-14T10:00:00Z"` (already past), and zero recordings
- **WHEN** the route renders
- **THEN** an `OfflineIngestBanner` element SHALL be present in the DOM with localized heading text resolved via `t("offline_ingest.banner.heading")`

#### Scenario: Banner is hidden for meetings still in the future

- **GIVEN** a meeting with `status = "scheduled"` and `scheduled_end_at` 30 minutes in the future
- **WHEN** the route renders
- **THEN** no `OfflineIngestBanner` SHALL appear

#### Scenario: Banner is hidden once a recording exists

- **GIVEN** a meeting with `status = "scheduled"`, past `scheduled_end_at`, and one `recording` row (perhaps from a prior offline ingest)
- **WHEN** the route renders
- **THEN** no `OfflineIngestBanner` SHALL appear


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: Upload dialog drives the tus session and progress polling

The frontend SHALL render `<OfflineIngestUploadDialog>` when the banner button is clicked. The dialog SHALL contain a file picker (accept `.wav,.mp3,.m4a,.aac,.flac,.ogg`), a `<DateTimePicker>` for "actual started at" defaulting to `meeting.scheduled_start_at`, and a "Start upload" button. On submit the dialog SHALL use `tus-js-client` to POST to `/api/meetings/{id}/recordings/offline_upload`, then PATCH chunks until completion, displaying a determinate progress bar driven by the tus `onProgress` callback. After the upload reaches 100%, the dialog SHALL poll `GET /api/meetings/{id}/offline_ingest_progress` every 3 seconds and surface `state` transitions (`transcoding`, `asr_running`, `completed`, `failed`) with localized status text. On `completed`, the dialog SHALL close, invalidate the meeting query, and show a localized success toast.

#### Scenario: Successful flow ends with closed dialog and meeting query invalidated

- **GIVEN** a banner-eligible meeting and a 30-second MP3 file selected
- **WHEN** the user clicks "Start upload"
- **THEN** the dialog SHALL show progressing percentage during upload, transition to a "Transcoding..." then "ASR (12 / 20 chunks)" state via polling, close on `state = "completed"`, AND the parent meeting query SHALL refetch (verifiable: `transcript_chunk` collection becomes non-empty)

#### Scenario: Upload failure surfaces localized error message

- **GIVEN** the backend rejects the upload with `error_code = "offline_ingest.unsupported_format"`
- **WHEN** the dialog receives the response
- **THEN** the dialog SHALL render the localized message resolved via `localizedErrorMessage("offline_ingest.unsupported_format", t)` AND the "Start upload" button SHALL re-enable so the user can pick a different file


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->

---
### Requirement: Configuration via OFFLINE_UPLOAD_DIR and limit env vars

The backend SHALL read `OFFLINE_UPLOAD_DIR` (default `~/MeetingPlaybook/offline_uploads`), `OFFLINE_UPLOAD_MAX_BYTES` (default `524288000` = 500 MiB), and `OFFLINE_UPLOAD_MAX_DURATION_SECONDS` (default `10800` = 3 hours) from the project Settings (loaded from `.env`). All three SHALL appear in `.env.example` with the documented defaults and short usage comments. The directory SHALL be created on demand if missing; the backend SHALL NOT fail to start when the directory does not yet exist.

#### Scenario: Missing OFFLINE_UPLOAD_DIR is created on first upload

- **GIVEN** `OFFLINE_UPLOAD_DIR` points at a path that does not exist
- **WHEN** the first `POST /api/meetings/{id}/recordings/offline_upload` arrives
- **THEN** the backend SHALL create the directory tree before writing the staging file AND respond 201 normally

<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
-->