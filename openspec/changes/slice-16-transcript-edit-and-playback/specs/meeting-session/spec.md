## MODIFIED Requirements

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

## ADDED Requirements

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
