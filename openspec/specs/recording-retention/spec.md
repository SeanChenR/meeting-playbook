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

The backend SHALL provide `packages/backend/meeting_playbook/retention/job.py` exporting an async function `cleanup(now: datetime, *, retention_days: int, recordings_dir: Path, attachments_dir: Path) -> int` that returns the count of files (WAV and attachment combined) actually deleted. The function SHALL:

1. Open a fresh `AsyncSession` via the application-wide session factory.
2. Select all `recording` rows where `created_at < (now - timedelta(days=retention_days)) AND deleted_at IS NULL`.
3. For each matched recording row: attempt `Path(rec.file_path).unlink()` (skip if file already missing); on success, set `rec.deleted_at = now`. On `OSError` (permission / FS issues), log a warning, skip this row, do NOT set `deleted_at` (next sweep retries).
4. Select all `meeting_attachment` rows where `uploaded_at < (now - timedelta(days=retention_days)) AND deleted_at IS NULL`.
5. For each matched attachment row: attempt `Path(att.file_path).unlink()` (skip if file already missing); on success, set `att.deleted_at = now`. On `OSError`, log a warning, skip this row, do NOT set `deleted_at`.
6. Commit all `deleted_at` updates (both recording and attachment) in a single transaction.
7. Return the count of files actually unlinked or already-missing-but-now-marked, summed across both tables.

The function SHALL be idempotent: running it twice in succession with the same `now` SHALL produce zero deletions on the second call (because all matched rows already have `deleted_at IS NOT NULL`). An exception while processing one row (recording or attachment) SHALL NOT abort the entire transaction; the row is skipped, the loop continues, and successful rows are committed.

#### Scenario: Cleanup deletes recording files older than threshold and marks rows

- **GIVEN** 3 recording rows: one with `created_at = now - 31 days` (file exists), one with `created_at = now - 5 days` (file exists), one with `created_at = now - 60 days` (file already deleted from disk by hand), and zero `meeting_attachment` rows
- **WHEN** `cleanup(now=now, retention_days=30, recordings_dir=..., attachments_dir=...)` runs
- **THEN** the 31-day-old WAV file SHALL be deleted from disk; the 5-day-old WAV SHALL remain on disk; the 60-day-old row SHALL get `deleted_at = now` (file was already gone — self-heal); all 3 rows SHALL still exist in the DB; the 5-day-old row's `deleted_at` SHALL still be NULL; the function SHALL return `2`

#### Scenario: Cleanup deletes attachment files older than threshold and marks rows

- **GIVEN** zero recording rows and 3 `meeting_attachment` rows: one with `uploaded_at = now - 31 days` (file exists), one with `uploaded_at = now - 5 days` (file exists), one with `uploaded_at = now - 45 days` (file already missing from disk)
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs
- **THEN** the 31-day-old attachment file SHALL be deleted from disk; the 5-day-old attachment SHALL remain; the 45-day-old row SHALL get `deleted_at = now`; all 3 `meeting_attachment` rows SHALL still exist; the function SHALL return `2`

#### Scenario: Cleanup processes recordings and attachments together

- **GIVEN** 2 recording rows older than 30 days (both files present) and 2 `meeting_attachment` rows older than 30 days (both files present), all with `deleted_at IS NULL`
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs
- **THEN** all 4 files SHALL be removed from disk; all 4 rows SHALL have `deleted_at = now`; the function SHALL return `4`

#### Scenario: Idempotent — second cleanup with same now is a no-op

- **GIVEN** a database state where every row older than the threshold already has `deleted_at` set
- **WHEN** `cleanup(now=now, retention_days=30, ...)` runs again immediately
- **THEN** zero additional file unlinks happen; no row's `deleted_at` is changed; no exceptions are raised; the function SHALL return `0`

#### Scenario: Transcripts and chat_messages are never touched

