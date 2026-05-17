# meeting-attachment Specification

## Purpose

TBD - created by archiving change 'slice-20a-meeting-attachment'. Update Purpose after archive.

## Requirements

### Requirement: meeting_attachment table stores per-meeting attachment metadata

The backend SHALL provide a `meeting_attachment` table with columns `(id UUID PRIMARY KEY, meeting_id UUID NOT NULL, file_path TEXT NOT NULL, kind TEXT NOT NULL, original_name TEXT NOT NULL, bytes INTEGER NOT NULL, uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(), deleted_at TIMESTAMPTZ NULL)`. The `meeting_id` column SHALL reference `meeting.id` with `ON DELETE CASCADE` so deleting a meeting removes its attachments automatically. The `kind` column SHALL be constrained by `CHECK (kind IN ('image','pdf','docx','text','markdown'))`. The `bytes` column SHALL be constrained by `CHECK (bytes > 0)`. The table SHALL have an index on `(meeting_id, deleted_at)` to support the list endpoint. The Alembic migration SHALL be reversible: `up` creates the table, `down` drops it.

#### Scenario: Migration creates table with constraints

- **WHEN** `alembic upgrade head` runs from the prior head revision
- **THEN** the `meeting_attachment` table SHALL exist with all columns and types as specified, the `kind` CHECK constraint SHALL reject any value outside the five allowed strings, the `bytes` CHECK constraint SHALL reject zero or negative values, and the FK to `meeting.id` SHALL cascade on delete

#### Scenario: Migration down drops the table cleanly

- **GIVEN** the database at the new head with one populated `meeting_attachment` row
- **WHEN** `alembic downgrade -1` runs
- **THEN** the `meeting_attachment` table SHALL no longer exist and no other tables SHALL be affected

#### Scenario: Deleting a meeting cascades to its attachments

- **GIVEN** meeting `m_a` with three `meeting_attachment` rows
- **WHEN** the `meeting` row for `m_a` is deleted
- **THEN** all three `meeting_attachment` rows for `m_a` SHALL be removed by the database CASCADE without manual cleanup


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
### Requirement: Upload validation enforces whitelist, per-meeting file count, and per-meeting byte quota

The backend SHALL validate every attachment upload before persisting the file or row. The validation SHALL reject the upload with HTTP 422 and a specific `error_code` when any of the following conditions are met:

1. The declared `Content-Type` is NOT in the whitelist `{image/jpeg, image/png, image/webp, application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, text/plain, text/markdown}` AND the file extension is NOT in the whitelist `{.jpg, .jpeg, .png, .webp, .pdf, .docx, .txt, .md, .markdown}` → `error_code = "attachment.unsupported_format"`.
2. The meeting already has 10 or more active (`deleted_at IS NULL`) attachment rows → `error_code = "attachment.too_many"`.
3. The sum of `bytes` across active attachment rows for this meeting PLUS the incoming file's size would exceed `60 * 1024 * 1024` bytes (60 MiB) → `error_code = "attachment.quota_exceeded"`.

When validation passes, the backend SHALL infer `kind` as follows: if `Content-Type` matches the whitelist, use the mapped kind; otherwise fall back to extension lookup. When validation fails, the staged file (if any) SHALL be removed from disk before responding so partial uploads do not accumulate.

Rationale for the file count and byte limits: per `meeting-attachment` design D12, the per-meeting limits are aligned with the per-user staging limits (10 files / 60 MiB). Aligning the two surfaces means a user's mental model of "what fits" is the same in `/meetings/new` and on the meeting detail page.

#### Scenario: Unsupported format is rejected

- **GIVEN** an authenticated user uploading a file with `Content-Type: image/bmp` and filename `chart.bmp` to a meeting with zero existing attachments
- **WHEN** the request reaches `POST /api/meetings/{meeting_id}/attachments`
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.unsupported_format"`, no row SHALL be written to `meeting_attachment`, and no file SHALL remain on disk under `ATTACHMENT_DIR`

#### Scenario: Eleventh attachment is rejected

