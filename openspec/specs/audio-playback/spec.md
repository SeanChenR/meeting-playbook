# audio-playback Specification

## Purpose

TBD - created by archiving change 'slice-16-transcript-edit-and-playback'. Update Purpose after archive.

## Requirements

### Requirement: parse_wav_header reads the WAV header and surfaces format metadata

The backend SHALL provide `parse_wav_header(header_bytes: bytes) -> WavHeaderInfo` at `packages/backend/meeting_playbook/audio_playback/wav_header.py`. The function SHALL be pure (no IO) and accept the first N bytes of a WAV file (caller supplies at least 4096 bytes). It SHALL scan RIFF chunks to find the `fmt ` and `data` chunks, returning `WavHeaderInfo` with fields `(data_offset: int, sample_rate: int, channels: int, bits_per_sample: int, data_bytes: int)`. When the file is not a 16kHz mono 16-bit PCM WAV the function SHALL raise `UnsupportedWavFormat` with a message naming the offending field. The function SHALL tolerate optional `LIST` and other auxiliary chunks appearing before the `data` chunk (so `data_offset` is NOT hard-coded to 44).

#### Scenario: Standard 44-byte header is parsed correctly

- **GIVEN** a 16kHz mono 16-bit PCM WAV file whose header is the canonical 44 bytes
- **WHEN** `parse_wav_header(first_4096_bytes)` runs
- **THEN** the result SHALL have `data_offset = 44`, `sample_rate = 16000`, `channels = 1`, `bits_per_sample = 16`, and `data_bytes` equal to the WAV `data` chunk size

#### Scenario: Header with intermediate LIST chunk shifts data_offset past the LIST chunk

- **GIVEN** a 16kHz mono 16-bit PCM WAV file containing a `LIST` chunk of 36 bytes after the `fmt ` chunk and before the `data` chunk
- **WHEN** `parse_wav_header(first_4096_bytes)` runs
- **THEN** the result's `data_offset` SHALL equal the byte offset where the `data` chunk's payload begins (NOT 44); `sample_rate`, `channels`, `bits_per_sample` SHALL match the file

#### Scenario: Non-16kHz file is rejected

- **GIVEN** a 48kHz mono 16-bit PCM WAV
- **WHEN** `parse_wav_header(first_4096_bytes)` runs
- **THEN** the call SHALL raise `UnsupportedWavFormat` whose message mentions `sample_rate`

#### Scenario: Stereo file is rejected

- **GIVEN** a 16kHz stereo 16-bit PCM WAV
- **WHEN** `parse_wav_header(first_4096_bytes)` runs
- **THEN** the call SHALL raise `UnsupportedWavFormat` whose message mentions `channels`


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
### Requirement: compute_byte_range converts a second-aligned interval into a block-aligned byte range

The backend SHALL provide `compute_byte_range(*, header: WavHeaderInfo, start_second: float, end_second: float) -> tuple[int, int]` at `packages/backend/meeting_playbook/audio_playback/wav_header.py`. The function SHALL compute `bytes_per_second = sample_rate * channels * (bits_per_sample // 8)` and `block_align = channels * (bits_per_sample // 8)`. It SHALL return inclusive byte offsets `(start_byte, end_byte)` where:

- `start_byte = data_offset + ((round(start_second * bytes_per_second) // block_align) * block_align)`
- `end_byte = data_offset + (ceil(end_second * bytes_per_second) - 1)`, then rounded UP to the next `block_align - 1` boundary so the range covers full samples
- both clamped to `[data_offset, data_offset + data_bytes - 1]`

When `end_second < start_second` or either is negative the function SHALL raise `InvalidRange`. When the interval lies entirely outside the audio data the function SHALL raise `InvalidRange`.

#### Scenario: 10-second slice from second 5 to second 15 of a 16kHz mono 16-bit WAV

- **GIVEN** a WAV with `data_offset = 44`, `sample_rate = 16000`, `channels = 1`, `bits_per_sample = 16`, `data_bytes = 1_280_000` (40 seconds of audio)
- **WHEN** `compute_byte_range(header=above, start_second=5.0, end_second=15.0)` runs
- **THEN** the returned tuple SHALL equal `(44 + 5 * 32000, 44 + 15 * 32000 - 1) = (160_044, 480_043)`

##### Example: block-alignment boundary cases

