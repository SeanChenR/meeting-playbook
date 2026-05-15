# transcript-edit Specification

## Purpose

TBD - created by archiving change 'slice-16-transcript-edit-and-playback'. Update Purpose after archive.

## Requirements

### Requirement: PATCH /api/meetings/{id}/transcript_chunks/{chunk_id} updates only the text field

The backend SHALL expose `PATCH /api/meetings/{meeting_id}/transcript_chunks/{chunk_id}` accepting a JSON body. The endpoint SHALL accept only the field `text` (a string with `1 <= len(text) <= 10000` characters). Any other field present in the body (including but not limited to `speaker`, `started_at`, `ended_at`, `asr_provider_used`, `confidence`) SHALL cause HTTP 422 with `error_code = "transcript_edit.immutable_field"` and the response body SHALL list the rejected field names. A missing or empty `text` field SHALL cause HTTP 422 with `error_code = "transcript_edit.invalid_text"`.

On a valid request the endpoint SHALL update the `transcript_chunk` row's `text` column to the supplied value and set `text_edited_at = now()`. The response SHALL be HTTP 200 with body `{"id": ..., "text": ..., "text_edited_at": "<iso8601>"}`. The endpoint SHALL reject requests where the chunk's `meeting_id` does not match the path `meeting_id` with HTTP 404 `transcript_edit.chunk_not_found`, and reject requests from a non-owner with HTTP 403 `transcript_edit.forbidden`.

#### Scenario: Valid text update succeeds and stamps text_edited_at

- **GIVEN** an authenticated owner of meeting `m_a` with a transcript chunk `c_1` whose `text = "原始文字"` and `text_edited_at IS NULL`
- **WHEN** the owner sends `PATCH /api/meetings/m_a/transcript_chunks/c_1` with body `{"text": "修正後的文字"}`
- **THEN** the response SHALL be HTTP 200 with `text = "修正後的文字"` and a non-null `text_edited_at`; the `transcript_chunk` row in the DB SHALL have `text = "修正後的文字"` and `text_edited_at` populated with the server time

#### Scenario: Attempting to edit speaker is rejected

- **GIVEN** an authenticated owner of meeting `m_a` with chunk `c_1`
- **WHEN** the owner sends `PATCH /api/meetings/m_a/transcript_chunks/c_1` with body `{"text": "x", "speaker": "counterparty"}`
- **THEN** the response SHALL be HTTP 422 with `error_code = "transcript_edit.immutable_field"` and the response body SHALL list `"speaker"` among the rejected fields; the row's `speaker` SHALL be unchanged; the row's `text` SHALL be unchanged

#### Scenario: Empty text is rejected

- **GIVEN** an authenticated owner of meeting `m_a` with chunk `c_1` whose `text = "abc"`
- **WHEN** the owner sends `PATCH /api/meetings/m_a/transcript_chunks/c_1` with body `{"text": ""}`
- **THEN** the response SHALL be HTTP 422 with `error_code = "transcript_edit.invalid_text"`; the row SHALL be unchanged

#### Scenario: Text over 10000 characters is rejected

- **GIVEN** an authenticated owner of meeting `m_a` with chunk `c_1`
- **WHEN** the owner sends `PATCH /api/meetings/m_a/transcript_chunks/c_1` with body whose `text` length is 10001
- **THEN** the response SHALL be HTTP 422 with `error_code = "transcript_edit.invalid_text"`; the row SHALL be unchanged

#### Scenario: Non-owner cannot edit another user's chunk

- **GIVEN** user `u_a` owns meeting `m_a` containing chunk `c_1`, and user `u_b` is authenticated
- **WHEN** `u_b` sends `PATCH /api/meetings/m_a/transcript_chunks/c_1` with body `{"text": "x"}`
- **THEN** the response SHALL be HTTP 403 with `error_code = "transcript_edit.forbidden"`; the row SHALL be unchanged

#### Scenario: Chunk belonging to a different meeting is not found

- **GIVEN** an authenticated owner of both meeting `m_a` and meeting `m_b`, where chunk `c_1` belongs to `m_b`
- **WHEN** the owner sends `PATCH /api/meetings/m_a/transcript_chunks/c_1` with body `{"text": "x"}`
- **THEN** the response SHALL be HTTP 404 with `error_code = "transcript_edit.chunk_not_found"`; chunk `c_1`'s row SHALL be unchanged


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
### Requirement: TranscriptChunkRow exposes inline edit mode for the chunk text

