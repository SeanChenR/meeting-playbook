# meeting-summary Specification

## Purpose

TBD - created by archiving change 'slice-10-post-meeting-summary'. Update Purpose after archive.

## Requirements

### Requirement: summary table persists per-meeting markdown summary

The backend SHALL provide a `summary` table (Alembic migration `0006_create_summary` plus migration `0014_add_attachment_hash_snapshot`) with exactly five columns: `id` (TEXT primary key, format `sm_<token>`), `meeting_id` (TEXT, NOT NULL, UNIQUE, foreign key to `meeting.id` ON DELETE CASCADE), `markdown` (TEXT, NOT NULL), `generated_at` (TIMESTAMPTZ, NOT NULL, DEFAULT `now()`), and `attachment_hash_snapshot` (TEXT, NULL). The `UNIQUE (meeting_id)` constraint enforces a 1:1 relationship between meeting and summary. Deleting a `meeting` row SHALL cascade-delete the associated `summary` row.

The backend SHALL provide `SummaryRepository` at `packages/backend/meeting_playbook/summarization/repository.py` as the SOLE access path for `summary` rows. The repository SHALL expose `get_for_meeting(meeting_id) -> Summary | None`, `get_with_stale_flag(meeting_id) -> SummaryWithStale | None` (returns the row plus a computed `is_stale` boolean — see the "Summary is_stale flag" requirement for the full computation), and `upsert(meeting_id, markdown, attachment_hash_snapshot) -> Summary` (uses PostgreSQL `INSERT ... ON CONFLICT (meeting_id) DO UPDATE SET markdown = EXCLUDED.markdown, generated_at = now(), attachment_hash_snapshot = EXCLUDED.attachment_hash_snapshot RETURNING *`). The repository SHALL NOT expose any delete method.

#### Scenario: summary row cascade-deletes with the parent meeting

- **GIVEN** a meeting with one `summary` row
- **WHEN** the meeting row is deleted
- **THEN** the `summary` row SHALL be deleted by FK cascade

#### Scenario: upsert replaces existing markdown atomically and updates attachment_hash_snapshot

- **GIVEN** a meeting whose summary was generated yesterday with markdown "v1" and `attachment_hash_snapshot = "h_old"`
- **WHEN** `repo.upsert(meeting_id, markdown="v2", attachment_hash_snapshot="h_new")` runs
- **THEN** the database SHALL contain exactly one summary row for the meeting with `markdown = "v2"`, `generated_at` updated to now (within 1 second tolerance), AND `attachment_hash_snapshot = "h_new"`

#### Scenario: get_for_meeting on missing summary returns None

- **GIVEN** a meeting that has never been summarized
- **WHEN** `repo.get_for_meeting(meeting_id)` runs
- **THEN** the call SHALL return `None`

#### Scenario: Legacy rows with NULL attachment_hash_snapshot remain readable

- **GIVEN** a `summary` row written before this migration with `attachment_hash_snapshot IS NULL`
- **WHEN** `repo.get_for_meeting(meeting_id)` runs
- **THEN** the call SHALL succeed and the returned `Summary.attachment_hash_snapshot` attribute SHALL be `None`


<!-- @trace
source: slice-20c-multimodal-input
updated: 2026-05-17
code:
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/uv.lock
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/metadata-card.tsx
  - .env.example
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/integrations.tsx
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/tags/__init__.py
  - README.md
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/retention/job.py
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/profile.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/package.json
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/web/src/lib/stats-api.ts
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/tags/models.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/components/ui/dialog.tsx
  - CONTEXT.md
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - bun.lock
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/settings/all-sections.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/public/icons/qwen.png
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/index.css
  - packages/web/src/components/playbook-pane.tsx
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/tags/repository.py
tests:
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/conftest.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/tags/test_router.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/tags/test_models.py
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/App.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/test_config.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/attachments/test_repository.py
-->

---
### Requirement: MeetingSummarizer module exposes a single coroutine summarize()

The backend SHALL provide a `MeetingSummarizer` Protocol (and a concrete `VertexProSummarizer` implementation) located at `packages/backend/meeting_playbook/summarization/`. The Protocol's single coroutine `summarize(meeting_id: str) -> SummaryGenerationResult` SHALL return a dataclass containing `markdown: str` (the full summary text) AND `attachment_hash_snapshot: str` (hex SHA-256 of the attachment set seen during generation, equal to the canonical empty-set hash when zero attachments are present). The Protocol SHALL be the SOLE entry point used by `summarization/runtime.py` to invoke the underlying LLM; no other module SHALL import any Vertex / `google-genai` symbol directly.

