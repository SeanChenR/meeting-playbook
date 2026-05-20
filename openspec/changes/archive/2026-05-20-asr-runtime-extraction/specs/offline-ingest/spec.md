## MODIFIED Requirements

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