- **GIVEN** a meeting whose recording and attachment were just cleaned up
- **WHEN** the cleanup transaction commits
- **THEN** the meeting's `transcript_chunk` and `chat_message` rows SHALL be untouched (same row count + content as before)

#### Scenario: One row's unlink failure does not abort the transaction

- **GIVEN** 2 attachment rows older than 30 days where the first row's file path raises `PermissionError` on unlink and the second row's file unlinks successfully
- **WHEN** `cleanup(...)` runs
- **THEN** the first row's `deleted_at` SHALL remain NULL (retry next sweep), the second row's `deleted_at` SHALL be set, the function SHALL return `1`, and the loop SHALL log the permission error without propagating


<!-- @trace
source: slice-20a-meeting-attachment
updated: 2026-05-17
code:
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/public/icons/qwen.png
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/routes/settings/profile.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/index.css
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/settings/integrations.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/routes/home.tsx
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/tags/router.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/pyproject.toml
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/uv.lock
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/tags/__init__.py
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/sessions/models.py
  - README.md
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/lib/stats-api.ts
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/attachments/__init__.py
  - .env.example
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/tags/repository.py
  - packages/web/src/components/ui/dialog.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/route-tree.tsx
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/web/src/routes/settings/preferences.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/tags/models.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/components/settings/all-sections.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/backend/meeting_playbook/sessions/repository.py
  - bun.lock
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/attachments/models.py
  - CONTEXT.md
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/auth/src/server.ts
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/retention/job.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/transcript-pane.tsx
tests:
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/backend/tests/tags/test_router.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/App.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/backend/tests/attachments/test_repository.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/tags/test_models.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/routes/home.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/dashboard_stats/__init__.py
-->

---
### Requirement: Retention job runs every 24 hours via FastAPI lifespan

The backend SHALL provide `packages/backend/meeting_playbook/retention/runtime.py` exporting `run_forever(*, settings: Settings) -> None` that runs an infinite `asyncio` loop: at the top of each iteration call `cleanup(now=datetime.now(UTC), retention_days=settings.recording_retention_days, recordings_dir=Path(settings.recordings_dir).expanduser(), attachments_dir=Path(settings.attachment_dir).expanduser())`, then `await asyncio.sleep(24 * 3600)`. Exceptions inside the iteration SHALL be caught (except `asyncio.CancelledError` which re-raises) and logged via `logger.exception`; the loop SHALL continue.

The FastAPI app SHALL register a `lifespan` async context manager that spawns `run_forever` as a background `asyncio.Task` on startup and cancels it on shutdown (with `asyncio.CancelledError` suppressed during the await of the cancelled task).

#### Scenario: First cleanup runs immediately on backend startup

- **GIVEN** a backend that just booted with `RECORDING_RETENTION_DAYS = 30` and `ATTACHMENT_DIR` configured
- **WHEN** the lifespan startup hook fires
- **THEN** within 1 second `cleanup` SHALL have been invoked exactly once with both `recordings_dir` and `attachments_dir` arguments

#### Scenario: Subsequent cleanups run on a 24-hour cadence

- **GIVEN** a running backend with retention loop active
- **WHEN** 24 hours pass
- **THEN** a second `cleanup` invocation SHALL fire with the same argument signature

#### Scenario: Cleanup exception does NOT kill the loop

- **GIVEN** a stub `cleanup` that raises `RuntimeError("disk full")` on first call but succeeds on second
- **WHEN** the loop runs through two iterations
- **THEN** the first iteration SHALL log the exception traceback; the second iteration SHALL execute and succeed; the loop SHALL still be alive

#### Scenario: Lifespan shutdown cancels the loop cleanly

- **GIVEN** a running backend with retention loop active
- **WHEN** the FastAPI app shuts down
- **THEN** the lifespan finalizer SHALL cancel the task and await it; the await SHALL complete without raising (CancelledError suppressed); shutdown SHALL not hang