The `<TranscriptChunkRow>` component in `packages/web/src/components/transcript-chunk-row.tsx` SHALL render the chunk text together with a **persistently-visible** ✎ icon button (the `<ChunkActionMenu>` trigger) at the row's trailing edge. The icon SHALL NOT depend on hover for visibility. Clicking the ✎ icon SHALL open `<ChunkActionMenu>` whose "Edit text" item SHALL transition the row to inline-edit mode rendering a `<textarea>` pre-filled with the current `text` and two buttons labeled Save and Cancel. The Cancel button SHALL revert the row to read mode with the original `text` unchanged. The Save button SHALL POST the new text via `PATCH /api/meetings/{id}/transcript_chunks/{chunk_id}` and, on HTTP 200, SHALL replace the displayed `text` with the response's `text` and exit edit mode. On HTTP 422 with `error_code` in (`transcript_edit.invalid_text`, `transcript_edit.immutable_field`) the row SHALL remain in edit mode and surface the localized error message; the Save button SHALL re-enable after the error so the user can retry.

#### Scenario: Cancel restores the original text without calling the API

- **GIVEN** a chunk row showing `text = "原始"` and the user clicks ✎
- **WHEN** the user types `"修改後"` then clicks Cancel
- **THEN** no PATCH request SHALL be sent; the row SHALL exit edit mode and display `"原始"`

#### Scenario: Save success updates the row and exits edit mode

- **GIVEN** a chunk row in edit mode with the textarea containing `"修改後"`
- **WHEN** the user clicks Save and the API returns HTTP 200 with `text = "修改後"`
- **THEN** the row SHALL exit edit mode; the row SHALL display `"修改後"`; the ✎ icon SHALL remain visible on hover

#### Scenario: Save failure with localized error keeps the row in edit mode

- **GIVEN** a chunk row in edit mode and the API returns HTTP 422 with `error_code = "transcript_edit.invalid_text"`
- **WHEN** the response arrives
- **THEN** the row SHALL remain in edit mode; the textarea content SHALL be preserved; a localized error message SHALL appear (zh-TW: `"文字長度需介於 1 至 10000 字元"`; en: `"Text must be between 1 and 10000 characters"`); the Save button SHALL re-enable


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
### Requirement: TranscriptColorScheme palettes and per-cluster overrides drive cluster colour rendering

The frontend SHALL define a fixed set of cluster colour schemes identified by the string union `"default" | "vivid" | "pastel" | "high-contrast" | "grayscale"`. Each scheme SHALL provide a 6-entry hue palette (for chromatic schemes) or a 6-entry lightness ladder (for `grayscale`). The `default` scheme SHALL use the hue array `[300, 150, 30, 240, 90, 0]` so existing transcripts render identically to the pre-customisation behaviour. The scheme set SHALL be a compile-time constant; runtime addition or modification of schemes SHALL NOT be supported.

A user preference SHALL be persisted in `localStorage` under the key `meeting-playbook:transcript-color-pref` with the schema `{ "scheme": <scheme id>, "overrides": { "<cluster index>": "<oklch() or hex colour string>" } }`. Loading SHALL be fail-soft: invalid JSON, an unknown scheme id, a non-object `overrides` value, or any override value that is not a recognised colour string SHALL cause the resolver to fall back to `{ "scheme": "default", "overrides": {} }` without throwing.

The pure resolver `_resolveClusterColor(speaker, pref) -> { background, accent }` SHALL apply this precedence:

1. If `speaker` matches `^speaker_cluster_(\d+)$` and `pref.overrides[N]` is present, the override colour SHALL drive both `accent` and the `background` tint expression for that cluster, regardless of the active scheme.
2. Otherwise the cluster colour SHALL be derived from the active scheme's palette entry at index `(N - 1) % 6`.
3. If `speaker === "me"` or `speaker === "counterparty"`, the resolver SHALL ignore both `scheme` and `overrides` and return the existing semantic colours sourced from the project design system (`var(--color-me)` / `var(--color-them)` and their soft variants). The customisation surface SHALL NOT mutate `me` or `counterparty` colours.
4. If `speaker` matches `speaker_cluster_unknown`, the resolver SHALL return the existing muted colour pair and SHALL ignore `overrides`.

The `transcript-pane.tsx` component SHALL render chunk backgrounds and speaker accent colours exclusively through `_resolveClusterColor`; it SHALL NOT contain a private hue constant.

#### Scenario: Default scheme reproduces the existing 6-hue palette