The concrete `VertexProSummarizer` SHALL wrap the official `google-genai` SDK against Vertex AI. The model id SHALL come from `Settings.vertex_pro_model_id` (default `gemini-2.5-pro`). The implementation SHALL apply a 90-second outer `asyncio.timeout` so a hung Vertex stream raises `asyncio.TimeoutError` rather than blocking the background task indefinitely. The implementation SHALL fetch context (transcript chunks via `SessionRepository.list_chunks_for_meeting`, playbook via `PlaybookRepository.get_or_create_for_meeting`, chat history via `ChatMessageRepository.list_for_meeting`, and attachments via `MeetingAttachmentRepository.list_for_meeting`) inside its own `async with session_factory() as ...` scope; the LLM call itself SHALL run OUTSIDE the session block (no DB connection held during the LLM round-trip).

The implementation SHALL pass the assembled `MultimodalContext.parts` to `client.models.generate_content(contents=parts, ...)` when at least one attachment was successfully processed; otherwise it SHALL pass the legacy single-text-string `contents` to preserve identical behaviour to the pre-S20c implementation.

The implementation SHALL validate that the returned markdown contains exactly four required headings (case- and trim-insensitive match) in fixed order. Missing or out-of-order headings SHALL raise `SummaryFormatError`; the runtime treats this same as a Vertex failure (no upsert).

#### Scenario: summarize returns markdown with all four required sections and an attachment hash

- **GIVEN** a mocked Vertex client returning markdown that contains "## 重點討論", "## 決議", "## Action items", and "## 待解決問題" in order AND a meeting with one PDF attachment whose bytes hash to `h_pdf`
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL return `SummaryGenerationResult(markdown=<the markdown verbatim>, attachment_hash_snapshot=sha256(sorted([h_pdf])))`

#### Scenario: summarize with zero attachments returns the canonical empty-set hash

- **GIVEN** a mocked Vertex client returning valid markdown AND a meeting with zero attachments
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the returned `attachment_hash_snapshot` SHALL equal `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`

#### Scenario: summarize with mixed image and PDF passes Part list to Vertex

- **GIVEN** a meeting with one PNG attachment and one PDF attachment
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the `contents` argument passed to `client.models.generate_content(...)` SHALL be a `list[Part]` whose first element is `Part.from_bytes(data=<png bytes>, mime_type="image/png")` and whose subsequent text part contains both the PDF-extracted text and the transcript / playbook / chat sections

#### Scenario: 90-second cap on Vertex call raises TimeoutError

- **GIVEN** a mocked Vertex client that sleeps 100 seconds before returning AND any attachment configuration
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL raise `asyncio.TimeoutError` between 90.0 and 92.0 seconds after invocation

#### Scenario: Missing required heading raises SummaryFormatError

- **GIVEN** a mocked Vertex client returning markdown that omits the "## 決議" heading
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the call SHALL raise `SummaryFormatError` (which the runtime catches and treats as a generation failure — no upsert, log warning, pop in-flight)

#### Scenario: A corrupt PDF among attachments is skipped, not fatal

- **GIVEN** a meeting with one good PNG and one corrupt PDF that raises during `pypdf` extraction
- **WHEN** `summarizer.summarize("m_x")` runs
- **THEN** the Vertex call SHALL succeed with `contents` containing the good PNG part plus a text part assembled from the remaining context, the returned `attachment_hash_snapshot` SHALL hash only the good PNG, AND a structured warning naming the corrupt PDF's `attachment_id` and `error_code = "attachment.extraction_failed"` SHALL be logged


<!-- @trace
source: slice-20c-multimodal-input
updated: 2026-05-17
code:
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/uv.lock
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/metadata-card.tsx
  - .env.example
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/integrations.tsx
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/tags/__init__.py
  - README.md
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/retention/job.py
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/profile.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/package.json
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/web/src/lib/stats-api.ts
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/tags/models.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/components/ui/dialog.tsx
  - CONTEXT.md
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - bun.lock
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/settings/all-sections.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/public/icons/qwen.png
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/index.css
  - packages/web/src/components/playbook-pane.tsx
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/tags/repository.py
tests:
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/conftest.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/tags/test_router.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/tags/test_models.py
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/App.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/test_config.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/attachments/test_repository.py
-->

---
### Requirement: Summary prompt assembles 4 fixed sections with locale-aware headings

