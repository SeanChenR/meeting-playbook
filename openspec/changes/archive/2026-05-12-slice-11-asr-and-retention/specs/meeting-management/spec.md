## ADDED Requirements

### Requirement: New meetings default to qwen3 ASR provider; existing rows are not back-filled

The `Meeting.asr_provider` SQLAlchemy column SHALL change its server-side default and ORM default from `"whisper"` to `"qwen3"`. Alembic migration `0008_meeting_asr_provider_default_qwen3` SHALL update the `DEFAULT` clause on the column ONLY; it SHALL NOT issue an `UPDATE` against any existing rows. Pre-existing meeting rows continue to carry whatever value was inserted at create time (typically `"whisper"` for slice-7..10 historical rows).

The POST `/api/meetings` endpoint SHALL respect the new default: when the request body omits `asr_provider`, the new row SHALL be persisted with `asr_provider = "qwen3"`.

#### Scenario: Migration changes default but does not back-fill historical rows

- **GIVEN** the database at slice-10 head with 4 existing meeting rows whose `asr_provider = "whisper"`
- **WHEN** Alembic upgrades to `0008_meeting_asr_provider_default_qwen3`
- **THEN** the column DEFAULT in `pg_attribute` / `information_schema.columns` SHALL be `'qwen3'`; all 4 existing rows SHALL still report `asr_provider = "whisper"`

#### Scenario: New meeting created without asr_provider in body uses qwen3

- **GIVEN** a backend at the new migration head
- **WHEN** the client POSTs `/api/meetings` with `{title, counterparty_display_name, me_display_name}` (no `asr_provider`)
- **THEN** the persisted row SHALL have `asr_provider = "qwen3"`; the response body SHALL include `"asr_provider": "qwen3"`

### Requirement: GET /api/meetings/{id} returns recordings_available and rerun_asr_pending derived fields

The GET single-meeting response payload SHALL gain two derived boolean fields, computed server-side and never persisted to the meeting row:

- **`recordings_available: bool`** — `true` when at least one row in `recording` for this `meeting_id` has `deleted_at IS NULL`; `false` otherwise (including when no recording rows exist at all, e.g. for `scheduled` meetings that never ran).
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