| start_second | end_second | bytes_per_second | data_offset | data_bytes | Expected (start_byte, end_byte) |
| ------------ | ---------- | ---------------- | ----------- | ---------- | ------------------------------- |
| 0.0          | 1.0        | 32000            | 44          | 320000     | (44, 32043)                     |
| 0.5          | 1.5        | 32000            | 44          | 320000     | (16044, 48043)                  |
| 9.9          | 10.0       | 32000            | 44          | 320000     | (316844, 320043)                |

#### Scenario: end_second before start_second is rejected

- **GIVEN** a valid header
- **WHEN** `compute_byte_range(header=h, start_second=10.0, end_second=5.0)` runs
- **THEN** the call SHALL raise `InvalidRange`

#### Scenario: Interval beyond the audio data is rejected

- **GIVEN** a WAV with `data_bytes = 320000` (10 seconds)
- **WHEN** `compute_byte_range(header=h, start_second=20.0, end_second=25.0)` runs
- **THEN** the call SHALL raise `InvalidRange`


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
### Requirement: parse_range_header decodes an HTTP Range header into byte offsets

The backend SHALL provide `parse_range_header(value: str, total_length: int) -> tuple[int, int]` at `packages/backend/meeting_playbook/audio_playback/range_server.py`. The function SHALL accept the three forms in RFC 7233 section 2.1:

- `bytes=START-END` → `(START, END)`
- `bytes=START-` → `(START, total_length - 1)`
- `bytes=-N` (suffix-length) → `(total_length - N, total_length - 1)`

The function SHALL clamp `END` to `total_length - 1`. Any other syntax SHALL cause `MalformedRange` to be raised. A range where `START > END` after parsing or `START >= total_length` SHALL cause `MalformedRange`.

#### Scenario: bytes=100-200 parses to inclusive offsets

- **GIVEN** a header value `"bytes=100-200"` and `total_length = 1000`
- **WHEN** `parse_range_header` runs
- **THEN** the result SHALL be `(100, 200)`

#### Scenario: bytes=500- parses to (500, total_length-1)

- **GIVEN** a header value `"bytes=500-"` and `total_length = 1000`
- **WHEN** `parse_range_header` runs
- **THEN** the result SHALL be `(500, 999)`

#### Scenario: bytes=-200 parses to suffix from end

- **GIVEN** a header value `"bytes=-200"` and `total_length = 1000`
- **WHEN** `parse_range_header` runs
- **THEN** the result SHALL be `(800, 999)`

#### Scenario: Malformed range raises MalformedRange

- **GIVEN** a header value `"items=0-10"` and `total_length = 1000`
- **WHEN** `parse_range_header` runs
- **THEN** the call SHALL raise `MalformedRange`


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
### Requirement: GET /api/meetings/{id}/recordings/{recording_id}/audio serves Range-aware audio streaming

The backend SHALL expose `GET /api/meetings/{meeting_id}/recordings/{recording_id}/audio` at `packages/backend/meeting_playbook/audio_playback/router.py`. The endpoint SHALL load the `recording` row and verify that (a) `recording.meeting_id == meeting_id` else HTTP 404 with `error_code = "audio_playback.recording_not_found"`, (b) the meeting's owner equals the `X-User-Id` header else HTTP 403 with `error_code = "audio_playback.forbidden"`, (c) `recording.deleted_at IS NULL` else HTTP 410 with `error_code = "audio_playback.expired"`.

When the request carries an HTTP `Range` header the endpoint SHALL parse it via `parse_range_header`, cap the served byte count at `AUDIO_RANGE_MAX_BYTES` (default `2_097_152`), and respond with HTTP 206 Partial Content. The response SHALL include `Accept-Ranges: bytes`, `Content-Type: audio/wav`, `Content-Range: bytes <start>-<end>/<total>`, and `Content-Length: <end - start + 1>`. A malformed Range header SHALL cause HTTP 422 with `error_code = "audio_playback.malformed_range"`. A Range that lies outside the file SHALL cause HTTP 416 with `error_code = "audio_playback.range_not_satisfiable"`.

When the request has no `Range` header the endpoint SHALL respond with HTTP 200, `Content-Type: audio/wav`, `Accept-Ranges: bytes`, `Content-Length: <total file size>`, and the full file body.

#### Scenario: Range request returns 206 with correct bytes for a 10-second slice

- **GIVEN** an authenticated owner of meeting `m_a` with a non-expired recording `r_1` whose WAV is 40 seconds long (header 44 bytes + 1_280_000 data bytes)
- **WHEN** the owner sends `GET /api/meetings/m_a/recordings/r_1/audio` with header `Range: bytes=160044-480043`
- **THEN** the response SHALL be HTTP 206 with `Content-Range: bytes 160044-480043/1280044`, `Content-Length: 320000`, `Content-Type: audio/wav`, and the body bytes SHALL equal the file bytes from offset 160044 through 480043 inclusive

