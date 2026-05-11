# recording-retention Specification

## Purpose

TBD - created by archiving change 'slice-11-asr-and-retention'. Update Purpose after archive.

## Requirements

### Requirement: recording.deleted_at column tracks soft-deletion timestamp

The Alembic migration `0007_add_recording_deleted_at` SHALL add a single column `deleted_at TIMESTAMPTZ NULL` to the existing `recording` table. The migration SHALL NOT back-fill any rows; existing rows start with `deleted_at IS NULL` ("recording still available"). The column has no index — the cleanup query is a daily background sweep, not a hot path.

The cleanup logic SHALL set `deleted_at = now()` on each row whose corresponding WAV file is deleted; the row itself is NEVER deleted (preserves the historical fact that audio was captured for the meeting + stream).

#### Scenario: Migration adds deleted_at column with NULL default

- **GIVEN** a database at revision `0006_create_summary` (slice-10 head)
- **WHEN** `alembic upgrade head` runs
- **THEN** the `recording` table SHALL have a new `deleted_at` column with type `timestamp with time zone` and `is_nullable = YES`; no existing rows SHALL have a non-NULL value

#### Scenario: Existing recording rows survive the migration with deleted_at NULL

- **GIVEN** 5 existing recording rows from slice-7 dual-stream sessions
- **WHEN** the migration runs
- **THEN** all 5 rows SHALL still exist; all 5 SHALL have `deleted_at IS NULL`


<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->

---
### Requirement: RecordingRetentionJob.cleanup deletes WAV files older than threshold

The backend SHALL provide `packages/backend/meeting_playbook/retention/job.py` exporting an async function `cleanup(now: datetime, *, retention_days: int, recordings_dir: Path) -> int` that returns the count of WAV files actually deleted. The function SHALL:

1. Open a fresh `AsyncSession` via the application-wide session factory.
2. Select all `recording` rows where `created_at < (now - timedelta(days=retention_days)) AND deleted_at IS NULL`.
3. For each matched row: attempt `Path(rec.file_path).unlink()` (skip if file already missing); on success, set `rec.deleted_at = now`. On `OSError` (permission / FS issues), log a warning, skip this row, do NOT set `deleted_at` (next sweep retries).
4. Commit all `deleted_at` updates in a single transaction.
5. Return the count of files actually unlinked or already-missing-but-now-marked.

The function SHALL be idempotent: running it twice in succession with the same `now` SHALL produce zero deletions on the second call (because all matched rows already have `deleted_at IS NOT NULL`).

#### Scenario: Cleanup deletes files older than threshold and marks rows

- **GIVEN** 3 recording rows: one with `created_at = now - 31 days` (file exists), one with `created_at = now - 5 days` (file exists), one with `created_at = now - 60 days` (file already deleted from disk by hand)
- **WHEN** `cleanup(now=now, retention_days=30, recordings_dir=...)` runs
- **THEN** the 31-day-old WAV file SHALL be deleted from disk; the 5-day-old WAV SHALL remain on disk; the 60-day-old row SHALL get `deleted_at = now` (file was already gone — self-heal); all 3 rows SHALL still exist in the DB; the 5-day-old row's `deleted_at` SHALL still be NULL

#### Scenario: Idempotent — second cleanup with same now is a no-op

- **GIVEN** a database state from the previous scenario (after first cleanup)
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs again immediately
- **THEN** zero additional file unlinks happen; the 5-day-old row's `deleted_at` is still NULL; no exceptions raised

#### Scenario: Transcripts and chat_messages are never touched

- **GIVEN** a meeting whose recording was just cleaned up
- **WHEN** the cleanup transaction commits
- **THEN** the meeting's `transcript_chunk` and `chat_message` rows SHALL be untouched (same row count + content as before)


<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->

---
### Requirement: Retention job runs every 24 hours via FastAPI lifespan

The backend SHALL provide `packages/backend/meeting_playbook/retention/runtime.py` exporting `run_forever(*, settings: Settings) -> None` that runs an infinite `asyncio` loop: at the top of each iteration call `cleanup(now=datetime.now(UTC), retention_days=settings.recording_retention_days, recordings_dir=Path(settings.recordings_dir).expanduser())`, then `await asyncio.sleep(24 * 3600)`. Exceptions inside the iteration SHALL be caught (except `asyncio.CancelledError` which re-raises) and logged via `logger.exception`; the loop SHALL continue.