The summarizer's prompt builder SHALL produce a system instruction that explicitly enumerates the four required heading texts in the requested locale and forbids the model from changing heading text or order, skipping a heading, inventing facts beyond the supplied context, or wrapping the four sections in additional summary paragraphs. The user message SHALL include four labeled sections in fixed order: meeting metadata (title, counterparty / me display names), playbook (only non-empty structured fields plus `free_form_markdown` if non-empty; whole playbook absent renders the locale's `(尚未填寫)` / `(empty playbook)` placeholder), full transcript (every `transcript_chunk` ordered ascending by `started_at` formatted as `{display_name}：{text} ({HH:mm:ss})`), and chat history (slice-9 `chat_message` rows ordered ascending by `created_at`; rendered as `{me_display_name}: {content}` for user role and `Advisor: {content}` for advisor role; empty renders the locale's `(無)` / `(none)` placeholder).

The four heading texts per locale are EXACTLY:
- zh-TW: `## 重點討論`, `## 決議`, `## Action items`, `## 待解決問題`
- en: `## Key discussion points`, `## Decisions`, `## Action items`, `## Open questions`

Action items inside section 3 SHALL render as bullet items in the format `- [{owner_or_TBD}] {action}`; owner extraction is the model's responsibility based on transcript content; unknown owners default to literal `TBD`.

#### Scenario: System instruction lists the 4 zh-TW headings verbatim

- **WHEN** `build_system_instruction(locale="zh-TW")` runs
- **THEN** the returned string SHALL contain the literal substrings `## 重點討論`, `## 決議`, `## Action items`, and `## 待解決問題` AND SHALL contain a phrase forbidding the model from changing heading text or order

#### Scenario: System instruction lists the 4 en headings verbatim

- **WHEN** `build_system_instruction(locale="en")` runs
- **THEN** the returned string SHALL contain the literal substrings `## Key discussion points`, `## Decisions`, `## Action items`, and `## Open questions`

#### Scenario: User message includes meeting metadata, playbook, transcript, and chat history sections in order

- **GIVEN** a meeting with non-empty playbook, 3 transcript chunks, and 1 chat exchange
- **WHEN** `build_user_message(meeting, playbook, chunks, chat_history, locale="zh-TW")` runs
- **THEN** the returned string SHALL contain `## 會議基本資料`, `## Playbook`, `## 整場 Transcript`, and `## In-meeting Advisor 對話` in that order

#### Scenario: Empty chat_history renders the localised placeholder

- **GIVEN** a first-time-summarized meeting with zero `chat_message` rows
- **WHEN** `build_user_message(..., chat_history=[], locale="zh-TW")` runs
- **THEN** the `## In-meeting Advisor 對話` section's body SHALL be the literal `(無)`


<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: Summary generation runtime serializes per-meeting work via in-process registry

The backend SHALL provide `summarization/runtime.py` exposing `spawn_summary_task(meeting_id) -> bool` and `is_pending(meeting_id) -> bool`. The module SHALL maintain a process-scoped `dict[str, asyncio.Task]` mapping meeting_id to the in-flight summary task; access SHALL be guarded by an `asyncio.Lock` to prevent races between concurrent spawn calls. `spawn_summary_task` SHALL return `True` and create a new task when no in-flight task exists for the meeting; SHALL return `False` (no new task created) when an in-flight task is present and not done. `is_pending` SHALL return `True` iff the registry holds an unfinished task for the meeting.

The spawned task SHALL invoke `MeetingSummarizer.summarize(meeting_id)`, then `SummaryRepository.upsert(meeting_id=..., markdown=result.markdown, attachment_hash_snapshot=result.attachment_hash_snapshot)` on success. On any exception (`asyncio.TimeoutError`, `SummaryFormatError`, generic `Exception`) the task SHALL log the full traceback via `logger.exception` and SHALL NOT call `upsert`. The task's `finally` clause SHALL pop the meeting_id from the registry regardless of outcome.

Process restart loses the in-flight registry entirely; this is acceptable because the task itself dies with the process and no row was written, leaving a consistent "no summary, can regenerate" UI state.

#### Scenario: Successful generation upserts markdown + snapshot then pops registry

- **GIVEN** a registered task running `summarizer.summarize("m_x")` that returns `SummaryGenerationResult(markdown="...", attachment_hash_snapshot="h_x")`
- **WHEN** the task completes
- **THEN** the database SHALL contain a `summary` row for "m_x" whose `markdown` and `attachment_hash_snapshot` match the result AND `is_pending("m_x")` SHALL return `False`

#### Scenario: Concurrent spawn calls — second returns False without creating a task

- **GIVEN** an empty registry
- **WHEN** two coroutines call `spawn_summary_task("m_x")` simultaneously
- **THEN** exactly one call SHALL return `True` and create a task; the other call SHALL return `False`

#### Scenario: Failed generation skips upsert but still pops registry

- **GIVEN** a registered task whose `summarize` raises `asyncio.TimeoutError`
- **WHEN** the task's exception path runs
- **THEN** the database SHALL have ZERO new `summary` rows for the meeting AND `is_pending("m_x")` SHALL return `False` AND the backend log SHALL contain the traceback


<!-- @trace
source: slice-20c-multimodal-input
updated: 2026-05-17
code:
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/uv.lock
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/metadata-card.tsx
  - .env.example
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/integrations.tsx
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/tags/__init__.py
  - README.md
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/retention/job.py
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/profile.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/package.json
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/web/src/lib/stats-api.ts
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/tags/models.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/components/ui/dialog.tsx
  - CONTEXT.md
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - bun.lock
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/settings/all-sections.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/public/icons/qwen.png
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/index.css
  - packages/web/src/components/playbook-pane.tsx
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/tags/repository.py
tests:
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/conftest.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/tags/test_router.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/tags/test_models.py
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/App.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/test_config.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/attachments/test_repository.py
-->

---
### Requirement: POST /api/meetings/{id}/summary triggers regeneration with busy-aware response

The backend SHALL expose `POST /api/meetings/{meeting_id}/summary` (mounted by `summarization/router.py`) requiring the gateway-injected `X-User-Id` header. The endpoint SHALL verify ownership via `MeetingRepository.get_for_user`; non-owner / non-existent meeting SHALL return HTTP 404 with the standard flat envelope `{error_code: "meeting.not_found", message: "Meeting not found"}`. Missing `X-User-Id` SHALL return HTTP 401 with `{error_code: "auth.gateway_bypass", ...}`.

When a summary task is already in-flight for the meeting (`runtime.is_pending(meeting_id) == True`), the endpoint SHALL return HTTP 409 with `{error_code: "summary.busy", message: "A summary generation is already running for this meeting"}` and SHALL NOT spawn a second task. When no in-flight task exists, the endpoint SHALL call `runtime.spawn_summary_task(meeting_id)` and return HTTP 202 with body `{status: "pending"}`.

#### Scenario: Owner POST on idle meeting spawns task and returns 202

- **GIVEN** a meeting belonging to user `u_a` with no in-flight summary
- **WHEN** `u_a` issues `POST /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 202 with body `{"status": "pending"}` AND `runtime.is_pending(meeting_id)` SHALL return `True`

#### Scenario: POST while summary already in-flight returns 409 summary.busy

- **GIVEN** a meeting whose summary task is already in-flight
- **WHEN** the owner POSTs again
- **THEN** the response SHALL be HTTP 409 with body `{"error_code": "summary.busy", ...}` AND no second task SHALL be spawned

#### Scenario: Non-owner POST returns 404 meeting.not_found

- **GIVEN** a meeting belonging to user `u_a`
- **WHEN** user `u_b` issues `POST /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 404 with body `{"error_code": "meeting.not_found", ...}`


<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: GET /api/meetings/{id}/summary returns three states (present / pending / not_found)

The backend SHALL expose `GET /api/meetings/{meeting_id}/summary` requiring the gateway-injected `X-User-Id` header. Ownership / auth gates match the POST endpoint. The response shape SHALL be one of:

(a) Summary row exists → HTTP 200 with body `{id, meeting_id, markdown, generated_at, is_stale}` where `is_stale` is the boolean computed by `SummaryRepository.get_with_stale_flag` (see scenario 3 of the chat_message persistence requirement).

(b) Summary row absent BUT `runtime.is_pending(meeting_id) == True` → HTTP 200 with body `{status: "pending", generated_at: null}`.

(c) Summary row absent AND no in-flight task → HTTP 404 with body `{error_code: "summary.not_found", message: "No summary has been generated for this meeting"}`.

The response SHALL never embed transcript / playbook / chat_message data; clients fetch those separately if needed.

#### Scenario: Owner GET on completed meeting returns the persisted summary

- **GIVEN** a meeting belonging to user `u_a` with a persisted summary row
- **WHEN** `u_a` issues `GET /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 200 with body keys `id`, `meeting_id`, `markdown`, `generated_at`, `is_stale`

#### Scenario: Owner GET while generation is in-flight returns the pending shape

- **GIVEN** a meeting whose summary task is in-flight AND no row exists yet
- **WHEN** `u_a` issues `GET /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 200 with body `{"status": "pending", "generated_at": null}`

#### Scenario: Owner GET on never-summarized meeting returns 404 summary.not_found

- **GIVEN** a meeting with no summary row and no in-flight task
- **WHEN** `u_a` issues `GET /api/meetings/{meeting_id}/summary`
- **THEN** the response SHALL be HTTP 404 with body `{"error_code": "summary.not_found", ...}`

<!-- @trace
source: slice-10-post-meeting-summary
updated: 2026-05-11
code:
  - packages/backend/meeting_playbook/server.py
  - packages/backend/alembic/versions/0006_create_summary.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - .env.example
  - packages/backend/meeting_playbook/summarization/base.py
  - docs/agents/summarization.md
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/backend/meeting_playbook/summarization/prompts.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/summarization/__init__.py
  - packages/web/src/lib/markdown-export.ts
  - packages/web/src/locales/en.json
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/components/ui/tabs.tsx
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/hooks/use-detail-tab.ts
  - packages/web/package.json
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/detail.tsx
  - packages/web/src/lib/summary-api.ts
  - packages/backend/meeting_playbook/summarization/dependencies.py
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/web/tsconfig.json
  - bun.lock
tests:
  - packages/backend/tests/summarization/test_runtime.py
  - packages/web/src/lib/summary-api.test.ts
  - packages/web/src/lib/markdown-export.test.ts
  - packages/backend/tests/sessions/test_router_summary_spawn.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/summarization/test_dependencies.py
  - packages/backend/tests/summarization/test_vertex_summarizer.py
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/web/src/hooks/use-detail-tab.test.tsx
  - packages/backend/tests/summarization/test_repository.py
  - packages/backend/tests/summarization/test_prompts.py
  - packages/web/src/components/summary-pane.test.tsx
  - packages/backend/tests/summarization/test_router.py
  - packages/backend/tests/summarization/__init__.py
-->

---
### Requirement: Summary is_stale flag reacts to attachment set changes

`SummaryRepository.get_with_stale_flag(meeting_id) -> SummaryWithStale | None` SHALL compute `is_stale: bool` as `True` when ANY of the following hold:

1. The latest `transcript_chunk.created_at` for the meeting is later than `summary.generated_at`.
2. The latest `playbook.updated_at` for the meeting is later than `summary.generated_at`.
3. The latest `chat_message.created_at` for the meeting is later than `summary.generated_at`.
4. The current attachment-set hash for the meeting differs from `summary.attachment_hash_snapshot`. The current attachment-set hash is computed as `sha256(sorted(sha256(open(att.file_path,'rb').read()) for att in MeetingAttachmentRepository.list_for_meeting(meeting_id) if att.deleted_at IS NULL))`, expressed as a lowercase hex string. The empty-attachment set SHALL hash to the canonical empty-set hash `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`.

Legacy rows where `attachment_hash_snapshot IS NULL` SHALL be treated as if they recorded the canonical empty-set hash — so a legacy summary for a meeting with zero attachments is NOT stale on the attachment axis, but a legacy summary for a meeting with one or more current attachments IS stale.

#### Scenario: Adding a new attachment marks the summary stale

- **GIVEN** a meeting with one PDF whose summary was generated with `attachment_hash_snapshot` matching the one-PDF hash AND no transcript / playbook / chat changes since generation
- **WHEN** a second PNG attachment is uploaded AND `get_with_stale_flag(meeting_id)` runs
- **THEN** `is_stale` SHALL be `True`

#### Scenario: Deleting an attachment marks the summary stale

- **GIVEN** a meeting whose summary was generated with two attachments and snapshot hash matches that set
- **WHEN** one attachment is soft-deleted and `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `True`

#### Scenario: Replacing an attachment with byte-identical content does NOT mark stale

- **GIVEN** a meeting whose summary was generated with one PDF whose bytes hash to `h_pdf`
- **WHEN** the user deletes that attachment and uploads a different `AttachmentRef` whose file bytes are byte-identical
- **THEN** the current attachment-set hash SHALL still equal `attachment_hash_snapshot` AND `is_stale` SHALL be `False` (provided no other axis triggers)

#### Scenario: Legacy NULL snapshot row with no current attachments is NOT stale on the attachment axis

- **GIVEN** a summary row written before migration with `attachment_hash_snapshot IS NULL` AND the meeting has zero non-deleted attachments AND no other axis is newer than `generated_at`
- **WHEN** `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `False`

#### Scenario: Legacy NULL snapshot row with current attachments IS stale

- **GIVEN** a summary row written before migration with `attachment_hash_snapshot IS NULL` AND the meeting has one PDF attachment
- **WHEN** `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `True`


<!-- @trace
source: slice-20c-multimodal-input
updated: 2026-05-17
code:
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/uv.lock
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/metadata-card.tsx
  - .env.example
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/integrations.tsx
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/tags/__init__.py
  - README.md
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/retention/job.py
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/profile.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/package.json
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/web/src/lib/stats-api.ts
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/tags/models.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/components/ui/dialog.tsx
  - CONTEXT.md
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - bun.lock
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/settings/all-sections.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/public/icons/qwen.png
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/index.css
  - packages/web/src/components/playbook-pane.tsx
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/tags/repository.py
tests:
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/conftest.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/tags/test_router.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/tags/test_models.py
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/App.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/test_config.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/attachments/test_repository.py
-->

---
### Requirement: Summary pane shows a localized stale banner when attachments change

The frontend `<SummaryPane>` component at `packages/web/src/components/summary-pane.tsx` SHALL render a stale banner above the markdown body whenever the GET `/api/meetings/{id}/summary` response body has `is_stale === true`. The banner SHALL contain (a) localized text retrieved via `t("summary.stale.attachments_changed")` and (b) a button labeled via `t("summary.stale.regenerate_button")` that POSTs to `/api/meetings/{id}/summary` to trigger regeneration. The locale files `packages/web/src/locales/zh-TW.json` and `packages/web/src/locales/en.json` SHALL both contain the keys `summary.stale.attachments_changed` and `summary.stale.regenerate_button` (the `locales.test.ts` deep-equal test SHALL pass).

The banner SHALL NOT show when `is_stale === false`, and SHALL NOT show when the GET response is the pending shape (`{status: "pending", generated_at: null}`).

#### Scenario: is_stale true renders the localized banner

- **GIVEN** GET `/api/meetings/m_x/summary` returns `{id, meeting_id, markdown, generated_at, is_stale: true}` in the zh-TW locale
- **WHEN** `<SummaryPane>` renders
- **THEN** the rendered DOM SHALL contain the localized text from `summary.stale.attachments_changed` (zh-TW) AND a button whose text equals the localized text from `summary.stale.regenerate_button`

#### Scenario: is_stale false hides the banner

- **GIVEN** the GET response has `is_stale: false`
- **WHEN** `<SummaryPane>` renders
- **THEN** the rendered DOM SHALL NOT contain the localized stale banner text

#### Scenario: Pending response hides the banner

- **GIVEN** the GET response is `{status: "pending", generated_at: null}`
- **WHEN** `<SummaryPane>` renders
- **THEN** the rendered DOM SHALL NOT contain the localized stale banner text (the pending UI is rendered instead)

<!-- @trace
source: slice-20c-multimodal-input
updated: 2026-05-17
code:
  - packages/backend/alembic/versions/0016_meeting_attachment.py
  - packages/web/src/components/meetings-view-tabs.tsx
  - packages/web/src/lib/attachments-api.ts
  - packages/backend/meeting_playbook/dashboard_stats/router.py
  - packages/backend/uv.lock
  - packages/web/src/components/ui/alert.tsx
  - packages/web/src/components/metadata-card.tsx
  - .env.example
  - packages/backend/meeting_playbook/summarization/runtime.py
  - packages/web/src/lib/tus-uploader.ts
  - packages/web/src/routes/settings/integrations.tsx
  - packages/backend/meeting_playbook/tags/router.py
  - packages/web/src/components/chunk-action-menu.tsx
  - packages/backend/meeting_playbook/attachments/__init__.py
  - packages/backend/meeting_playbook/summarization/repository.py
  - packages/web/src/components/calendar/calendar-integration-panel.tsx
  - packages/web/src/components/dashboard/hour-distribution-chart.tsx
  - packages/backend/meeting_playbook/attachments/models.py
  - packages/backend/meeting_playbook/offline_ingest/runtime.py
  - packages/backend/alembic/versions/0014_recording_started_at.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/backend/meeting_playbook/sessions/models.py
  - packages/backend/meeting_playbook/offline_ingest/__init__.py
  - packages/backend/meeting_playbook/playbooks/models.py
  - packages/web/src/components/transcript-pane.tsx
  - packages/web/src/components/meetings-kanban.tsx
  - packages/web/src/components/transcript-chunk-row.tsx
  - packages/backend/meeting_playbook/attachments/router.py
  - packages/web/public/icons/google-authenticator.png
  - packages/web/src/lib/transcripts-api.ts
  - packages/web/src/routes/meetings/detail.tsx
  - packages/backend/meeting_playbook/offline_ingest/tus_protocol.py
  - packages/web/src/lib/transcript-edit-api.ts
  - packages/web/src/route-tree.tsx
  - packages/web/src/components/magicui/border-beam.tsx
  - packages/backend/meeting_playbook/config.py
  - packages/backend/meeting_playbook/attachments/multimodal_context.py
  - packages/web/src/components/attachment-dropzone.tsx
  - packages/web/src/components/dashboard/calendar-heatmap.tsx
  - packages/web/src/components/protected-shell.tsx
  - packages/web/src/lib/transcript-color-schemes.ts
  - packages/backend/alembic/versions/0012_meeting_start_not_null.py
  - packages/web/src/hooks/use-mini-player.ts
  - packages/backend/meeting_playbook/transcript_edit/__init__.py
  - packages/backend/meeting_playbook/sessions/repository.py
  - packages/web/src/components/magicui/spotlight-card.tsx
  - packages/web/src/components/meeting-audio-mini-player.tsx
  - packages/web/src/components/user-menu.tsx
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/dashboard_stats/queries.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/meetings/repository.py
  - packages/web/src/lib/tags-api.ts
  - packages/web/src/locales/en.json
  - packages/backend/meeting_playbook/tags/__init__.py
  - README.md
  - packages/web/src/components/dashboard/dashboard-body.tsx
  - packages/backend/meeting_playbook/offline_ingest/transcode.py
  - packages/web/src/components/dashboard/period-switcher.tsx
  - packages/backend/meeting_playbook/playbooks/schemas.py
  - packages/web/src/lib/session-ws.ts
  - packages/web/src/hooks/use-cluster-speaker-labels.ts
  - packages/backend/meeting_playbook/playbooks/router.py
  - packages/web/src/routes/settings/data.tsx
  - packages/backend/meeting_playbook/meetings/router.py
  - packages/backend/meeting_playbook/meetings/models.py
  - packages/backend/meeting_playbook/retention/job.py
  - packages/backend/meeting_playbook/summarization/vertex_summarizer.py
  - packages/web/src/components/summary-pane.tsx
  - packages/backend/meeting_playbook/attachments/exceptions.py
  - packages/web/src/lib/playbook-api.ts
  - packages/web/src/components/tags/tag-filter.tsx
  - packages/web/src/lib/tag-palette.ts
  - packages/web/src/routes/settings/profile.tsx
  - packages/web/src/lib/offline-ingest-api.ts
  - packages/web/package.json
  - packages/web/src/components/meeting-card.tsx
  - packages/web/src/components/speaker-color-popover.tsx
  - packages/backend/meeting_playbook/attachments/validation.py
  - packages/web/src/lib/meetings-bucket.ts
  - packages/web/src/components/dashboard/top-counterparties-chart.tsx
  - packages/web/src/lib/stats-api.ts
  - packages/backend/meeting_playbook/retention/runtime.py
  - packages/backend/meeting_playbook/audio_playback/__init__.py
  - packages/backend/meeting_playbook/playbooks/repository.py
  - packages/web/src/hooks/use-transcript-color-pref.ts
  - packages/web/src/components/tags/tag-picker.tsx
  - packages/backend/meeting_playbook/attachments/repository.py
  - packages/backend/meeting_playbook/offline_ingest/router.py
  - packages/backend/meeting_playbook/attachments/processor.py
  - packages/backend/meeting_playbook/audio/capture.py
  - packages/web/src/components/dashboard/tag-distribution-chart.tsx
  - packages/backend/meeting_playbook/dashboard_stats/__init__.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/web/src/routes/meetings/new.tsx
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/tags/models.py
  - packages/backend/meeting_playbook/speaker/finalize.py
  - packages/web/src/components/ui/dialog.tsx
  - CONTEXT.md
  - packages/web/src/lib/meetings-api.ts
  - packages/web/src/routes/settings/security.tsx
  - packages/backend/pyproject.toml
  - packages/backend/meeting_playbook/audio_playback/range_server.py
  - packages/backend/alembic/versions/0017_attachment_hash_snapshot.py
  - bun.lock
  - packages/web/src/components/magicui/gradient-card-frame.tsx
  - packages/web/src/routes/home.tsx
  - packages/web/src/components/dashboard/stat-cards.tsx
  - packages/web/src/components/settings/all-sections.tsx
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/web/public/icons/qwen.png
  - packages/backend/alembic/versions/0015_chunk_text_edited_at.py
  - packages/backend/meeting_playbook/dashboard_stats/clock.py
  - packages/web/src/components/dashboard/monthly-trend-chart.tsx
  - packages/web/src/routes/settings/voice.tsx
  - packages/web/src/components/tags/tag-chip.tsx
  - packages/backend/alembic/versions/0011_recording_source_started.py
  - packages/backend/meeting_playbook/sessions/router.py
  - packages/backend/meeting_playbook/audio_playback/wav_header.py
  - packages/web/src/components/offline-ingest/UploadDialog.tsx
  - packages/backend/meeting_playbook/summarization/models.py
  - packages/web/src/components/settings/sub-nav.tsx
  - packages/web/src/lib/meetings-calendar-utils.ts
  - packages/web/src/routes/DashboardPage.tsx
  - packages/web/src/routes/settings/tags.tsx
  - packages/backend/alembic/versions/0013_tag_system.py
  - packages/web/src/routes/meetings/calendar.tsx
  - packages/backend/meeting_playbook/summarization/router.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - packages/web/src/components/ui/button.tsx
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/audio_playback/router.py
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/meetings/schemas.py
  - packages/backend/meeting_playbook/transcript_edit/router.py
  - packages/web/src/index.css
  - packages/web/src/components/playbook-pane.tsx
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/tags/colors.py
  - packages/web/src/components/meeting-edit-form.tsx
  - packages/web/src/components/dashboard/daily-trend-chart.tsx
  - packages/web/src/components/settings/layout.tsx
  - packages/web/public/icons/google-calendar.png
  - packages/backend/meeting_playbook/tags/repository.py
tests:
  - packages/backend/tests/audio_playback/__init__.py
  - packages/backend/tests/test_alembic_summary.py
  - packages/web/src/components/offline-ingest/UploadDialog.test.tsx
  - packages/web/src/lib/tus-uploader.test.ts
  - packages/backend/tests/integration/test_voice_enrollment_e2e.py
  - packages/backend/tests/retention/test_job.py
  - packages/web/src/components/attachment-dropzone.test.tsx
  - packages/web/src/components/tags/tag-picker.test.tsx
  - packages/web/src/routes/meetings/detail.test.tsx
  - packages/backend/tests/tags/test_repository.py
  - packages/backend/tests/conftest.py
  - packages/web/src/components/transcript-chunk-row.test.tsx
  - packages/backend/tests/audio_playback/test_router.py
  - packages/backend/tests/test_alembic_meeting_attachment.py
  - packages/backend/tests/attachments/test_multimodal_context.py
  - packages/backend/tests/dashboard_stats/__init__.py
  - packages/backend/tests/meetings/test_repository.py
  - packages/backend/tests/transcript_edit/test_router.py
  - packages/web/src/components/meeting-card.test.tsx
  - packages/web/src/components/tags/tag-filter.test.tsx
  - packages/backend/tests/test_alembic_meeting.py
  - packages/web/src/components/chunk-action-menu.test.tsx
  - packages/backend/tests/tags/test_router.py
  - packages/backend/tests/integration/test_single_channel_e2e.py
  - packages/backend/tests/attachments/test_processor.py
  - packages/backend/tests/offline_ingest/test_pipeline.py
  - packages/backend/tests/test_alembic_transcript_chunk_text_edited_at.py
  - packages/backend/tests/tags/test_models.py
  - packages/web/src/routes/home.test.tsx
  - packages/web/src/hooks/use-cluster-speaker-labels.test.tsx
  - packages/web/src/routes/meetings/calendar.test.tsx
  - packages/backend/tests/integration/test_audio_playback_e2e.py
  - packages/web/src/lib/stats-api.test.ts
  - packages/backend/tests/tags/__init__.py
  - packages/web/src/lib/transcript-color-schemes.test.ts
  - packages/backend/tests/meetings/test_list_filters.py
  - packages/backend/tests/transcript_edit/__init__.py
  - packages/web/src/routes/meetings/list.test.tsx
  - packages/backend/tests/meetings/test_validation.py
  - packages/backend/tests/audio_playback/test_range_server.py
  - packages/web/src/routes/settings/tags.test.tsx
  - packages/backend/tests/meetings/test_integration_round_trip.py
  - packages/backend/tests/audio_playback/test_wav_header.py
  - packages/backend/tests/test_alembic_meeting_scheduled_not_null.py
  - packages/web/src/App.test.tsx
  - packages/backend/tests/test_alembic_playbook.py
  - packages/backend/tests/rerun/test_runtime.py
  - packages/backend/tests/meetings/test_tags_integration.py
  - packages/web/src/components/meetings-kanban.test.tsx
  - packages/backend/tests/integration/test_playbook_with_attachments.py
  - packages/web/src/lib/tags-api.test.ts
  - packages/backend/tests/offline_ingest/test_tus_protocol.py
  - packages/backend/tests/rerun/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_started_at.py
  - packages/web/src/lib/meetings-calendar-utils.test.ts
  - packages/backend/tests/integration/test_summary_with_attachments.py
  - packages/backend/tests/dashboard_stats/test_dashboard_stats.py
  - packages/backend/tests/offline_ingest/test_duration.py
  - packages/backend/tests/test_config.py
  - packages/backend/tests/offline_ingest/test_transcode.py
  - packages/backend/tests/offline_ingest/__init__.py
  - packages/web/src/hooks/use-transcript-color-pref.test.tsx
  - packages/web/src/hooks/use-mini-player.test.tsx
  - packages/backend/tests/playbook_generation/test_generator_multimodal.py
  - packages/backend/tests/attachments/test_validation.py
  - packages/web/src/lib/attachments-api.test.ts
  - packages/backend/tests/tags/test_palette_parity.py
  - packages/web/src/routes/meetings/new.test.tsx
  - packages/backend/tests/meetings/test_get_runtime_flags.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/backend/tests/offline_ingest/test_progress_endpoint.py
  - packages/backend/tests/speaker/fixtures/compare_diarization.md
  - packages/backend/tests/test_alembic_meeting_scheduled.py
  - packages/backend/tests/meetings/test_endpoints.py
  - packages/web/src/lib/meetings-api.test.ts
  - packages/web/src/components/meeting-edit-form.test.tsx
  - packages/web/src/lib/i18n-plural.test.ts
  - packages/web/src/routes/routes-i18n.test.tsx
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/web/src/components/protected-shell.test.tsx
  - packages/backend/tests/test_alembic_tag_system.py
  - packages/web/src/components/meeting-prev-next-nav.test.tsx
  - packages/web/src/lib/offline-ingest-api.test.ts
  - packages/backend/tests/integration/test_offline_ingest_e2e.py
  - packages/web/src/lib/meetings-bucket.test.ts
  - packages/backend/tests/summarization/test_summarizer_multimodal.py
  - packages/web/src/components/speaker-color-popover.test.tsx
  - packages/web/src/lib/tag-palette.test.ts
  - packages/web/src/components/meeting-audio-mini-player.test.tsx
  - packages/web/src/components/tags/tag-chip.test.tsx
  - packages/web/src/routes/meetings/tag-filter-roundtrip.test.tsx
  - packages/backend/tests/attachments/test_endpoints.py
  - packages/backend/tests/test_alembic_recording_source_and_started_at.py
  - packages/backend/tests/attachments/__init__.py
  - packages/backend/tests/attachments/test_repository.py
-->