#### Scenario: Range request is rejected when the recording has been retention-expired

- **GIVEN** an authenticated owner of meeting `m_a` with recording `r_1` whose `deleted_at = 2026-04-01T00:00:00Z`
- **WHEN** the owner sends `GET /api/meetings/m_a/recordings/r_1/audio` with header `Range: bytes=0-1023`
- **THEN** the response SHALL be HTTP 410 with `error_code = "audio_playback.expired"`; no bytes from the WAV file SHALL be streamed

#### Scenario: Missing Range returns the full file with 200 OK

- **GIVEN** an authenticated owner of meeting `m_a` with non-expired recording `r_1` whose total file size is `1_280_044` bytes
- **WHEN** the owner sends `GET /api/meetings/m_a/recordings/r_1/audio` with NO Range header
- **THEN** the response SHALL be HTTP 200 with `Content-Length: 1280044`, `Accept-Ranges: bytes`, `Content-Type: audio/wav`, and the body SHALL equal the entire file

#### Scenario: Range request exceeding AUDIO_RANGE_MAX_BYTES is capped

- **GIVEN** an authenticated owner of meeting `m_a` with non-expired recording `r_1` whose file size is `10_000_000` bytes and `AUDIO_RANGE_MAX_BYTES = 2_097_152`
- **WHEN** the owner sends `GET /api/meetings/m_a/recordings/r_1/audio` with header `Range: bytes=0-9999999`
- **THEN** the response SHALL be HTTP 206 with `Content-Length: 2097152` and `Content-Range: bytes 0-2097151/10000000`

#### Scenario: Recording belonging to a different meeting returns 404

- **GIVEN** an authenticated owner of meeting `m_a` and meeting `m_b`, where recording `r_1` belongs to `m_b`
- **WHEN** the owner sends `GET /api/meetings/m_a/recordings/r_1/audio`
- **THEN** the response SHALL be HTTP 404 with `error_code = "audio_playback.recording_not_found"`

#### Scenario: Non-owner is rejected with 403

- **GIVEN** user `u_a` owns meeting `m_a` containing recording `r_1`, and user `u_b` is authenticated
- **WHEN** `u_b` sends `GET /api/meetings/m_a/recordings/r_1/audio`
- **THEN** the response SHALL be HTTP 403 with `error_code = "audio_playback.forbidden"`

#### Scenario: Range outside file returns 416

- **GIVEN** an authenticated owner of meeting `m_a` with non-expired recording `r_1` whose file size is `1_000_000` bytes
- **WHEN** the owner sends `GET /api/meetings/m_a/recordings/r_1/audio` with header `Range: bytes=2000000-3000000`
- **THEN** the response SHALL be HTTP 416 with `error_code = "audio_playback.range_not_satisfiable"`


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
### Requirement: MeetingAudioMiniPlayer is a sticky bottom control bar with whole-recording playback

The frontend SHALL provide `<MeetingAudioMiniPlayer>` at `packages/web/src/components/meeting-audio-mini-player.tsx`. The component SHALL render as a sticky bottom bar (CSS `position: sticky; bottom: 0`) inside the meeting detail page.

The mini-player SHALL load **the entire recording WAV file** via a single `<audio>` element. The recording is resolved by `pickMeetingRecording(recordings)` which returns:

- For **dual-channel meetings** (both `stream === "me"` AND `stream === "counterparty"` rows present): a result whose `kind === "dual"` and `defaultSource === "mixed"`. The mini-player SHALL mount `<audio>.src` pointing at `/api/meetings/{id}/recordings/mixed/audio?...` (per the new `Mixed audio endpoint` requirement) and SHALL render the source toggle (per `MeetingAudioMiniPlayer source toggle` requirement) so the user can switch to `me` / `counterparty` if desired.
- For **single-channel meetings** (exactly one recording row): a result whose `kind === "single"` and whose `sources.me` URL points at the single recording's per-recording endpoint. The mini-player SHALL mount `<audio>.src` to that URL and SHALL NOT render any source toggle.
- When no recording is available, the mini-player SHALL render in an idle state (all transport controls disabled) without mounting an `<audio>` element.

