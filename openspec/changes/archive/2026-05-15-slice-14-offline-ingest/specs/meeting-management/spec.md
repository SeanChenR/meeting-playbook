## MODIFIED Requirements

### Requirement: GET /api/meetings/{id} returns recordings_available and rerun_asr_pending derived fields

The GET single-meeting response payload SHALL gain two derived boolean fields, computed server-side and never persisted to the meeting row:

- **`recordings_available: bool`** — `true` when at least one row in `recording` for this `meeting_id` has `deleted_at IS NULL`; `false` otherwise (including when no recording rows exist at all, e.g. for `scheduled` meetings that never ran). The `source` value (`live` or `offline`) SHALL NOT affect this computation — offline-ingested recordings are counted identically to live-captured ones for the purpose of `recordings_available`.
- **`rerun_asr_pending: bool`** — `true` when the in-flight re-run registry (`packages/backend/meeting_playbook/asr/rerun_runtime.py`) reports `is_pending(meeting_id)`; `false` otherwise.

Both fields SHALL be present on every GET response (no conditional omission); the OpenAPI / Pydantic response model SHALL declare them as required boolean fields.

#### Scenario: Completed meeting with non-deleted recordings reports recordings_available true

- **GIVEN** a `completed` meeting with 2 recording rows (one for me-stream, one for counterparty), both with `deleted_at IS NULL`
- **WHEN** GET `/api/meetings/{id}` is called
- **THEN** the response body SHALL contain `"recordings_available": true` AND `"rerun_asr_pending": false`

#### Scenario: Meeting with all recordings cleaned up reports recordings_available false

- **GIVEN** a `completed` meeting with 2 recording rows, both with `deleted_at = some past timestamp`
- **WHEN** GET `/api/meetings/{id}` is called
- **THEN** the response body SHALL contain `"recordings_available": false`

#### Scenario: Scheduled meeting with no recording rows yet reports recordings_available false

- **GIVEN** a `scheduled` meeting that has never started (zero rows in `recording`)
- **WHEN** GET `/api/meetings/{id}` is called
- **THEN** `"recordings_available"` SHALL be `false` AND `"rerun_asr_pending"` SHALL be `false`

#### Scenario: Active re-run flips rerun_asr_pending true; clears after completion

- **GIVEN** a completed meeting whose re-run task was just spawned (registry contains the meeting ID)
- **WHEN** GET `/api/meetings/{id}` is called while the task is still running
- **THEN** the response body SHALL contain `"rerun_asr_pending": true`
- **AND WHEN** the task completes and pops the registry entry; a subsequent GET fires
- **THEN** the response body SHALL contain `"rerun_asr_pending": false`

#### Scenario: Offline-ingested recording counts toward recordings_available

- **GIVEN** a `completed` meeting whose only recording row has `source = "offline"`, `stream = "me"`, and `deleted_at IS NULL`
- **WHEN** GET `/api/meetings/{id}` is called
- **THEN** the response body SHALL contain `"recordings_available": true` AND `"rerun_asr_pending": false`