- **GIVEN** `pref = { scheme: "default", overrides: {} }`
- **WHEN** `_resolveClusterColor("speaker_cluster_1", pref)` and `_resolveClusterColor("speaker_cluster_2", pref)` are evaluated
- **THEN** the resolver SHALL return an `accent` derived from hue `300` for cluster 1 and hue `150` for cluster 2, matching the pre-customisation rendering bit-for-bit (same `oklch()` expression as the previous inline `_CLUSTER_HUES` constant)

#### Scenario: Per-cluster override takes precedence over the active scheme

- **GIVEN** `pref = { scheme: "vivid", overrides: { "3": "oklch(0.65 0.20 200)" } }`
- **WHEN** `_resolveClusterColor("speaker_cluster_3", pref)` is evaluated
- **THEN** the resolver SHALL return `accent` and `background` derived from `oklch(0.65 0.20 200)` (the override), NOT from the `vivid` scheme's hue at index `2`

#### Scenario: Grayscale scheme produces achromatic colours

- **GIVEN** `pref = { scheme: "grayscale", overrides: {} }`
- **WHEN** `_resolveClusterColor("speaker_cluster_2", pref)` is evaluated
- **THEN** the returned `accent` SHALL be of the form `oklch(<L> 0 0)` (zero chroma) and SHALL NOT include any hue component

#### Scenario: `me` and `counterparty` are not customisable

- **GIVEN** `pref = { scheme: "grayscale", overrides: { "1": "#ff0000" } }`
- **WHEN** `_resolveClusterColor("me", pref)` and `_resolveClusterColor("counterparty", pref)` are evaluated
- **THEN** the resolver SHALL return the existing semantic accents (`var(--color-me)` for `me`, `var(--color-them)` for `counterparty`); the scheme and overrides SHALL NOT influence the result

#### Scenario: Corrupt localStorage payload falls back to defaults without throwing

- **GIVEN** `localStorage["meeting-playbook:transcript-color-pref"] = "{not-valid-json"`
- **WHEN** the `useTranscriptColorPref` hook initialises
- **THEN** the resolved pref SHALL equal `{ scheme: "default", overrides: {} }`; no exception SHALL propagate to the React tree; the next call to `setScheme(...)` SHALL succeed and write a valid payload


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
### Requirement: SpeakerColorPopover provides inline scheme and override controls

The frontend SHALL render a `<SpeakerColorPopover>` component anchored inline to a speaker name in the transcript. The popover SHALL open exclusively from `<ChunkActionMenu>`'s "Edit color" action (the menu's parent already gates non-cluster speakers out). The component SHALL NOT attach `contextmenu` or long-press handlers, and SHALL NOT be triggerable by right-click. The popover SHALL NOT be rendered as a separate full-screen modal.

The popover content SHALL include:

1. A scheme picker showing all five scheme ids (`default`, `vivid`, `pastel`, `high-contrast`, `grayscale`) as selectable controls labelled via i18n keys `transcript.color.scheme.<id>`. Selecting a scheme SHALL update `pref.scheme` in `localStorage` immediately.
2. A swatch grid for the targeted cluster `N` containing the six hues (or six lightness values for the `grayscale` scheme) derived from the currently active scheme. Selecting any swatch SHALL set `pref.overrides[N]` to the **hue number** (0–360 for non-grayscale schemes) or the **lightness index** for grayscale. The popover SHALL NOT include a custom hex / oklch color picker.
3. A control labelled via i18n key `transcript.color.resetToScheme` that, when activated, SHALL remove the entry `pref.overrides[N]`, causing the cluster to fall back to the active scheme colour.

The component SHALL render only when its parent (`<ChunkActionMenu>`) determines the chunk's speaker matches `/^speaker_cluster_(\d+)$/`; `me`, `counterparty`, and `speaker_cluster_unknown` never instantiate this component.

#### Scenario: Right-click on a cluster speaker opens the popover

- **GIVEN** a transcript row whose speaker is `speaker_cluster_2` rendered with the user's current preference
- **WHEN** the user dispatches a `contextmenu` event on that speaker name
- **THEN** the default browser context menu SHALL be suppressed; `<SpeakerColorPopover>` SHALL appear anchored to that speaker name; the popover SHALL display the five scheme options and a swatch grid for cluster `2`

#### Scenario: Selecting a swatch persists an override and updates rendering

