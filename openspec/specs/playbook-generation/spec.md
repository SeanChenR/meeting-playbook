# playbook-generation Specification

## Purpose

TBD - created by archiving change 'slice-05-calendar-llm-playbook'. Update Purpose after archive.

## Requirements

### Requirement: Generator produces all seven playbook fields with non-empty content for any Calendar event input

The `PlaybookGenerator` capability SHALL accept a Calendar event record (title, attendees, start time, end time, optional description, organizer) and produce a playbook draft containing all seven content fields defined by `playbook-management`: `free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`. Every structured field in the returned draft MUST be a non-empty string. The free-form markdown body MUST contain at least three lines of markdown content.

#### Scenario: Rich event input produces seven non-empty fields

- **GIVEN** a Calendar event with title, two attendees, a description longer than 200 characters, and a one-hour duration
- **WHEN** the generator processes that event
- **THEN** the returned draft SHALL contain non-empty strings for `free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, and `red_lines`

#### Scenario: Sparse event input still produces seven non-empty fields via fallback

- **GIVEN** a Calendar event with only a title (no description, no attendees other than the user, no organizer name)
- **WHEN** the generator processes that event
- **THEN** the returned draft SHALL still contain non-empty strings for all six structured fields and a `free_form_markdown` of at least three lines

##### Example: minimum non-empty contract per field

| Field | Minimum content |
| ----- | --------------- |
| `free_form_markdown` | at least three lines (each line ≥ 1 non-whitespace character) |
| `objective` | non-empty string after trimming whitespace |
| `counterparty_profile` | non-empty string after trimming whitespace |
| `anticipated_topics` | non-empty string after trimming whitespace |
| `anticipated_objections` | non-empty string after trimming whitespace |
| `talking_points` | non-empty string after trimming whitespace |
| `red_lines` | non-empty string after trimming whitespace |


<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->

---
### Requirement: Generator uses Vertex AI Gemini 2.5 Pro through the official SDK

The generator SHALL invoke the Gemini 2.5 Pro model on Vertex AI through the `google-genai` SDK with structured-output mode (response schema enforcing the seven string fields). When `attachment_refs` is empty, the SDK call SHALL use a single text `contents` argument. When `attachment_refs` is non-empty, the SDK call SHALL use a list of `types.Part` objects assembled by `MultimodalContextBuilder`. The generator SHALL NOT call any non-Vertex-AI provider, and SHALL NOT bypass the SDK by issuing raw HTTP requests. Authentication MUST flow through Application Default Credentials so deployments can swap service accounts without code changes.

#### Scenario: Non-Vertex provider is forbidden

- **WHEN** the generator code is reviewed
- **THEN** there MUST be no import of, nor HTTP call to, providers other than Vertex AI's Gemini family

##### Example: forbidden imports and HTTP calls that MUST fail review

```python
# FORBIDDEN — direct OpenAI SDK import
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
client.chat.completions.create(model="gpt-4o", messages=[...])

# FORBIDDEN — Anthropic SDK import
from anthropic import Anthropic
Anthropic().messages.create(model="claude-3-5-sonnet", messages=[...])

# FORBIDDEN — raw HTTP to a non-Vertex endpoint
httpx.post("https://api.openai.com/v1/chat/completions", json={...})

# FORBIDDEN — raw HTTP that bypasses the SDK even if the host is Vertex
httpx.post(
    "https://us-central1-aiplatform.googleapis.com/v1/projects/.../models/gemini-2.5-pro:generateContent",
    json={...},
)