It SHALL render the following controls: Previous chunk button (seeks to the previous chunk's `started_at`), Play / Pause toggle button, Next chunk button (seeks to the next chunk's `started_at`), Seek bar (HTML5 `<input type="range">` or equivalent), and Speed dropdown. The Speed dropdown SHALL expose exactly six options: `0.5x`, `0.75x`, `1.0x`, `1.25x`, `1.5x`, `2.0x`. The user's last selected speed SHALL persist in `localStorage` under the key `miniPlayerRate` and default to `1.0` when the key is absent.

Chunk-level "play this chunk" actions (originating from `<ChunkActionMenu>`) SHALL invoke `miniPlayerStore.seekToChunk(chunkId)` which computes `audio.currentTime = (chunk.started_at - recording.started_at) / 1000` and calls `audio.play()`. This SHALL NOT change the `<audio>` element's `src` to a different source kind (mixed → mixed, me → me, etc.).

The component SHALL hold a single `<audio>` element whose `src` is the URL for the currently active source + chunk slice. Switching to a different chunk SHALL set the `src` to the new URL and call `play()`; it SHALL NOT unmount the `<audio>` element. The `playbackRate` property SHALL be applied to the `<audio>` element on every speed change without reloading the source. Switching the source toggle SHALL reload `src` (per `MeetingAudioMiniPlayer source toggle` requirement), preserving `currentTime`, `paused`, and `playbackRate`.

The Previous and Next buttons SHALL select the chunk with index `current - 1` and `current + 1` respectively in the chunks-sorted-by-`started_at` array. When the current chunk is the first in the array the Previous button SHALL be disabled; when it is the last the Next button SHALL be disabled.

When the mixed endpoint returns an error (`recording.mixed_not_applicable` or `recording.mix_failed`), the mini-player SHALL render the localized error via `localizedErrorMessage` and SHALL NOT automatically fall back to `me` / `counterparty` sources — the user must manually switch via the source toggle. This ensures the user is aware that the mixed audio is unavailable rather than silently hearing only one side.

#### Scenario: Clicking the play button on a chunk starts playback at the correct slice

- **GIVEN** a meeting detail page with three chunks `c_1`, `c_2`, `c_3` and the mini-player idle, source `mixed`
- **WHEN** the user clicks the ▶ button on chunk `c_2` (a row-level button defined under the `meeting-detail-layout` capability)
- **THEN** the mini-player's `<audio>` element SHALL be assigned `src = "/api/meetings/{id}/recordings/mixed/audio?start={c_2.started_at}&end={c_2.ended_at}"` and SHALL start playing; the Play/Pause button SHALL show the Pause icon

#### Scenario: Changing speed updates playbackRate without reloading audio

- **GIVEN** the mini-player is mid-playback at `playbackRate = 1.0`
- **WHEN** the user selects `1.5x` from the Speed dropdown
- **THEN** the `<audio>` element's `playbackRate` property SHALL equal `1.5`; the current `src` SHALL be unchanged; playback SHALL continue from the same `currentTime`; `localStorage.miniPlayerRate` SHALL equal `"1.5"`

#### Scenario: Next button advances to the next chunk in started_at order

- **GIVEN** the mini-player is playing chunk `c_2` of `[c_1, c_2, c_3]` ordered by `started_at`, source `mixed`
- **WHEN** the user clicks Next
- **THEN** the `<audio>` element's `src` SHALL update to the mixed slice URL for `c_3`; playback SHALL begin from `currentTime = 0`

#### Scenario: Previous is disabled on the first chunk and Next is disabled on the last

- **GIVEN** the mini-player is playing chunk `c_1` of `[c_1, c_2, c_3]`
- **WHEN** the page renders
- **THEN** the Previous button SHALL have the `disabled` attribute; the Next button SHALL NOT be disabled
- **WHEN** the user clicks Next twice to reach `c_3`
- **THEN** the Next button SHALL have the `disabled` attribute; the Previous button SHALL NOT be disabled

#### Scenario: Speed preference persists across reloads

- **GIVEN** a fresh browser with no `miniPlayerRate` key in `localStorage`
- **WHEN** the user selects `0.75x` then reloads the page
- **THEN** the mini-player SHALL mount with `playbackRate = 0.75` and the Speed dropdown SHALL show `0.75x` selected

#### Scenario: Mixed endpoint error surfaces inline without auto-fallback