- **GIVEN** the popover for `speaker_cluster_3` is open with `pref = { scheme: "default", overrides: {} }`
- **WHEN** the user clicks a swatch corresponding to the colour `oklch(0.62 0.18 210)`
- **THEN** `localStorage["meeting-playbook:transcript-color-pref"]` SHALL be updated to a payload whose `overrides["3"] === "oklch(0.62 0.18 210)"`; all transcript rows for `speaker_cluster_3` SHALL re-render using that colour without a page reload

#### Scenario: Reset removes the override for that cluster only

- **GIVEN** `pref = { scheme: "vivid", overrides: { "1": "#ff0000", "2": "#00ff00" } }` and the popover for cluster `2` is open
- **WHEN** the user activates the "Reset to scheme color" control
- **THEN** `pref.overrides` SHALL equal `{ "1": "#ff0000" }`; cluster `2` SHALL render using the `vivid` scheme's hue at index `1`; cluster `1`'s override SHALL be preserved

#### Scenario: Popover is not available for `me` and `counterparty`

- **GIVEN** a transcript row whose speaker is `me` (and another whose speaker is `counterparty`)
- **WHEN** the user attempts to open the chunk action menu
- **THEN** no `<SpeakerColorPopover>` SHALL be rendered for those rows; `<ChunkActionMenu>` SHALL omit the "Edit color" item entirely; `localStorage` SHALL NOT be modified by these interactions


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
### Requirement: ChunkActionMenu surfaces per-chunk actions in a single dropdown

The frontend SHALL provide a `<ChunkActionMenu>` component anchored to the ✎ icon at the end of each `<TranscriptChunkRow>`. The menu SHALL be opened by **click** on the ✎ icon (NOT by hover, NOT by right-click / contextmenu). The menu SHALL close on Escape, on click outside, or on selecting a menu item.

The menu SHALL render the following action items in this order:

1. **Play this chunk** — always present. When the resolved recording's `deleted_at IS NULL`, clicking SHALL call `miniPlayerStore.seekToChunk(chunkId)`. When `deleted_at IS NOT NULL`, the item SHALL be disabled with the localized "錄音已過 30 天保留期" / "Recording exceeded the 30-day retention window" tooltip / aria-label (audio-playback capability covers this scenario).
2. **Edit text** — always present. Clicking SHALL set the row to inline-edit mode (see the TranscriptChunkRow requirement above).
3. **Edit color** — rendered ONLY when the chunk's speaker matches the regex `/^speaker_cluster_(\d+)$/` (cluster speakers only, excluding `speaker_cluster_unknown`). Clicking SHALL open `<SpeakerColorPopover>` for that cluster.
4. **Rename speaker** — rendered ONLY when the chunk's speaker matches the regex `/^speaker_cluster_(\d+)$/` (cluster speakers only). Clicking SHALL replace the row's speaker name with an inline `<input>` (autofocus + select-all) for entering a new label.

For speakers `me`, `counterparty`, and `speaker_cluster_unknown`, the menu SHALL render only the "Play this chunk" and "Edit text" items; "Edit color" and "Rename speaker" SHALL NOT be in the DOM at all (DOM-absent, not just hidden).

#### Scenario: Clicking the ✎ icon on a cluster speaker chunk opens a 4-item menu

- **GIVEN** a `<TranscriptChunkRow>` whose chunk has `speaker = "speaker_cluster_2"` and whose resolved recording's `deleted_at IS NULL`
- **WHEN** the user clicks the ✎ icon
- **THEN** `<ChunkActionMenu>` SHALL render and expose four menu items in order: Play this chunk, Edit text, Edit color, Rename speaker; the Play item SHALL be enabled

#### Scenario: Clicking the ✎ icon on a me speaker chunk opens a 2-item menu

- **GIVEN** a `<TranscriptChunkRow>` whose chunk has `speaker = "me"`
- **WHEN** the user clicks the ✎ icon
- **THEN** `<ChunkActionMenu>` SHALL render only two menu items in order: Play this chunk, Edit text; Edit color and Rename speaker SHALL NOT appear in the DOM

#### Scenario: Retention-expired recording disables only the play item

- **GIVEN** a `<TranscriptChunkRow>` whose resolved recording has `deleted_at IS NOT NULL`
- **WHEN** the user clicks the ✎ icon
- **THEN** the menu SHALL render with the Play item disabled (with localized tooltip / aria-label); Edit text and (for cluster speakers) Edit color / Rename speaker SHALL remain enabled


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
### Requirement: Cluster speaker label override is persisted in localStorage per meeting

