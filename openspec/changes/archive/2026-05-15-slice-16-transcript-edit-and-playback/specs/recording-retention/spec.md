## ADDED Requirements

### Requirement: GET /api/meetings/{id}/recordings/{recording_id}/audio returns 410 Gone when the recording is retention-expired

The audio playback endpoint defined in the `audio-playback` capability SHALL consult `recording.deleted_at` on every request and SHALL respond with HTTP 410 Gone and `error_code = "audio_playback.expired"` whenever `recording.deleted_at IS NOT NULL`. The response body SHALL be a JSON object `{"error_code": "audio_playback.expired", "message": "<localized message>"}`. The endpoint MUST NOT stream any bytes of the on-disk WAV file when the recording is expired; even if the file still exists on disk (e.g. partial retention failure) the 410 response SHALL be authoritative. The retention sweep job's own behavior is unchanged: `cleanup` SHALL continue to set `deleted_at = now()` on rows whose WAV files are deleted, and the daily 24-hour cadence SHALL remain.

#### Scenario: Expired recording returns 410 even when the WAV file still exists on disk

- **GIVEN** a `recording` row with `deleted_at = "2026-04-01T00:00:00Z"` whose `file_path` still references a WAV file present on disk (retention's `unlink` previously failed)
- **WHEN** an authenticated owner sends `GET /api/meetings/{id}/recordings/{recording_id}/audio` with header `Range: bytes=0-1023`
- **THEN** the response SHALL be HTTP 410 with body containing `"error_code": "audio_playback.expired"`; no bytes from the WAV file SHALL be streamed to the client

#### Scenario: Non-expired recording is served normally

- **GIVEN** a `recording` row with `deleted_at IS NULL`
- **WHEN** an authenticated owner sends `GET /api/meetings/{id}/recordings/{recording_id}/audio` with header `Range: bytes=0-1023`
- **THEN** the response SHALL be HTTP 206 Partial Content (per the `audio-playback` capability)

### Requirement: Retention expiration surfaces in the frontend via disabled play affordances

The frontend SHALL, on every meeting detail page load, read each `recording.deleted_at` from the meeting payload. For every transcript chunk row whose mapped recording (per the `audio-playback` capability's `useChunkAudioSource` rule) has `deleted_at IS NOT NULL`, the row's ▶ play button SHALL be rendered with the `disabled` attribute and SHALL display a localized tooltip explaining the expiration. The tooltip text SHALL be: (zh-TW) `"錄音已過 30 天保留期"`; (en) `"Recording exceeded the 30-day retention window"`. The tooltip strings SHALL exist in both `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json` under the key `meeting.detail.audioPlayer.chunkExpired`. The mini-player SHALL NOT accept a play action targeting an expired chunk; if a race condition causes the mini-player to receive an expired-recording URL, the resulting HTTP 410 response from the backend SHALL be caught and SHALL flip the affected chunk row to the disabled state.

#### Scenario: Frontend renders disabled play button when the chunk's recording is expired

- **GIVEN** a meeting whose payload contains a `recording` with `deleted_at = "2026-04-01T00:00:00Z"` and a chunk row mapped to that recording, with the UI in zh-TW
- **WHEN** the user hovers over the chunk row
- **THEN** the ▶ button SHALL have the `disabled` attribute and the tooltip text SHALL be `"錄音已過 30 天保留期"`

#### Scenario: Backend 410 response during a race causes the row to become disabled

- **GIVEN** a meeting page rendered while `recording.deleted_at` was still `NULL`, but the retention job has just expired the recording between page-load and play-click
- **WHEN** the user clicks ▶ and the mini-player issues `GET /api/meetings/{id}/recordings/{recording_id}/audio`, receiving HTTP 410 `audio_playback.expired`
- **THEN** the mini-player SHALL surface a localized error toast (zh-TW: `"錄音已過 30 天保留期，無法播放"`; en: `"Recording has expired and cannot be played"`); the affected chunk row SHALL be re-rendered with its ▶ button in the disabled state with the standard expired tooltip