- **GIVEN** a dual-channel meeting whose mixed endpoint returns `HTTP 500 {error_code: "recording.mix_failed"}`
- **WHEN** the mini-player attempts to load mixed audio on mount
- **THEN** an `<Alert variant="destructive">` SHALL render with the localized message for `recording.mix_failed`
- **AND** the source toggle SHALL still render with `mixed` highlighted (NOT auto-switched to `me`)
- **AND** the user SHALL be able to manually click `source-me` to play just the me-stream


<!-- @trace
source: mixed-stream-playback
updated: 2026-05-18
code:
  - packages/backend/meeting_playbook/audio_playback/mixer.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/locales/en.json
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/hooks/use-mini-player.ts
tests:
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/audio_playback/test_mixer.py
  - packages/backend/tests/audio_playback/test_router_mixed.py
  - packages/web/src/hooks/use-mini-player.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
-->

---
### Requirement: useChunkAudioSource maps a transcript chunk to the correct recording

The frontend SHALL provide the hook `useChunkAudioSource(chunk, recordings) -> Recording` at `packages/web/src/hooks/use-mini-player.ts`. The hook SHALL apply the following rules:

- If `recordings.length === 1` the hook SHALL return that recording (single-channel mode).
- Else if `recordings.length === 2` and contains both `stream = "me"` and `stream = "counterparty"`: when `chunk.speaker === "me"` the hook SHALL return the recording with `stream = "me"`; when `chunk.speaker === "counterparty"` the hook SHALL return the recording with `stream = "counterparty"`; otherwise (e.g. `speaker_cluster_<N>` arriving in a dual-channel meeting, which is a defect path) the hook SHALL return the recording with `stream = "me"` as a defensive default.
- Else the hook SHALL throw `Error("invalid recording configuration")`.

#### Scenario: Single-channel meeting always returns the only recording

- **GIVEN** `recordings = [{id: "r_1", stream: "me", ...}]` and a chunk with `speaker = "speaker_cluster_2"`
- **WHEN** `useChunkAudioSource(chunk, recordings)` runs
- **THEN** the return value SHALL be the recording with `id = "r_1"`

#### Scenario: Dual-channel meeting picks the me recording for a me-speaker chunk

- **GIVEN** `recordings = [{id: "r_m", stream: "me"}, {id: "r_c", stream: "counterparty"}]` and a chunk with `speaker = "me"`
- **WHEN** `useChunkAudioSource(chunk, recordings)` runs
- **THEN** the return value SHALL be the recording with `id = "r_m"`

#### Scenario: Dual-channel meeting picks the counterparty recording for a counterparty-speaker chunk

- **GIVEN** `recordings = [{id: "r_m", stream: "me"}, {id: "r_c", stream: "counterparty"}]` and a chunk with `speaker = "counterparty"`
- **WHEN** `useChunkAudioSource(chunk, recordings)` runs
- **THEN** the return value SHALL be the recording with `id = "r_c"`


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
### Requirement: ChunkActionMenu disables the play action when the recording is retention-expired

The chunk-level play affordance lives inside `<ChunkActionMenu>` (see the `ChunkActionMenu surfaces per-chunk actions` requirement in the transcript-edit capability) rather than as a separate hover-revealed ▶ button on `<TranscriptChunkRow>`. The "Play this chunk" menu item SHALL be rendered for every chunk that has an associated recording; when the resolved recording (`pickMeetingRecording(recordings)`) has `deleted_at IS NOT NULL`, the menu item SHALL be disabled and accompanied by a tooltip / aria-label whose visible text is (zh-TW) `"錄音已過 30 天保留期"` or (en) `"Recording exceeded the 30-day retention window"`. A disabled play menu item SHALL NOT dispatch `miniPlayerStore.seekToChunk(...)`.

#### Scenario: Expired recording renders disabled play button with localized tooltip

- **GIVEN** a chunk row whose mapped recording has `deleted_at = "2026-04-01T00:00:00Z"` and the UI is in zh-TW
- **WHEN** the user hovers over the chunk row
- **THEN** the ▶ button SHALL be present and have the `disabled` attribute; the tooltip SHALL display `"錄音已過 30 天保留期"`

#### Scenario: Non-expired recording renders enabled play button and triggers mini-player

- **GIVEN** a chunk row whose mapped recording has `deleted_at IS NULL`
- **WHEN** the user clicks the ▶ button
- **THEN** the ▶ button SHALL NOT be disabled; the mini-player's active chunk SHALL be updated to this row's chunk; the mini-player's `<audio>` SHALL begin playing


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
### Requirement: AUDIO_RANGE_MAX_BYTES configuration with 2 MiB default