The frontend SHALL provide a `useClusterSpeakerLabels(meetingId)` hook backed by `localStorage["meeting-playbook:speaker-labels"]`. The localStorage value SHALL be JSON of shape `Record<meetingId, Record<clusterN, label>>` where `clusterN` is a 1-indexed integer and `label` is a non-empty trimmed string of length 1 to 50 characters. The hook SHALL expose `{ labels: Record<number, string>, setLabel(clusterN: number, label: string): void, resetLabel(clusterN: number): void }`. Invalid labels (empty after trim, longer than 50 characters, non-string) SHALL be fail-soft rejected by `setLabel` without writing.

The transcript pane SHALL render the chunk speaker name by resolving `labels[clusterN]` first; when absent, it SHALL fall back to the existing localized "與會者 N" / "Participant N" template. The override SHALL apply only to chunks whose speaker matches `/^speaker_cluster_(\d+)$/`; chunks with speaker `me`, `counterparty`, or `speaker_cluster_unknown` SHALL NOT consult the label override (their display name uses the meeting's `me_display_name` / `counterparty_display_name` / domain-glossary fallback as before).

The rename UI SHALL live inside `<ChunkActionMenu>`'s "Rename speaker" action. Clicking the action SHALL replace the row's speaker name with an `<input>` (autofocus + select all); pressing Enter SHALL call `setLabel(clusterN, value.trim())` and exit rename mode; pressing Escape SHALL abort and exit rename mode without writing.

#### Scenario: Rename writes to localStorage and updates all chunks of that cluster

- **GIVEN** the transcript contains three chunks with `speaker = "speaker_cluster_2"` rendered as "與會者 2"
- **WHEN** the user opens the ✎ menu on one of those chunks, clicks "Rename speaker", types "Alice", and presses Enter
- **THEN** all three chunks SHALL re-render with the speaker name "Alice"; `localStorage["meeting-playbook:speaker-labels"]` SHALL contain `{ "<meetingId>": { "2": "Alice" } }`

#### Scenario: Invalid label is fail-soft rejected

- **GIVEN** the user is in rename mode for cluster 1 of meeting `m_x`
- **WHEN** the user submits the empty string
- **THEN** `setLabel("1", "")` SHALL return without writing; `localStorage` SHALL NOT contain an entry for cluster 1 of `m_x`; the row SHALL stay in rename mode so the user can correct

#### Scenario: Rename is unavailable for me / counterparty / unknown speakers

- **GIVEN** a chunk with `speaker = "me"`
- **WHEN** the user opens the ✎ menu
- **THEN** the "Rename speaker" item SHALL NOT be present in the menu DOM


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
### Requirement: TranscriptColorPref stores cluster overrides as hue numbers, not full color strings

The `TranscriptColorPref.overrides` field in `packages/web/src/lib/transcript-color-schemes.ts` SHALL have shape `Record<number /*clusterN*/, number /*hue or lightness encoding*/>`. For non-grayscale schemes, the override value SHALL be a hue in `[0, 360)`. For the `grayscale` scheme, overrides SHALL NOT be stored (the popover under grayscale SHALL hide the swatch grid and offer only scheme selection + reset). The resolver `_resolveClusterColor(speaker, pref)` SHALL compute the override's resulting accent + background by feeding the hue into the active scheme's `accentL/accentC/bgL/bgC` constants, guaranteeing the chunk background tint stays light enough to read the speaker name accent on top.

`parseTranscriptColorPref(raw)` SHALL validate each override entry: keys SHALL be positive integers; values SHALL be finite numbers in `[0, 360)`. Entries failing either constraint SHALL be silently dropped (fail-soft) and the rest of the pref SHALL be retained.

#### Scenario: Hue override produces light background contrast

- **GIVEN** `pref = { scheme: "default", overrides: { 2: 200 } }` and a chunk with `speaker = "speaker_cluster_2"`
- **WHEN** the resolver runs
- **THEN** the returned `accent` SHALL be `oklch(<scheme.accentL> <scheme.accentC> 200)` and `background` SHALL be `color-mix(in oklch, oklch(<scheme.bgL> <scheme.bgC> 200) calc(var(--them-tint-alpha) * 1000%), transparent)`; the lightness gap between accent and background SHALL be the same as a no-override cluster of hue 200

#### Scenario: Legacy string overrides are dropped on parse

- **GIVEN** `raw = '{"scheme":"default","overrides":{"2":"oklch(0.55 0.18 150)"}}'`
- **WHEN** `parseTranscriptColorPref(raw)` runs
- **THEN** the result SHALL be `{ scheme: "default", overrides: {} }` (string value rejected as not-a-number); the scheme field SHALL survive

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