<!-- @trace
source: slice-20a-meeting-attachment
updated: 2026-05-17
code:
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/public/icons/qwen.png
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/routes/settings/profile.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/index.css
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/settings/integrations.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/routes/home.tsx
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/tags/router.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/pyproject.toml
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/uv.lock
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/tags/__init__.py
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/sessions/models.py
  - README.md
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/lib/stats-api.ts
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/attachments/__init__.py
  - .env.example
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/tags/repository.py
  - packages/web/src/components/ui/dialog.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/route-tree.tsx
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/web/src/routes/settings/preferences.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/tags/models.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/components/settings/all-sections.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/backend/meeting_playbook/sessions/repository.py
  - bun.lock
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/attachments/models.py
  - CONTEXT.md
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/auth/src/server.ts
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/retention/job.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/transcript-pane.tsx
tests:
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/backend/tests/tags/test_router.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/App.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/backend/tests/attachments/test_repository.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/tags/test_models.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/routes/home.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/dashboard_stats/__init__.py
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

---
### Requirement: ATTACHMENT_DIR configuration with documented default

The `Settings` class in `packages/backend/meeting_playbook/config.py` SHALL gain a new field `attachment_dir: str = "~/MeetingPlaybook/attachments"` (read from env var `ATTACHMENT_DIR` per pydantic-settings convention). The directory SHALL be created lazily on first upload if it does not exist. The `.env.example` file SHALL document the option (commented-out line referencing ADR-0020 and noting that attachments share the same retention window as recordings).

#### Scenario: Default attachment directory is `~/MeetingPlaybook/attachments`

- **GIVEN** no `ATTACHMENT_DIR` env var set
- **WHEN** `Settings()` is instantiated
- **THEN** `settings.attachment_dir` SHALL equal `"~/MeetingPlaybook/attachments"`

#### Scenario: Override via env var takes effect

- **GIVEN** env var `ATTACHMENT_DIR = /tmp/test-attachments`
- **WHEN** `Settings()` is instantiated
- **THEN** `settings.attachment_dir` SHALL equal `"/tmp/test-attachments"`

<!-- @trace
source: slice-20a-meeting-attachment
updated: 2026-05-17
code:
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/public/icons/qwen.png
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/web/src/locales/zh-TW.json
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/web/src/routes/settings/profile.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/index.css
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/src/routes/settings/integrations.tsx
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/routes/home.tsx
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/tags/router.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/pyproject.toml
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/uv.lock
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/tags/__init__.py
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/sessions/models.py
  - README.md
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/lib/stats-api.ts
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/attachments/__init__.py
  - .env.example
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/meeting_playbook/tags/repository.py
  - packages/web/src/components/ui/dialog.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/route-tree.tsx
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/web/src/routes/settings/preferences.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/tags/models.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/components/settings/all-sections.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/backend/meeting_playbook/sessions/repository.py
  - bun.lock
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/attachments/models.py
  - CONTEXT.md
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/auth/src/server.ts
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/web/package.json
  - packages/web/src/components/meeting-card.tsx
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/retention/job.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/transcript-pane.tsx
tests:
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/backend/tests/tags/test_router.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/web/src/App.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/web/src/components/meeting-card.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/backend/tests/attachments/test_repository.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/test_config.py
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/tags/test_models.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/routes/home.test.tsx
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/backend/tests/dashboard_stats/__init__.py
-->

---
### Requirement: Export bundle MUST exclude recordings whose Recording row is soft-deleted

The per-meeting export bundle MUST treat `recording.deleted_at IS NOT NULL` as the authoritative signal that a WAV is no longer available, mirroring the cleanup-job invariant established by this capability. Any export path that assembles a bundle of meeting artefacts SHALL filter its Recording query to `deleted_at IS NULL` and SHALL NOT consult the filesystem as a fallback existence check. A soft-deleted Recording row SHALL NOT be re-included by any "if the file still happens to exist on disk" heuristic; the Recording window 30-day retention is a contract, not a hint. The Playbook, transcript, and Summary belonging to the meeting are unaffected and SHALL be included in the export regardless of any Recording row's `deleted_at` status, because those artefacts are not subject to the Recording window.