The `Settings` class in `packages/backend/meeting_playbook/config.py` SHALL gain a new field `audio_range_max_bytes: int = 2_097_152` read from env var `AUDIO_RANGE_MAX_BYTES` per pydantic-settings convention. The `.env.example` file SHALL document this option with a commented-out line and a short explanation of why it caps Range responses (browser buffer sizing, retry-friendly).

#### Scenario: Default cap is 2 MiB

- **GIVEN** no `AUDIO_RANGE_MAX_BYTES` env var set
- **WHEN** `Settings()` is instantiated
- **THEN** `settings.audio_range_max_bytes` SHALL equal `2_097_152`

#### Scenario: Override via env var takes effect

- **GIVEN** env var `AUDIO_RANGE_MAX_BYTES = "1048576"`
- **WHEN** `Settings()` is instantiated
- **THEN** `settings.audio_range_max_bytes` SHALL equal `1_048_576`

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
### Requirement: GET /api/meetings/{id}/recordings/mixed/audio serves the dual-stream mix as a Range-aware mono stream

The backend SHALL expose `GET /api/meetings/{meeting_id}/recordings/mixed/audio?start=&end=` for any dual-channel meeting (one whose `recording` rows include both `stream === "me"` AND `stream === "counterparty"`). The response SHALL be `audio/wav` mono PCM 16 kHz 16-bit and SHALL honor HTTP `Range` headers using the same `compute_byte_range` arithmetic and `AUDIO_RANGE_MAX_BYTES` cap as the existing per-recording endpoint.

The first request SHALL trigger lazy mix via `ensure_mixed_wav(meeting_id, recordings_dir)`. Subsequent requests SHALL read directly from the cached `{recordings_dir}/{meeting_id}/mixed.wav` file.

The endpoint SHALL respond:

- `HTTP 404` with `error_code = "recording.mixed_not_applicable"` when the meeting is single-channel (either `me.wav` or `counterparty.wav` is absent under `{recordings_dir}/{meeting_id}/`)
- `HTTP 500` with `error_code = "recording.mix_failed"` when mixing fails due to IO error, numpy error, or any wrapped `MixerError`
- `HTTP 404` when the meeting is not owned by the caller (existing ownership check)

Cross-meeting / cross-owner ownership SHALL follow the same scoping rules as the per-recording endpoint.

#### Scenario: First request triggers mix then serves Range-aware bytes

- **GIVEN** a dual-channel meeting `m_d` with `me.wav` (10 MiB, 16 kHz mono 16-bit) and `counterparty.wav` (10 MiB, 16 kHz mono 16-bit) on disk, no `mixed.wav` yet
- **WHEN** the user requests `GET /api/meetings/m_d/recordings/mixed/audio` with `Range: bytes=0-1048575`
- **THEN** the response SHALL be `HTTP 206 Partial Content` with `Content-Range: bytes 0-1048575/...`
- **AND** `{recordings_dir}/m_d/mixed.wav` SHALL exist on disk after the response
- **AND** the response body SHALL be the first 1 MiB of the mixed WAV

#### Scenario: Subsequent request reads from cached mix

- **GIVEN** a dual-channel meeting `m_d` whose `mixed.wav` has already been created
- **WHEN** the user makes a second `Range: bytes=1048576-2097151` request to the mixed endpoint
- **THEN** the response SHALL be served directly from the cached `mixed.wav` without re-running the mix
- **AND** the response SHALL be `HTTP 206 Partial Content` with the requested 1 MiB slice

#### Scenario: Single-channel meeting rejects mixed endpoint with 404

- **GIVEN** a single-channel meeting `m_s` with only `me.wav` on disk (no `counterparty.wav`)
- **WHEN** the user requests `GET /api/meetings/m_s/recordings/mixed/audio`
- **THEN** the response SHALL be `HTTP 404` with body `{"error_code": "recording.mixed_not_applicable", "message": ...}`
- **AND** no `mixed.wav` SHALL be written to disk

#### Scenario: Mix failure during ensure_mixed_wav surfaces as 500 mix_failed

- **GIVEN** a dual-channel meeting whose `counterparty.wav` is on disk but corrupt (unparseable WAV header)
- **WHEN** the user requests `GET /api/meetings/{id}/recordings/mixed/audio`
- **THEN** the response SHALL be `HTTP 500` with body `{"error_code": "recording.mix_failed", "message": ...}`
- **AND** any partial `mixed.wav.tmp` SHALL be removed (atomic rename precondition)