- **GIVEN** an authenticated user and a meeting that already has 10 active `meeting_attachment` rows totalling 10 MiB
- **WHEN** the user POSTs an eleventh valid 1 MiB PDF
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.too_many"`, the existing 10 rows SHALL remain unchanged, and no new file SHALL be persisted

#### Scenario: Cumulative byte quota is enforced

- **GIVEN** an authenticated user and a meeting whose active attachments sum to 58 MiB across 3 rows
- **WHEN** the user POSTs a 3 MiB PDF
- **THEN** the response SHALL be HTTP 422 with `error_code = "attachment.quota_exceeded"`, the 3 existing rows SHALL remain unchanged, and the staged 3 MiB file SHALL be removed from disk

#### Scenario: Markdown file with octet-stream Content-Type accepted via extension fallback

- **GIVEN** an authenticated user uploading `notes.md` whose browser-provided `Content-Type` is `application/octet-stream`
- **WHEN** the request reaches the upload endpoint
- **THEN** the backend SHALL infer `kind = "markdown"` from the `.md` extension fallback, persist the file, and return HTTP 200 with `{id, kind: "markdown", original_name: "notes.md", bytes, uploaded_at}`


<!-- @trace
source: slice-24-attachment-staging-at-create
updated: 2026-05-17
code:
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/package.json
  - CONTEXT.md
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/retention/job.py
  - .env.example
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/export-api.ts
  - bun.lock
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meetings/router.py
tests:
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/export/test_bundler.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/export/test_router.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/meeting-links-api.test.ts
-->

---
### Requirement: GET list endpoint returns active attachments for the meeting owner

The backend SHALL expose `GET /api/meetings/{meeting_id}/attachments` returning HTTP 200 with body `{"attachments": [{"id": ..., "kind": ..., "original_name": ..., "bytes": ..., "uploaded_at": ...}, ...]}` ordered by `uploaded_at ASC`. Only rows where `deleted_at IS NULL` SHALL be returned. The endpoint SHALL return HTTP 404 when the `meeting_id` does not exist OR is not owned by the authenticated user; the response body SHALL NOT distinguish between "not found" and "not owned" to avoid leaking ownership.

#### Scenario: Owner lists active attachments

- **GIVEN** user `u_a` who owns meeting `m_a` with 2 active attachments and 1 soft-deleted attachment (`deleted_at` set 2 days ago)
- **WHEN** `u_a` sends `GET /api/meetings/m_a/attachments`
- **THEN** the response SHALL be HTTP 200 with exactly 2 attachment entries in `attachments`, both with `deleted_at IS NULL` semantics (their `deleted_at` is not returned in the body)

#### Scenario: Non-owner receives 404

- **GIVEN** user `u_b` who does NOT own meeting `m_a`
- **WHEN** `u_b` sends `GET /api/meetings/m_a/attachments`
- **THEN** the response SHALL be HTTP 404 and the body SHALL NOT confirm or deny the existence of `m_a`


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
### Requirement: POST upload endpoint persists file and row on success

The backend SHALL expose `POST /api/meetings/{meeting_id}/attachments` accepting `multipart/form-data` with a single field `file`. On a validation-passing upload the endpoint SHALL: (a) persist the file under `ATTACHMENT_DIR/{meeting_id}/{attachment_id}.<canonical_extension>` where `canonical_extension` is determined by the inferred `kind`; (b) insert a `meeting_attachment` row with `(id, meeting_id, file_path, kind, original_name=<browser-provided name>, bytes=<actual bytes written>, uploaded_at=now())`; (c) return HTTP 200 with body `{"id", "kind", "original_name", "bytes", "uploaded_at"}`. The endpoint SHALL return HTTP 404 when the `meeting_id` does not exist or is not owned by the authenticated user.

#### Scenario: Owner uploads a valid PDF successfully