#### Scenario: Bundle excludes a Recording whose deleted_at is set

- **GIVEN** a meeting with two Recording rows: `counterparty` with `deleted_at IS NULL` and `me` with `deleted_at = 2026-03-01T00:00:00Z`
- **WHEN** the per-meeting export bundle is generated for this meeting
- **THEN** the bundle SHALL contain `recordings/counterparty.wav` and SHALL NOT contain `recordings/me.wav`, even if the `me.wav` file is still present on disk for any reason

#### Scenario: Bundle preserves transcript and summary even when every Recording is expired

- **GIVEN** a meeting whose every Recording row has `deleted_at IS NOT NULL` while its Playbook, TranscriptChunk rows, and Summary row remain in the database
- **WHEN** the export bundle is generated
- **THEN** the bundle SHALL contain `playbook.md`, `transcript.md`, and `summary.md` and SHALL NOT contain any entry under the `recordings/` prefix

#### Scenario: Filesystem fallback heuristic is forbidden

- **GIVEN** a Recording row whose `deleted_at IS NOT NULL` but whose `file_path` still resolves to an existing WAV on disk (cleanup raced with a manual restore)
- **WHEN** the export bundle is generated
- **THEN** that Recording SHALL be excluded from the bundle solely because of `deleted_at IS NOT NULL`; the bundle MUST NOT include the WAV based on filesystem existence

<!-- @trace
source: slice-22-export-bundle
updated: 2026-05-17
code:
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/web/public/icons/qwen.png
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/backend/uv.lock
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/meeting_playbook/tags/repository.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/web/src/routes/settings/profile.tsx
  - packages/web/src/routes/settings/security.tsx
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/web/src/components/meetings-kanban.tsx
  - CONTEXT.md
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/index.css
  - packages/web/src/lib/calendar-api.ts
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/calendar/router.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/ui/alert.tsx
  - packages/backend/meeting_playbook/calendar/schemas.py
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/web/src/route-tree.tsx
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/meeting-links-section.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/locales/en.json
  - packages/web/src/routes/settings/tags.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/backend/meeting_playbook/tags/models.py
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/web/src/lib/stats-api.ts
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/web/package.json
  - packages/backend/meeting_playbook/retention/job.py
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/web/src/components/ui/dialog.tsx
  - packages/web/src/components/summary-pane.tsx
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/web/src/routes/settings/integrations.tsx
  - packages/web/src/components/transcript-pane.tsx
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/web/src/lib/export-api.ts
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/web/src/components/ui/button.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - README.md
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/web/src/components/playbook-pane.tsx
  - docs/adr/0027-calendar-scope-link.md
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/web/src/lib/attachments-api.ts
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/lib/tags-api.ts
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/web/src/components/user-menu.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/web/src/routes/DashboardPage.tsx
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/backend/meeting_playbook/server.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/components/settings/all-sections.tsx
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/protected-shell.tsx
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/routes/home.tsx
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/auth/src/server.ts
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/meeting_playbook/tags/__init__.py
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/backend/meeting_playbook/meetings/models.py
  - bun.lock
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/backend/meeting_playbook/calendar/token_store.py
tests:
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/backend/tests/export/test_bundler.py
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/retention/test_job.py
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/backend/tests/tags/__init__.py
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/backend/tests/calendar/test_get_event_endpoint.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/web/src/lib/calendar-api.queries.test.ts
  - packages/web/src/App.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/lib/meetings-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/meeting_links/__init__.py
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/export/test_router.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/conftest.py
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/backend/tests/attachments/__init__.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/tags/test_router.py
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/backend/tests/tags/test_models.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/web/src/lib/tag-palette.test.ts
  - packages/web/src/lib/meeting-links-api.test.ts
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/audio_playback/test_router.py
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/web/src/routes/home.test.tsx
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/offline_ingest/__init__.py
-->

---
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

---
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