The FastAPI app SHALL register a `lifespan` async context manager that spawns `run_forever` as a background `asyncio.Task` on startup and cancels it on shutdown (with `asyncio.CancelledError` suppressed during the await of the cancelled task).

#### Scenario: First cleanup runs immediately on backend startup

- **GIVEN** a backend that just booted with `RECORDING_RETENTION_DAYS = 30`
- **WHEN** the lifespan startup hook fires
- **THEN** within 1 second `cleanup` SHALL have been invoked exactly once

#### Scenario: Subsequent cleanups run on a 24-hour cadence

- **GIVEN** a running backend with retention loop active
- **WHEN** 24 hours pass
- **THEN** a second `cleanup` invocation SHALL fire (the loop awakens from `asyncio.sleep`)

#### Scenario: Cleanup exception does NOT kill the loop

- **GIVEN** a stub `cleanup` that raises `RuntimeError("disk full")` on first call but succeeds on second
- **WHEN** the loop runs through two iterations
- **THEN** the first iteration SHALL log the exception traceback; the second iteration SHALL execute and succeed; the loop SHALL still be alive

#### Scenario: Lifespan shutdown cancels the loop cleanly

- **GIVEN** a running backend with retention loop active
- **WHEN** the FastAPI app shuts down
- **THEN** the lifespan finalizer SHALL cancel the task and await it; the await SHALL complete without raising (CancelledError suppressed); shutdown SHALL not hang


<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->

---
### Requirement: RECORDING_RETENTION_DAYS configuration with 30-day default

The `Settings` class in `packages/backend/meeting_playbook/config.py` SHALL gain a new field `recording_retention_days: int = 30` (read from env var `RECORDING_RETENTION_DAYS` per pydantic-settings convention). Setting the value to `0` SHALL be valid and behave as "delete everything older than this exact moment" (test path; useful for manually flushing during dev).

The `.env.example` file SHALL document the option (commented-out line + brief explanation referencing ADR-0020).

#### Scenario: Default retention is 30 days

- **GIVEN** no `RECORDING_RETENTION_DAYS` env var set
- **WHEN** `Settings()` is instantiated
- **THEN** `settings.recording_retention_days` SHALL equal `30`

#### Scenario: Override via env var takes effect

- **GIVEN** env var `RECORDING_RETENTION_DAYS = 7`
- **WHEN** `Settings()` is instantiated
- **THEN** `settings.recording_retention_days` SHALL equal `7`

#### Scenario: Zero days flushes everything matched on the next sweep

- **GIVEN** `recording_retention_days = 0` and a recording row with `created_at = now - 1 second`
- **WHEN** `cleanup(now=now, retention_days=0, ...)` runs
- **THEN** the row's WAV file SHALL be deleted and `deleted_at = now` set

<!-- @trace
source: slice-11-asr-and-retention
updated: 2026-05-12
code:
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/alembic/versions/0007_add_recording_deleted_at.py
  - packages/backend/meeting_playbook/sessions/models.py
  - .env.example
  - packages/backend/meeting_playbook/sessions/dependencies.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/alembic/versions/0008_asr_default_qwen3.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/components/recording-badge.tsx
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - packages/backend/meeting_playbook/rerun/runtime.py
  - packages/backend/uv.lock
  - packages/backend/meeting_playbook/rerun/__init__.py
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/asr/factory.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/locales/zh-TW.json
  - docs/adr/0028-qwen3-asr-replaces-vibevoice.md
  - packages/backend/pyproject.toml
  - packages/web/src/components/rerun-button.tsx
  - packages/backend/meeting_playbook/asr/transliteration.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/rerun-api.ts
  - scripts/spike_qwen3_asr.py
  - packages/backend/meeting_playbook/retention/__init__.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/retention/job.py
tests:
  - packages/web/src/components/transcript-pane.test.tsx
  - packages/backend/tests/rerun/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/web/src/components/rerun-button.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/asr/test_transliteration.py
  - packages/backend/tests/retention/__init__.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/retention/test_runtime.py
  - packages/backend/tests/asr/test_factory.py
  - packages/backend/tests/sessions/test_router_advice.py
  - packages/web/src/components/transcript-pane-rerun.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/test_alembic_meeting.py
  - packages/backend/tests/test_alembic_meeting_asr_default_qwen3.py
  - packages/backend/tests/test_alembic_recording_deleted_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/recording-badge.test.tsx
-->