- **GIVEN** an authenticated owner `u_a` of meeting `m_a` with zero existing attachments, and a 2 MiB PDF named `proposal.pdf`
- **WHEN** `u_a` POSTs the file to `/api/meetings/m_a/attachments`
- **THEN** the response SHALL be HTTP 200 with `kind = "pdf"`, `original_name = "proposal.pdf"`, `bytes = 2097152`, and `uploaded_at` populated; a row SHALL exist in `meeting_attachment` with the matching `id`; a file SHALL exist at `ATTACHMENT_DIR/m_a/<id>.pdf` whose byte count equals `bytes`

#### Scenario: Upload to non-owned meeting returns 404

- **GIVEN** an authenticated user `u_b` who does not own meeting `m_a`
- **WHEN** `u_b` POSTs a valid PDF to `/api/meetings/m_a/attachments`
- **THEN** the response SHALL be HTTP 404, no row SHALL be inserted, and no file SHALL be written to disk


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
### Requirement: DELETE endpoint soft-deletes the row and unlinks the file

The backend SHALL expose `DELETE /api/meetings/{meeting_id}/attachments/{attachment_id}` that sets `deleted_at = now()` on the matching row and calls `Path(file_path).unlink(missing_ok=True)` to remove the file. The endpoint SHALL return HTTP 204 with empty body. The endpoint SHALL return HTTP 404 when the attachment does not exist, does not belong to the meeting, or the meeting is not owned by the authenticated user. Subsequent `GET list` calls SHALL NOT return the deleted attachment.

#### Scenario: Owner deletes an active attachment

- **GIVEN** an authenticated owner of meeting `m_a` and an attachment `a_x` whose `deleted_at IS NULL` and whose file exists on disk
- **WHEN** the owner sends `DELETE /api/meetings/m_a/attachments/a_x`
- **THEN** the response SHALL be HTTP 204, the row's `deleted_at` SHALL be populated, the file SHALL be removed from disk, and a subsequent `GET /api/meetings/m_a/attachments` SHALL NOT include `a_x`

#### Scenario: Delete of already-deleted attachment returns 404

- **GIVEN** an attachment `a_x` whose `deleted_at` was set 1 day ago
- **WHEN** the owner sends `DELETE /api/meetings/m_a/attachments/a_x`
- **THEN** the response SHALL be HTTP 404 (the repository treats soft-deleted rows as not found from the API perspective)


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
### Requirement: Download endpoint streams the file with original filename

The backend SHALL expose `GET /api/meetings/{meeting_id}/attachments/{attachment_id}/download` that returns the raw file bytes with `Content-Disposition: attachment; filename="<original_name>"` and a `Content-Type` matching the row's `kind`. The endpoint SHALL return HTTP 404 when the attachment does not exist, does not belong to the meeting, is soft-deleted, or the meeting is not owned by the authenticated user. The endpoint SHALL return HTTP 410 with `error_code = "attachment.expired"` when the row exists with `deleted_at IS NULL` but the underlying file is missing from disk (retention cleanup has run between row read and file open).

#### Scenario: Owner downloads an active attachment

- **GIVEN** an authenticated owner of meeting `m_a` and an active attachment `a_x` whose `original_name = "quote.pdf"` and whose file is present on disk
- **WHEN** the owner sends `GET /api/meetings/m_a/attachments/a_x/download`
- **THEN** the response SHALL be HTTP 200 with `Content-Disposition: attachment; filename="quote.pdf"`, `Content-Type: application/pdf`, and a body whose byte count equals the row's `bytes` column

#### Scenario: Download after disk file has gone missing returns 410

- **GIVEN** an attachment row whose `deleted_at IS NULL` but whose `file_path` no longer exists on disk
- **WHEN** the owner sends the download request
- **THEN** the response SHALL be HTTP 410 with body `{error_code: "attachment.expired", message: ...}`


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
### Requirement: AttachmentDropzone component renders list, dropzone, and progress

