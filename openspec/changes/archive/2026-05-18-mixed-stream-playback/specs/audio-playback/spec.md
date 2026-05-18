## ADDED Requirements

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

## MODIFIED Requirements

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