# ALLOWED — the official google-genai SDK against Vertex AI
from google import genai
client = genai.Client(vertexai=True, project=..., location=...)
client.models.generate_content(model="gemini-2.5-pro", contents=parts)
```

#### Scenario: Structured-output schema is enforced

- **WHEN** the generator builds its request to Gemini 2.5 Pro
- **THEN** the request SHALL include a JSON response schema with exactly the seven string keys defined by `playbook-management`

#### Scenario: Multimodal call uses Part objects rather than raw strings

- **GIVEN** a non-empty `attachment_refs`
- **WHEN** the generator invokes `client.models.generate_content(...)`
- **THEN** the `contents` keyword argument SHALL be a list of `google.genai.types.Part` instances, not a single string


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
### Requirement: Generator surfaces localizable failure codes for upstream and parsing errors

When generation cannot succeed, the generator SHALL raise an exception that the calling router maps into one of the following error codes, each resolved by the frontend through the i18n key registry:

- `playbook.generation_timeout` — the Vertex AI call exceeded a 60-second deadline. HTTP 504.
- `playbook.generation_failed` — the Vertex AI call returned an error response, or the returned JSON could not be validated against the seven-field schema. HTTP 502.

These codes SHALL be the only generator-domain failure codes; new failure modes require a separate change.

#### Scenario: Upstream timeout surfaces playbook.generation_timeout

- **GIVEN** the Vertex AI request takes longer than 60 seconds
- **WHEN** the generator is invoked
- **THEN** the generator SHALL raise an error that the router maps to HTTP 504 with `error_code: playbook.generation_timeout`

#### Scenario: Schema validation failure surfaces playbook.generation_failed

- **GIVEN** the Vertex AI response is HTTP 200 but the body cannot be parsed as JSON conforming to the seven-string-fields schema
- **WHEN** the generator processes that response
- **THEN** the generator SHALL raise an error that the router maps to HTTP 502 with `error_code: playbook.generation_failed`


<!-- @trace
source: slice-05-calendar-llm-playbook
updated: 2026-05-09
code:
  - packages/backend/meeting_playbook/calendar/__init__.py
  - packages/backend/meeting_playbook/calendar/schemas.py
  - docs/adr/0027-calendar-scope-link.md
  - packages/web/src/lib/calendar-api.ts
  - docs/agents/calendar.md
  - packages/web/src/routes/calendar/upcoming.tsx
  - packages/backend/meeting_playbook/calendar/client.py
  - packages/backend/meeting_playbook/meetings/dependencies.py
  - packages/backend/uv.lock
  - docs/agents/playbook-generation.md
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/routes/meetings/list.tsx
  - packages/backend/pyproject.toml
  - .env.example
  - packages/backend/meeting_playbook/server.py
  - packages/backend/meeting_playbook/calendar/token_store.py
  - packages/web/src/locales/zh-TW.json
  - packages/backend/meeting_playbook/playbook_generation/__init__.py
  - packages/auth/src/server.ts
  - packages/backend/meeting_playbook/calendar/identity.py
  - packages/backend/meeting_playbook/calendar/router.py
  - packages/backend/meeting_playbook/playbook_generation/generator.py
  - packages/backend/meeting_playbook/playbook_generation/prompts.py
  - packages/web/src/locales/en.json
  - packages/web/src/route-tree.tsx
  - packages/auth/src/internal.ts
  - packages/backend/meeting_playbook/calendar/dependencies.py
tests:
  - packages/web/src/routes/calendar/upcoming.test.tsx
  - packages/backend/tests/playbook_generation/fixtures/en.json
  - packages/backend/tests/playbook_generation/fixtures/zh.json
  - packages/backend/tests/calendar/__init__.py
  - packages/backend/tests/calendar/test_endpoints.py
  - packages/web/src/locales/locales.test.ts
  - packages/backend/tests/playbook_generation/fixtures/rich.json
  - packages/backend/tests/playbook_generation/fixtures/mixed.json
  - packages/auth/src/__tests__/gateway-user-headers.test.ts
  - packages/backend/tests/calendar/test_classify_viewer_role.py
  - packages/backend/tests/playbook_generation/test_generator.py
  - packages/auth/src/__tests__/calendar-token-internal.test.ts
  - packages/auth/src/__tests__/calendar-link.test.ts
  - packages/backend/tests/calendar/test_pick_counterparty.py
  - packages/web/src/lib/calendar-api.mutations.test.tsx
  - packages/backend/tests/calendar/test_client.py
  - packages/backend/tests/playbook_generation/fixtures/long.json
  - packages/backend/tests/playbook_generation/fixtures/sparse.json
  - packages/backend/tests/playbook_generation/__init__.py
  - packages/web/src/lib/calendar-api.queries.test.ts
-->

---
### Requirement: Generator output is suitable for direct upsert through the existing playbook repository

The generator SHALL emit a draft whose shape exactly matches the upsert payload accepted by `PlaybookRepository.upsert_for_meeting` defined in `playbook-management`: a dictionary with the seven existing string keys (`free_form_markdown`, `objective`, `counterparty_profile`, `anticipated_topics`, `anticipated_objections`, `talking_points`, `red_lines`) AND the new key `attachment_hash_snapshot` (string, hex SHA-256). Callers MUST be able to pass the draft straight to the repository without remapping or filtering.

The `PlaybookRepository.upsert_for_meeting` method SHALL accept the new `attachment_hash_snapshot` key and persist it into the `playbook.attachment_hash_snapshot` column. Existing rows whose column value is `NULL` SHALL continue to be readable and editable; the repository SHALL treat `NULL` as "snapshot unknown" rather than as an error.

#### Scenario: Draft is shape-compatible with the upsert payload

- **WHEN** the generator returns a draft for any input event
- **THEN** the draft's keys SHALL be exactly the seven content-field names defined by `playbook-management` plus `attachment_hash_snapshot`, and each value SHALL be a string

#### Scenario: Repository upsert succeeds without intermediate transformation

- **GIVEN** a generator output `draft` and a meeting `m_target`
- **WHEN** `PlaybookRepository.upsert_for_meeting(meeting_id="m_target", payload=draft)` is invoked
- **THEN** the upsert SHALL succeed and persist all seven content fields verbatim AND SHALL persist `attachment_hash_snapshot` into the new column

#### Scenario: Legacy rows with NULL attachment_hash_snapshot remain readable

- **GIVEN** a `playbook` row written before this migration with `attachment_hash_snapshot IS NULL`
- **WHEN** `PlaybookRepository.get_or_create_for_meeting(meeting_id)` runs
- **THEN** the call SHALL succeed and the returned playbook object's `attachment_hash_snapshot` attribute SHALL be `None`


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
### Requirement: Playbook is_stale flag reacts to attachment set changes

The backend SHALL expose `PlaybookRepository.get_with_stale_flag(meeting_id) -> PlaybookWithStale | None` returning the persisted playbook row plus a computed `is_stale: bool`. The `is_stale` value SHALL be `True` when any of the following hold:

1. (Existing conditions covered by other capabilities — if any pre-S20c stale conditions apply, those still trigger `True`.)
2. The current attachment-set hash for the meeting differs from `playbook.attachment_hash_snapshot`. The current attachment-set hash is computed as `sha256(sorted(sha256(open(att.file_path,'rb').read()) for att in MeetingAttachmentRepository.list_for_meeting(meeting_id) if att.deleted_at IS NULL))`, expressed as a lowercase hex string. The empty-attachment set SHALL hash to the canonical empty-set hash `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`.

Legacy rows where `attachment_hash_snapshot IS NULL` SHALL be treated as if they recorded the empty-set hash — so a meeting with zero attachments and a NULL snapshot is NOT stale, but a meeting with one attachment and a NULL snapshot IS stale (the row was written before attachment tracking existed; the new attachment is real new context).

#### Scenario: Playbook stays fresh when attachment set is unchanged

- **GIVEN** a meeting with a playbook generated at T0 whose `attachment_hash_snapshot` matches the current attachment-set hash
- **WHEN** `PlaybookRepository.get_with_stale_flag(meeting_id)` runs at T0 + 1 hour
- **THEN** the returned object's `is_stale` SHALL be `False`

#### Scenario: Adding a new attachment marks the playbook stale

- **GIVEN** a meeting with one PDF whose playbook was generated and the row's `attachment_hash_snapshot` matches the one-PDF current hash
- **WHEN** a second PNG attachment is uploaded for that meeting AND `PlaybookRepository.get_with_stale_flag(meeting_id)` runs
- **THEN** `is_stale` SHALL be `True`

#### Scenario: Deleting an attachment marks the playbook stale

- **GIVEN** a meeting whose playbook was generated with two attachments and `attachment_hash_snapshot` matches that two-attachment hash
- **WHEN** one attachment is soft-deleted (`deleted_at = now()`) and `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `True`

#### Scenario: Replacing an attachment with identical content does NOT mark stale

- **GIVEN** a meeting whose playbook was generated with one PDF whose bytes hash to `h_pdf`
- **WHEN** the user deletes that attachment and uploads a different `AttachmentRef` row whose file bytes are byte-identical (hash to the same `h_pdf`)
- **THEN** the current attachment-set hash SHALL still equal `attachment_hash_snapshot` AND `is_stale` SHALL be `False`

#### Scenario: Legacy NULL snapshot row with no current attachments is NOT stale

- **GIVEN** a playbook row written before migration with `attachment_hash_snapshot IS NULL` AND the meeting has zero non-deleted attachments
- **WHEN** `get_with_stale_flag` runs
- **THEN** `is_stale` SHALL be `False`

#### Scenario: Legacy NULL snapshot row with new attachment IS stale

- **GIVEN** a playbook row written before migration with `attachment_hash_snapshot IS NULL` AND the meeting now has one PDF attachment
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