The frontend SHALL ship a component `<AttachmentDropzone>` at `packages/web/src/components/attachment-dropzone.tsx` that the meeting detail page renders below the Playbook pane in a collapsible section. The component SHALL display: (a) a list of existing active attachments showing a `kind`-appropriate icon, the `original_name`, formatted `bytes` (e.g., "2.1 MB"), formatted `uploaded_at`, a download button, and a delete button; (b) a drag-drop region that accepts the whitelist mime types and shows the hint "最多 10 個檔案、60 MiB 上限" / "Max 10 files, 60 MiB total"; (c) a per-file upload progress indicator driven by `XMLHttpRequest.upload.onprogress`; (d) localized error rendering via `localizedErrorMessage(errorCode, t)` when the backend returns HTTP 422 or 410. All visible strings SHALL be sourced from `react-i18next` keys present in BOTH `packages/web/src/locales/zh-TW.json` AND `packages/web/src/locales/en.json`.

#### Scenario: Dropping a file shows progress and adds to list on success

- **GIVEN** a meeting detail page mounted with zero existing attachments and the backend stubbed to respond HTTP 200 with `{id: "a_1", kind: "pdf", original_name: "proposal.pdf", bytes: 2097152, uploaded_at: "2026-05-15T12:00:00Z"}`
- **WHEN** the user drops a valid 2 MiB PDF onto the dropzone
- **THEN** the component SHALL display an upload progress card transitioning from 0% to 100%; on completion the card SHALL be removed AND a new attachment row SHALL appear in the list with the PDF icon, `original_name = "proposal.pdf"`, and `bytes = "2.0 MB"` (or "2.1 MB" with the project's standard rounding)


<!-- @trace
source: slice-24-attachment-staging-at-create
updated: 2026-05-17
code:
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/package.json
  - CONTEXT.md
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/retention/job.py
  - .env.example
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/export-api.ts
  - bun.lock
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meetings/router.py
tests:
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/export/test_bundler.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/export/test_router.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/meeting-links-api.test.ts
-->

---
### Requirement: meeting_attachment row supports staged (orphan) state

The `meeting_attachment` table SHALL allow rows with `meeting_id IS NULL`,
representing an attachment uploaded by a user but not yet bound to a
meeting. Such rows are referred to as **staged**.

To preserve ownership when `meeting_id IS NULL`, the table SHALL carry a
`user_id TEXT NOT NULL` column with a foreign key to `user.id`. The
existing FK from `meeting_id` to `meeting.id` remains `ON DELETE CASCADE`
for the attached case.

Staged rows are sweep-eligible by the existing retention job after
`STAGED_ATTACHMENT_TTL_HOURS` (default 24) have elapsed since
`uploaded_at`.

#### Scenario: Staged row exists with NULL meeting_id and explicit user_id

- **GIVEN** a user uploads a file to the staging endpoint
- **WHEN** the upload succeeds
- **THEN** a row in `meeting_attachment` is created with
  `meeting_id = NULL`, `user_id = <the uploader's id>`, `deleted_at = NULL`,
  and `file_path` pointing under `ATTACHMENT_DIR/_staging/<user_id>/`

#### Scenario: Attached row carries user_id mirroring its meeting's owner

- **GIVEN** a row whose `meeting_id` is non-null
- **THEN** that row's `user_id` SHALL equal the `user_id` of the meeting
  named by `meeting_id`


<!-- @trace
source: slice-24-attachment-staging-at-create
updated: 2026-05-17
code:
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/package.json
  - CONTEXT.md
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/retention/job.py
  - .env.example
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/export-api.ts
  - bun.lock
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meetings/router.py
tests:
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/export/test_bundler.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/export/test_router.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/meeting-links-api.test.ts
-->

---
### Requirement: POST /api/attachments/staging uploads to user-scoped staging path

`POST /api/attachments/staging` SHALL accept a multipart `file` field,
validate it against the existing per-meeting whitelist (image/jpeg,
image/png, image/webp, application/pdf, application/vnd.openxml...docx,
text/plain, text/markdown), and persist the file under
`ATTACHMENT_DIR/_staging/<user_id>/<attachment_id><ext>`.

The endpoint SHALL respond HTTP 201 with the same `Attachment` JSON shape
returned by the existing per-meeting upload endpoint, where `meeting_id`
is omitted (or null) and all other fields populated from the new row.

The endpoint SHALL enforce a **per-user staging quota** before persisting:

- Total staged file count (`meeting_id IS NULL AND deleted_at IS NULL AND
  user_id = current`) MUST be less than 10 before this upload
- Total staged bytes for the same set MUST be less than 60 MiB before
  this upload

Quota violations SHALL respond HTTP 422 with error_code
`attachment.staging_quota_exceeded`.

#### Scenario: Successful staged upload returns 201 with attachment payload

- **GIVEN** the user has 0 staged attachments
- **WHEN** they POST a 5 MiB PDF to `/api/attachments/staging`
- **THEN** the response is HTTP 201 with body matching the `Attachment`
  shape (`id`, `kind`, `original_name`, `bytes`, `uploaded_at`)
- **AND** the file exists on disk under
  `ATTACHMENT_DIR/_staging/<user_id>/<att_id>.pdf`
- **AND** a row exists in `meeting_attachment` with `meeting_id = NULL`
  and `user_id = <user>`

#### Scenario: Eleventh staged file is rejected

- **GIVEN** the user already has 10 active staged attachments
- **WHEN** they POST another file to `/api/attachments/staging`
- **THEN** the response is HTTP 422 with body
  `{"error_code": "attachment.staging_quota_exceeded", "message": ...}`
- **AND** no row is created and no file is written

#### Scenario: Staged bytes exceeding 60 MiB rejects the upload

- **GIVEN** the user's existing staged attachments total 58 MiB
- **WHEN** they POST a 5 MiB file
- **THEN** the response is HTTP 422 with error_code
  `attachment.staging_quota_exceeded`

#### Scenario: Disallowed MIME type rejects the upload

- **GIVEN** the user is within staging quota
- **WHEN** they POST a `.zip` file
- **THEN** the response is HTTP 422 with error_code
  `attachment.unsupported_format` (same code as per-meeting upload)


<!-- @trace
source: slice-24-attachment-staging-at-create
updated: 2026-05-17
code:
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/package.json
  - CONTEXT.md
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/retention/job.py
  - .env.example
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/export-api.ts
  - bun.lock
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meetings/router.py
tests:
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/export/test_bundler.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/export/test_router.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/meeting-links-api.test.ts
-->

---
### Requirement: GET /api/attachments?status=pending lists the user's staged attachments

`GET /api/attachments?status=pending` SHALL return HTTP 200 with body
`{"attachments": [Attachment, ...]}` containing every row where
`user_id = <current user>`, `meeting_id IS NULL`, and
`deleted_at IS NULL`. The list SHALL be sorted by `uploaded_at` ascending
so the UI renders them in upload order.

If `status` query is absent or any value other than `"pending"`, the
endpoint SHALL respond HTTP 422 with error_code
`attachment.invalid_status_filter`.

#### Scenario: Lists only the caller's staged rows

- **GIVEN** user A has 2 staged attachments and user B has 1 staged
  attachment
- **WHEN** user A calls `GET /api/attachments?status=pending`
- **THEN** the response body's `attachments` array has length 2
- **AND** none of the entries belong to user B

#### Scenario: Already-attached rows are excluded

- **GIVEN** user A has 1 staged row and 3 rows attached to existing
  meetings
- **WHEN** user A calls `GET /api/attachments?status=pending`
- **THEN** the response body's `attachments` array has length 1
- **AND** the entry's `id` matches the staged row

#### Scenario: Soft-deleted rows are excluded

- **GIVEN** user A has 1 staged row with `deleted_at` set to the past
  (soft-deleted)
- **WHEN** user A calls `GET /api/attachments?status=pending`
- **THEN** the response body's `attachments` array is empty


<!-- @trace
source: slice-24-attachment-staging-at-create
updated: 2026-05-17
code:
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/package.json
  - CONTEXT.md
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/retention/job.py
  - .env.example
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/export-api.ts
  - bun.lock
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meetings/router.py
tests:
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/export/test_bundler.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/export/test_router.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/meeting-links-api.test.ts
-->

---
### Requirement: DELETE /api/attachments/{id} removes a staged row only

`DELETE /api/attachments/{attachment_id}` SHALL accept ids of rows where
`meeting_id IS NULL` AND `user_id = <current user>` AND `deleted_at IS NULL`.
On success it SHALL unlink the file on disk and set `deleted_at` on the
row, then respond HTTP 204.

For ids that match an attached row (`meeting_id IS NOT NULL`), the
endpoint SHALL respond HTTP 404 with error_code `attachment.not_found` —
the caller MUST use the per-meeting delete endpoint instead. Cross-user
ids SHALL also return 404 to avoid information leak.

#### Scenario: Delete staged row succeeds with 204

- **GIVEN** a staged row owned by the caller
- **WHEN** they DELETE `/api/attachments/<id>`
- **THEN** the response is HTTP 204
- **AND** the row's `deleted_at` is now set
- **AND** the file at `ATTACHMENT_DIR/_staging/<user>/<id>.*` is removed

#### Scenario: Delete attached row returns 404

- **GIVEN** an attached row (`meeting_id IS NOT NULL`) owned by the caller
- **WHEN** they DELETE `/api/attachments/<id>` (top-level, not the
  per-meeting endpoint)
- **THEN** the response is HTTP 404 with error_code `attachment.not_found`
- **AND** the row is unchanged

#### Scenario: Cross-user staged row returns 404

- **GIVEN** a staged row owned by user B
- **WHEN** user A calls DELETE `/api/attachments/<that_id>`
- **THEN** the response is HTTP 404 with error_code `attachment.not_found`


<!-- @trace
source: slice-24-attachment-staging-at-create
updated: 2026-05-17
code:
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/package.json
  - CONTEXT.md
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/retention/job.py
  - .env.example
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/export-api.ts
  - bun.lock
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meetings/router.py
tests:
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/export/test_bundler.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/export/test_router.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/meeting-links-api.test.ts
-->

---
### Requirement: Retention job sweeps staged attachments older than the TTL

The existing `RecordingRetentionJob.cleanup` job SHALL, on each scheduled
run, additionally delete rows where:

- `meeting_id IS NULL`
- `deleted_at IS NULL`
- `uploaded_at < now() - STAGED_ATTACHMENT_TTL_HOURS hours`

For each such row, the job SHALL unlink the file at the row's `file_path`
(best-effort — `OSError` is logged and ignored), then hard-DELETE the row
(not soft-delete; staged rows are throwaway).

The 30-day soft-delete sweep for attached rows is unchanged.

#### Scenario: Staged row older than TTL is deleted

- **GIVEN** a staged row with `uploaded_at` = 25 hours ago and
  `STAGED_ATTACHMENT_TTL_HOURS = 24`
- **WHEN** `RecordingRetentionJob.cleanup` runs
- **THEN** the row is removed from `meeting_attachment`
- **AND** the on-disk file is unlinked

#### Scenario: Staged row younger than TTL is kept

- **GIVEN** a staged row with `uploaded_at` = 1 hour ago and
  `STAGED_ATTACHMENT_TTL_HOURS = 24`
- **WHEN** the cleanup job runs
- **THEN** the row is still present
- **AND** the file is still on disk


<!-- @trace
source: slice-24-attachment-staging-at-create
updated: 2026-05-17
code:
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/package.json
  - CONTEXT.md
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/retention/job.py
  - .env.example
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/export-api.ts
  - bun.lock
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meetings/router.py
tests:
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/export/test_bundler.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/export/test_router.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/meeting-links-api.test.ts
-->

---
### Requirement: Frontend StagedAttachmentDropzone uploads to staging and lists current staged

The web UI SHALL provide a `<StagedAttachmentDropzone>` component that
the `/meetings/new` route mounts. The component SHALL:

- Render a drag-drop zone that accepts the same MIME whitelist as the
  per-meeting dropzone
- Accept **multi-file selection** via both drag-drop (a `DataTransfer.files`
  FileList) and the file picker (the underlying `<input type="file">`
  carries the `multiple` attribute). For each accepted file the component
  SHALL call `uploadStagedAttachment` sequentially (one POST completes
  before the next starts) and append each resulting row to the list
- Apply **client-side quota truncation** before issuing any POST using a
  **skip-and-continue (accept-what-fits) algorithm**: iterate the dropped
  files in drop order, maintaining a running staged count and byte sum
  (initialized from the current staged list). For each file, accept it
  if AND only if `running_count + 1 <= 10` AND
  `running_bytes + file.size <= 60 * 1024 * 1024`; otherwise skip that
  file (count it toward `dropped`) and continue to the next. The skip
  rule SHALL NOT short-circuit — a large file that would overflow does
  not block smaller subsequent files that still fit. When `dropped > 0`,
  render an inline warning (`attachment.staging_batch_truncated`)
  naming `dropped` and `accepted` counts. Backend per-file enforcement
  of the quota remains the source of truth — truncation is a UX
  optimization, not a security boundary
- Render a **quota counter** of the shape `<used>/10 個 · <bytesUsed>/60 MiB`
  derived from the current staged list. Counter SHALL update reactively
  whenever the staged list changes
- When `current_staged_count === 10` OR
  `current_staged_bytes >= 60 * 1024 * 1024`, the drop area AND the
  upload button SHALL be `disabled`, and an at-limit hint
  (`staging.at_limit`) SHALL render in place of the empty-state text
- For each listed staged attachment, render a "remove" button that calls
  `deleteStagedAttachment` and removes the row from the list
- Show upload progress (0..100%) per file while a POST is in flight
- Localize backend error codes (`attachment.staging_quota_exceeded`,
  `attachment.unsupported_format`, etc.) via `localizedErrorMessage`

When the user clicks "建立" on `/meetings/new`, the submit handler SHALL
include the ids of every currently-listed staged attachment in the
`POST /api/meetings` request's `attachments[]` field.

#### Scenario: Drop one PDF, see it in the list

- **GIVEN** the user is on `/meetings/new` with the dropzone mounted and
  no staged attachments
- **WHEN** they drop a 2 MiB PDF onto the dropzone
- **THEN** the list above the dropzone renders one row showing the
  filename and size
- **AND** the staged attachment is included in the next form submission's
  `attachments[]`

#### Scenario: Drop three files at once uploads all three sequentially

- **GIVEN** the user has 0 staged attachments and the counter reads `0/10`
- **WHEN** they drop three files (1 MiB PDF, 2 MiB PNG, 3 MiB PDF) onto
  the dropzone in one drag operation
- **THEN** three sequential `POST /api/attachments/staging` requests are
  issued (next starts after the previous resolves)
- **AND** the list renders three rows in upload order
- **AND** the counter advances `0/10 → 1/10 → 2/10 → 3/10` and
  `0/60 MiB → 1/60 MiB → 3/60 MiB → 6/60 MiB`
- **AND** the submit handler's `attachments[]` contains all three ids

#### Scenario: Drop files that would exceed the file-count quota are truncated

- **GIVEN** the user has 8 staged attachments and the counter reads `8/10`
- **WHEN** they drop 5 files onto the dropzone
- **THEN** only the first 2 files are uploaded (one sequential POST each)
- **AND** an inline warning renders with `error_code:
  staging.batch_truncated`, message naming `dropped: 5, accepted: 2`
- **AND** the remaining 3 files are NOT sent to the backend
- **AND** the counter ends at `10/10`

#### Scenario: Drop files that would exceed the byte quota are truncated

- **GIVEN** the user has 1 staged file totalling 58 MiB
  (counter: `1/10 · 58/60 MiB`)
- **WHEN** they drop a 3 MiB file and a 1 MiB file in one operation
- **THEN** only the 1 MiB file is uploaded (the 3 MiB file would push
  total to 61 MiB)
- **AND** the inline warning renders with `staging.batch_truncated`
  naming `dropped: 2, accepted: 1`

#### Scenario: At-limit state disables the dropzone

- **GIVEN** the user has 10 staged attachments
- **WHEN** the dropzone renders
- **THEN** the drop area's `disabled` attribute is true (drag-over does
  not light up)