<!-- @trace
source: mixed-stream-playback
updated: 2026-05-18
code:
  - packages/backend/meeting_playbook/audio_playback/mixer.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/locales/en.json
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/hooks/use-mini-player.ts
tests:
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/audio_playback/test_mixer.py
  - packages/backend/tests/audio_playback/test_router_mixed.py
  - packages/web/src/hooks/use-mini-player.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
-->

---
### Requirement: mix_pcm_int16 averages two equal-length int16 PCM byte buffers without overflow

The mixer module `meeting_playbook/audio_playback/mixer.py` SHALL expose `mix_pcm_int16(left: bytes, right: bytes) -> bytes`.

Inputs SHALL be raw 16-bit signed little-endian PCM byte buffers of equal length. Output SHALL be the same-length byte buffer where each int16 sample is the arithmetic mean of the corresponding `left` and `right` samples computed in int32 intermediate then truncated to int16 (no overflow because `(int16_max + int16_max) // 2 == int16_max`).

When `len(left) != len(right)`, the function SHALL raise `ValueError`. Callers (`ensure_mixed_wav`) are responsible for zero-padding before calling.

#### Scenario: Two equal-length silent buffers produce silent output

- **GIVEN** `left = bytes(8000)` (4000 int16 zero samples) and `right = bytes(8000)` (4000 int16 zero samples)
- **WHEN** `mix_pcm_int16(left, right)` is called
- **THEN** the return value SHALL be `bytes(8000)` (4000 int16 zero samples)

#### Scenario: Mixing constant +1000 with constant -1000 produces zero

- **GIVEN** `left` containing 100 int16 samples each equal to `+1000` and `right` containing 100 int16 samples each equal to `-1000`
- **WHEN** `mix_pcm_int16(left, right)` is called
- **THEN** the return value SHALL contain 100 int16 samples each equal to `0`

#### Scenario: Mixing max amplitudes does not overflow

- **GIVEN** `left` and `right` each containing 100 int16 samples at `+32767` (int16 max)
- **WHEN** `mix_pcm_int16(left, right)` is called
- **THEN** the return value SHALL contain 100 int16 samples at `+32767` (no overflow / wraparound to negative)

#### Scenario: Mismatched length raises ValueError

- **GIVEN** `left = bytes(8000)` and `right = bytes(4000)`
- **WHEN** `mix_pcm_int16(left, right)` is called
- **THEN** a `ValueError` SHALL be raised


<!-- @trace
source: mixed-stream-playback
updated: 2026-05-18
code:
  - packages/backend/meeting_playbook/audio_playback/mixer.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/locales/en.json
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/hooks/use-mini-player.ts
tests:
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/audio_playback/test_mixer.py
  - packages/backend/tests/audio_playback/test_router_mixed.py
  - packages/web/src/hooks/use-mini-player.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
-->

---
### Requirement: ensure_mixed_wav is lazy, idempotent, and zero-pads the shorter stream

The mixer module SHALL expose `ensure_mixed_wav(meeting_id: str, recordings_dir: Path) -> Path` with the following contract:

1. If `{recordings_dir}/{meeting_id}/mixed.wav` already exists, return its path **without rewriting**.
2. If either `me.wav` or `counterparty.wav` is missing, raise `MixerInputMissing`.
3. Otherwise read both files' PCM data sections, compute `n = max(len(me_pcm), len(counterparty_pcm))`, zero-pad the shorter side to `n` bytes (using int16 silence `0x0000`), call `mix_pcm_int16(me_padded, counterparty_padded)`, and write the result to `{recordings_dir}/{meeting_id}/mixed.wav.tmp` then atomic-rename to `mixed.wav`.
4. Return the path to `mixed.wav`.

The output WAV SHALL be 16 kHz mono 16-bit (same as the inputs) so the existing `parse_wav_header` validation passes.

Concurrent first invocations on the same meeting are safe — last writer wins, all writers produce byte-identical output (deterministic mix).

#### Scenario: First call mixes and writes; second call returns cached path

- **GIVEN** `me.wav` and `counterparty.wav` exist for meeting `m_x`, no `mixed.wav`
- **WHEN** `ensure_mixed_wav("m_x", recordings_dir)` is called
- **THEN** `mixed.wav` SHALL exist on disk
- **AND** the file SHALL be a valid mono 16 kHz 16-bit WAV
- **AND** a second `ensure_mixed_wav("m_x", recordings_dir)` call SHALL return the same path without modifying the file's `st_mtime`

#### Scenario: Missing me.wav raises MixerInputMissing

