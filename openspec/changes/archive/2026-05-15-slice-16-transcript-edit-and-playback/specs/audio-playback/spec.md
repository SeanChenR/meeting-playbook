## ADDED Requirements

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

### Requirement: MeetingAudioMiniPlayer is a sticky bottom control bar with whole-recording playback

The frontend SHALL provide `<MeetingAudioMiniPlayer>` at `packages/web/src/components/meeting-audio-mini-player.tsx`. The component SHALL render as a sticky bottom bar (CSS `position: sticky; bottom: 0`) inside the meeting detail page.

The mini-player SHALL load **the entire recording WAV file** via a single `<audio>` element whose `src` is set once on mount and SHALL NOT change while the user navigates between chunks. The recording is resolved by `pickMeetingRecording(recordings)`: dual-channel meetings → the recording with `stream === "me"`; single-channel meetings → the only recording row. When no recording is available, the mini-player SHALL render in an idle state (all transport controls disabled) without mounting an `<audio>` element.

It SHALL render the following controls: Previous chunk button (seeks to the previous chunk's `started_at`), Play / Pause toggle button, Next chunk button (seeks to the next chunk's `started_at`), Seek bar (HTML5 `<input type="range">` or equivalent), and Speed dropdown. The Speed dropdown SHALL expose exactly six options: `0.5x`, `0.75x`, `1.0x`, `1.25x`, `1.5x`, `2.0x`. The user's last selected speed SHALL persist in `localStorage` under the key `miniPlayerRate` and default to `1.0` when the key is absent.

Chunk-level "play this chunk" actions (originating from `<ChunkActionMenu>`) SHALL invoke `miniPlayerStore.seekToChunk(chunkId)` which computes `audio.currentTime = (chunk.started_at - recording.started_at) / 1000` and calls `audio.play()`. This SHALL NOT change the `<audio>` element's `src`.

The component SHALL hold a single `<audio>` element whose `src` is the URL `/api/meetings/{meetingId}/recordings/{recordingId}/audio?start={chunkStart}&end={chunkEnd}` for the currently active chunk. Switching to a different chunk SHALL set the `src` to the new URL and call `play()`; it SHALL NOT unmount the `<audio>` element. The `playbackRate` property SHALL be applied to the `<audio>` element on every speed change without reloading the source.

The Previous and Next buttons SHALL select the chunk with index `current - 1` and `current + 1` respectively in the chunks-sorted-by-`started_at` array. When the current chunk is the first in the array the Previous button SHALL be disabled; when it is the last the Next button SHALL be disabled.

#### Scenario: Clicking the play button on a chunk starts playback at the correct slice

- **GIVEN** a meeting detail page with three chunks `c_1`, `c_2`, `c_3` and the mini-player idle
- **WHEN** the user clicks the ▶ button on chunk `c_2` (a row-level button defined under the `meeting-detail-layout` capability)
- **THEN** the mini-player's `<audio>` element SHALL be assigned `src = "/api/meetings/{id}/recordings/{recId}/audio?start={c_2.started_at}&end={c_2.ended_at}"` and SHALL start playing; the Play/Pause button SHALL show the Pause icon

#### Scenario: Changing speed updates playbackRate without reloading audio

- **GIVEN** the mini-player is mid-playback at `playbackRate = 1.0`
- **WHEN** the user selects `1.5x` from the Speed dropdown
- **THEN** the `<audio>` element's `playbackRate` property SHALL equal `1.5`; the current `src` SHALL be unchanged; playback SHALL continue from the same `currentTime`; `localStorage.miniPlayerRate` SHALL equal `"1.5"`

#### Scenario: Next button advances to the next chunk in started_at order

- **GIVEN** the mini-player is playing chunk `c_2` of `[c_1, c_2, c_3]` ordered by `started_at`
- **WHEN** the user clicks Next
- **THEN** the `<audio>` element's `src` SHALL update to the slice URL for `c_3`; playback SHALL begin from `currentTime = 0`

#### Scenario: Previous is disabled on the first chunk and Next is disabled on the last

- **GIVEN** the mini-player is playing chunk `c_1` of `[c_1, c_2, c_3]`
- **WHEN** the page renders
- **THEN** the Previous button SHALL have the `disabled` attribute; the Next button SHALL NOT be disabled
- **WHEN** the user clicks Next twice to reach `c_3`
- **THEN** the Next button SHALL have the `disabled` attribute; the Previous button SHALL NOT be disabled

#### Scenario: Speed preference persists across reloads

- **GIVEN** a fresh browser with no `miniPlayerRate` key in `localStorage`
- **WHEN** the user changes Speed to `0.75x` then reloads the meeting detail page
- **THEN** on reload the mini-player Speed dropdown SHALL show `0.75x` as the active value; the `<audio>` element's `playbackRate` SHALL equal `0.75` once playback starts

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