- **AND** the upload button is `disabled`
- **AND** the empty-state text is replaced with the at-limit hint
  (`staging.at_limit`)
- **AND** the counter reads `10/10`

#### Scenario: Removing a staged row re-enables the dropzone

- **GIVEN** the user has 10 staged attachments and the dropzone is in
  the at-limit state
- **WHEN** they click the remove button on one staged row
- **THEN** the counter drops to `9/10`
- **AND** the drop area is no longer `disabled`
- **AND** the at-limit hint is replaced with the empty-state / normal text

#### Scenario: Remove a staged file from the list

- **GIVEN** the user has 2 staged attachments listed
- **WHEN** they click the remove button on the first one
- **THEN** the list re-renders with only the second attachment
- **AND** the backend `DELETE /api/attachments/<first>` was called
- **AND** the next form submission's `attachments[]` does NOT include
  the removed id

<!-- @trace
source: slice-24-attachment-staging-at-create
updated: 2026-05-17
code:
  - packages/web/src/components/export-meeting-button.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/web/src/components/meeting-links-section.tsx
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/meeting_links/models.py
  - packages/web/src/components/staged-attachment-dropzone.tsx
  - packages/web/src/lib/meetings-api.ts
  - packages/backend/meeting_playbook/export/bundler.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/backend/meeting_playbook/meeting_links/repository.py
  - packages/web/src/components/playbook-diff-viewer.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/web/package.json
  - CONTEXT.md
  - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/web/src/lib/meeting-links-api.ts
  - packages/backend/meeting_playbook/export/router.py
  - packages/web/src/components/meeting-link-picker.tsx
  - packages/backend/meeting_playbook/meeting_links/router.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/lib/i18n-errors.ts
  - packages/backend/meeting_playbook/retention/job.py
  - .env.example
  - packages/web/src/components/metadata-card.tsx
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/export-api.ts
  - bun.lock
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/backend/meeting_playbook/attachments/staging_router.py
  - packages/backend/alembic/versions/0020_attachment_nullable_meeting.py
  - packages/backend/meeting_playbook/export/__init__.py
  - packages/backend/meeting_playbook/meeting_links/__init__.py
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/backend/meeting_playbook/meeting_links/schemas.py
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/alembic/versions/0019_meeting_link.py
  - packages/web/src/components/playbook-pane.tsx
  - packages/backend/meeting_playbook/export/markdown.py
  - packages/backend/meeting_playbook/meetings/router.py
