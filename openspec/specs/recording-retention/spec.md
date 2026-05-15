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
2. Select all `recording` rows where `created_at < (now - timedelta(days=retention_days)) AND deleted_at IS NULL`. The selection SHALL NOT filter on `source`; both `source = 'live'` and `source = 'offline'` recordings SHALL be eligible for retention cleanup on the same 30-day clock.
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

#### Scenario: Offline-ingested recording is cleaned up on the same 30-day clock as live recordings

- **GIVEN** an offline-ingested recording row with `source = "offline"`, `created_at = now - 31 days`, `deleted_at IS NULL`, and the file present on disk
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs
- **THEN** the offline WAV file SHALL be deleted from disk AND the row's `deleted_at` SHALL equal `now`; the `source` value SHALL NOT affect cleanup eligibility


<!-- @trace
source: slice-14-offline-ingest
updated: 2026-05-15
code:
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/pyproject.toml
  - CONTEXT.md
  - packages/web/package.json
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - bun.lock
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/speaker/finalize.py
  - .env.example
  - packages/web/src/components/offline-ingest/UploadBanner.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/locales/en.json
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/sessions/models.py
tests:
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/components/offline-ingest/UploadBanner.test.tsx
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

---
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