## ADDED Requirements

### Requirement: POST /api/recordings/batch-download MUST reject retention-expired and soft-deleted rows with HTTP 410

The batch-download endpoint introduced by the `recording-index` capability SHALL enforce the same retention boundary as the per-recording audio endpoint. If any id in the request body refers to a row whose `deleted_at IS NOT NULL` OR whose `captured_at` is outside the active Recording window, the endpoint SHALL return `410 Gone` with `error_code: "recording.retention_expired"` and SHALL NOT stream a partial zip. The check runs at request time, not at the time the user loaded the list page.

#### Scenario: any expired id triggers 410 for the whole batch

- **GIVEN** 5 ids are submitted, 4 of which are inside the Recording window and 1 of which is retention-expired
- **WHEN** the batch-download endpoint validates retention
- **THEN** the response is 410 with `error_code: "recording.retention_expired"`
- **AND** the body indicates the count of expired rows
- **AND** no bytes of any WAV are streamed

#### Scenario: any soft-deleted id triggers 410

- **GIVEN** a request contains an id whose row has `deleted_at IS NOT NULL`
- **WHEN** the endpoint validates retention
- **THEN** the response is 410 with `error_code: "recording.retention_expired"`

### Requirement: GET /api/recordings MUST exclude soft-deleted and retention-expired rows

The recording-index list endpoint SHALL apply the same retention filter as the existing per-recording audio endpoint: rows with `deleted_at IS NOT NULL` OR `captured_at < NOW() - INTERVAL '{RECORDING_RETENTION_DAYS} days'` SHALL NOT appear in the response, regardless of user-supplied `since` / `until` query parameters.

#### Scenario: soft-deleted row excluded

- **GIVEN** the user owns 4 recordings, 1 of which has `deleted_at` set
- **WHEN** `GET /api/recordings` runs
- **THEN** the response contains exactly 3 rows
- **AND** the soft-deleted row is not present

#### Scenario: user-supplied since cannot widen the retention window

- **GIVEN** a row has `captured_at` 45 days ago and the retention window is 30 days
- **WHEN** the user calls `GET /api/recordings?since=2026-01-01` (which would include the old row)
- **THEN** the row is still excluded because it falls outside the active Recording window