tests:
  - packages/backend/tests/meeting_links/test_repository.py
  - packages/web/src/components/meeting-links-section.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/playbook-diff-viewer.test.tsx
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/export-api.test.ts
  - packages/backend/tests/export/test_markdown.py
  - packages/backend/tests/attachments/test_staging_attach_flow.py
  - packages/backend/tests/attachments/test_repository.py
  - packages/backend/tests/playbooks/test_versioning_repository.py
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/backend/tests/test_alembic_playbook_previous.py
  - packages/backend/tests/test_alembic_attachment_nullable.py
  - packages/web/src/components/meeting-link-picker.test.tsx
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - packages/backend/tests/test_config.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/meeting_links/__init__.py
  - packages/backend/tests/export/__init__.py
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/export/test_bundler.py
  - packages/web/src/components/export-meeting-button.test.tsx
  - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
  - packages/backend/tests/meeting_links/test_models.py
  - packages/web/src/lib/playbook-api.test.ts
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/web/src/components/playbook-pane.test.tsx
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/playbooks/test_endpoints.py
  - packages/backend/tests/attachments/test_staging_endpoints.py
  - packages/backend/tests/meeting_links/test_router.py
  - packages/web/src/lib/i18n-errors.test.ts
  - packages/backend/tests/export/test_router.py
  - packages/backend/tests/integration/test_meeting_link_e2e.py
  - packages/backend/tests/playbooks/test_router.py
  - packages/backend/tests/test_alembic_meeting_link.py
  - packages/web/src/lib/meeting-links-api.test.ts
-->