- **GIVEN** only `counterparty.wav` exists for meeting `m_y` (no `me.wav`)
- **WHEN** `ensure_mixed_wav("m_y", recordings_dir)` is called
- **THEN** `MixerInputMissing` SHALL be raised
- **AND** no `mixed.wav` SHALL be written

#### Scenario: Shorter side is zero-padded so output length equals max

- **GIVEN** `me.wav` containing 1000 int16 samples at amplitude `+5000` and `counterparty.wav` containing 500 int16 samples at amplitude `+3000`
- **WHEN** `ensure_mixed_wav` is called
- **THEN** `mixed.wav` SHALL contain 1000 int16 samples
- **AND** the first 500 samples SHALL each be `(5000 + 3000) // 2 = 4000`
- **AND** the remaining 500 samples SHALL each be `(5000 + 0) // 2 = 2500`


<!-- @trace
source: mixed-stream-playback
updated: 2026-05-18
code:
  - packages/backend/meeting_playbook/audio_playback/mixer.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/locales/en.json
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/hooks/use-mini-player.ts
tests:
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/audio_playback/test_mixer.py
  - packages/backend/tests/audio_playback/test_router_mixed.py
  - packages/web/src/hooks/use-mini-player.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
-->

---
### Requirement: MeetingAudioMiniPlayer source toggle switches between mixed / me / counterparty while preserving currentTime

For dual-channel meetings the mini-player SHALL render a source toggle `<SourceToggle>` (segmented control) with exactly three options in this order: `混音 / 我方 / 對方` (zh-TW) and `Mixed / Me / Counterparty` (en). The toggle SHALL expose `data-testid="mini-player-source-toggle"` on the container and `data-testid="source-mixed"`, `source-me`, `source-counterparty` on each button.

The user's selection SHALL be persisted in `localStorage.miniPlayerSource` (values: `"mixed" | "me" | "counterparty"`, default `"mixed"`). The persisted value SHALL be read once on mount; absent or invalid values SHALL default to `"mixed"`.

When the toggle changes:

1. Capture the current `<audio>.currentTime` and `paused` state
2. Set `<audio>.src` to the new source URL (`/api/meetings/{id}/recordings/mixed/audio?start=&end=` for `mixed`, or the existing per-recording URL for `me` / `counterparty`) preserving the current chunk slice `start` / `end` params
3. On `<audio>.onLoadedMetadata`, restore `currentTime` to the captured value
4. If previously playing, call `<audio>.play()`
5. `playbackRate` SHALL be preserved across the switch (re-applied after src change)

For single-channel meetings the toggle SHALL NOT render at all (no DOM presence).

#### Scenario: Toggle to mixed preserves currentTime and playback state

- **GIVEN** a dual-channel meeting mini-player playing at `currentTime = 12.5`, `playbackRate = 1.5`, source `me`
- **WHEN** the user clicks `source-mixed`
- **THEN** the `<audio>` element's `src` SHALL match `/api/meetings/{id}/recordings/mixed/audio?...`
- **AND** after `onLoadedMetadata`, `<audio>.currentTime` SHALL equal `12.5` (within ±0.1s tolerance)
- **AND** `<audio>.playbackRate` SHALL equal `1.5`
- **AND** the audio SHALL continue playing (`paused === false`)
- **AND** `localStorage.miniPlayerSource` SHALL equal `"mixed"`

#### Scenario: Toggle persists across page reload

- **GIVEN** a user previously selected `source-counterparty` on a dual-channel meeting
- **WHEN** they reload the page (`localStorage.miniPlayerSource === "counterparty"` already set)
- **THEN** the mini-player SHALL mount with `<audio>.src` pointing at the `counterparty` recording's per-recording URL
- **AND** the `source-counterparty` button SHALL be marked active in the segmented control

#### Scenario: Single-channel meeting renders no source toggle

- **GIVEN** a single-channel meeting (only one recording row)
- **WHEN** the mini-player mounts
- **THEN** the DOM SHALL NOT contain any element with `data-testid="mini-player-source-toggle"`
- **AND** the existing single-recording playback behavior SHALL be unchanged

<!-- @trace
source: mixed-stream-playback
updated: 2026-05-18
code:
  - packages/backend/meeting_playbook/audio_playback/mixer.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/locales/en.json
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/hooks/use-mini-player.ts
tests:
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/audio_playback/test_mixer.py
  - packages/backend/tests/audio_playback/test_router_mixed.py
  - packages/web/src/hooks/use-mini-player.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
-->