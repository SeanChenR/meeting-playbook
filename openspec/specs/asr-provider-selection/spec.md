# asr-provider-selection Specification

## Purpose

TBD - created by archiving change 'slice-11-asr-and-retention'. Update Purpose after archive.

## Requirements

### Requirement: Qwen3ASRProvider implements ASRProvider Protocol via MLX 8-bit model

The backend SHALL provide a `Qwen3ASRProvider` at `packages/backend/meeting_playbook/asr/qwen3_provider.py` that implements the existing `ASRProvider` Protocol (slice-6 ADR-0005): `name -> str`, `transcribe_chunk(audio_bytes, sample_rate_hz, language_hint) -> TranscriptChunk`, and `warmup() -> None`. The implementation SHALL load the `doggy8088/Qwen3-ASR-1.7B-MLX-8bit` model from Hugging Face Hub on first use (lazy warmup, mirrors `WhisperProvider`); subsequent calls SHALL reuse the loaded model. The provider SHALL accept a `stream` parameter (`"me" | "counterparty"`) so per-stream singletons can be allocated separately for parallel inference.

The implementation SHALL convert int16 PCM input bytes to the format Qwen3-ASR expects (whatever the MLX loader API requires; resolved during a 5-10 minute spike in the apply phase) and SHALL return a `TranscriptChunk` with `text`, `started_at`, `ended_at`, `asr_provider_used = "qwen3"`, and an averaged confidence score (or None if the loader doesn't expose per-segment confidence). Empty / silent audio SHALL return a `TranscriptChunk` with empty `text` (matches Whisper behavior).

#### Scenario: Qwen3ASRProvider satisfies the ASRProvider Protocol

- **GIVEN** a `Qwen3ASRProvider(stream="me")` instance
- **WHEN** Python's `isinstance(provider, ASRProvider)` runs (the Protocol is `@runtime_checkable`)
- **THEN** the check SHALL return `True`

#### Scenario: First transcribe_chunk loads the model lazily; subsequent calls reuse it

- **GIVEN** a freshly constructed `Qwen3ASRProvider` (no `warmup()` called)
- **WHEN** `transcribe_chunk(audio_bytes=<10s of int16 PCM>, sample_rate_hz=16000)` runs the first time
- **THEN** the model SHALL be downloaded (if not cached) and loaded; the call returns a `TranscriptChunk`
- **AND** a second call to `transcribe_chunk(...)` SHALL NOT re-load the model (verified by patching the loader and asserting it's invoked exactly once)

#### Scenario: warmup() is idempotent

- **GIVEN** a freshly constructed `Qwen3ASRProvider`
- **WHEN** `warmup()` is called twice in succession
- **THEN** the model SHALL be loaded exactly once; the second `warmup()` SHALL return without re-loading


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
### Requirement: ASR factory selects provider per meeting at WebSocket connect time

The backend SHALL provide `packages/backend/meeting_playbook/asr/factory.py` exporting `get_asr_providers_for_meeting(provider_name: str) -> dict[Stream, ASRProvider]`. The function SHALL return a dict with keys `"me"` and `"counterparty"`, each mapping to a process-scoped singleton `ASRProvider` instance for that `(provider_name, stream)` pair (using `functools.lru_cache` on a private helper). Unknown `provider_name` values SHALL fall back to `WhisperProvider` (defensive default for forward compat with future renames or typos).

The session WebSocket handler `meeting_session_endpoint` SHALL replace the existing `Depends(get_asr_providers_dependency)` injection with an inline call to `get_asr_providers_for_meeting(meeting.asr_provider)` AFTER the meeting row is loaded and ownership verified. Existing FastAPI dependency `get_asr_providers_dependency` SHALL be deleted (no callers remain).

#### Scenario: Factory returns Qwen3 instances when meeting.asr_provider is "qwen3"

- **GIVEN** a meeting with `asr_provider = "qwen3"`
- **WHEN** the WS handler calls `get_asr_providers_for_meeting("qwen3")`
- **THEN** the returned dict SHALL contain two `Qwen3ASRProvider` instances (one per stream); calling the function again with the same args SHALL return the same instances (singleton)

#### Scenario: Factory returns Whisper instances when meeting.asr_provider is "whisper"

- **GIVEN** a meeting with `asr_provider = "whisper"`
- **WHEN** the WS handler calls `get_asr_providers_for_meeting("whisper")`
- **THEN** the returned dict SHALL contain two `WhisperProvider` instances

#### Scenario: Unknown provider name falls back to Whisper

- **GIVEN** a meeting with `asr_provider = "vibevoice"` (deprecated per ADR-0028)
- **WHEN** the WS handler calls `get_asr_providers_for_meeting("vibevoice")`
- **THEN** the returned dict SHALL contain `WhisperProvider` instances; the WS session SHALL still start successfully (no crash)


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
### Requirement: Meeting.asr_provider defaults to qwen3 for new meetings

The `Meeting` ORM column `asr_provider` SHALL default to `"qwen3"` (was `"whisper"`). The Alembic migration that introduces `recording.deleted_at` SHALL NOT back-fill existing meeting rows; existing meetings keep whatever `asr_provider` value they had at creation time (preserves the historical fact that those transcripts were generated by the named provider).

The `MeetingRepository.create` method's `asr_provider` parameter default SHALL also change to `"qwen3"` to keep the Python and SQL defaults in sync.

#### Scenario: New meeting creation uses qwen3 by default

- **WHEN** the meetings router creates a meeting via POST `/api/meetings` without specifying `asr_provider`
- **THEN** the inserted row's `asr_provider` SHALL be `"qwen3"`

#### Scenario: Existing meetings retain their original asr_provider after the migration

- **GIVEN** a meeting created in slice-3 with `asr_provider = "whisper"` (the slice-3 default at the time)
- **WHEN** the slice-11 migration runs
- **THEN** the row's `asr_provider` SHALL remain `"whisper"` (no UPDATE statement in the migration)


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
### Requirement: POST /api/meetings/{id}/rerun_asr triggers atomic transcript replacement

The backend SHALL expose `POST /api/meetings/{meeting_id}/rerun_asr` (mounted by `rerun/router.py`) requiring the gateway-injected `X-User-Id` header. The endpoint SHALL verify ownership via `MeetingRepository.get_for_user`; non-owner / non-existent meeting SHALL return HTTP 404 with the standard flat envelope `{error_code: "meeting.not_found"}`. Missing `X-User-Id` SHALL return HTTP 401 with `{error_code: "auth.gateway_bypass"}`.

The endpoint SHALL reject the request with these status codes when preconditions fail:
- HTTP 422 `{error_code: "rerun.not_completed"}` if `meeting.status != "completed"`.
- HTTP 410 `{error_code: "rerun.recording_expired"}` if all of the meeting's `recording` rows have `deleted_at IS NOT NULL` (or the meeting has zero recordings).
- HTTP 409 `{error_code: "rerun.busy"}` if `rerun.runtime.is_pending(meeting_id)` is True.

When all preconditions pass, the endpoint SHALL call `rerun.runtime.spawn_rerun_task(meeting_id)` (process-scoped in-flight registry, mirrors slice-10 summary runtime) and return HTTP 202 with body `{status: "pending"}`.

The spawned background task SHALL: (1) open a fresh `AsyncSession` via `session_factory()`; (2) load both `recording` rows for the meeting; (3) for each WAV file, chunk into ~10-second windows and update the in-flight registry's progress counter; (4) call `provider.transcribe_chunk(...)` per chunk using the meeting's current `asr_provider`; (5) accumulate all `TranscriptChunk` results in memory; (6) on full success, run a single transaction containing `DELETE FROM transcript_chunk WHERE meeting_id = ?` followed by `INSERT ... RETURNING` for every new chunk, then commit; (7) pop the meeting_id from the in-flight registry. On any exception during chunk processing, the task SHALL log the traceback, NOT touch existing `transcript_chunk` rows (no partial replacement), and still pop the registry in a `finally` block.

#### Scenario: Owner POST on a completed meeting with available recordings spawns task and returns 202

- **GIVEN** a meeting with `status = "completed"` and at least one recording with `deleted_at IS NULL`
- **WHEN** the owner POSTs to `/api/meetings/{id}/rerun_asr`
- **THEN** the response SHALL be HTTP 202 with body `{"status": "pending"}` AND `rerun.runtime.is_pending(meeting_id)` SHALL return `True`

#### Scenario: POST on a meeting with all recordings expired returns 410

- **GIVEN** a meeting whose recording row(s) all have `deleted_at IS NOT NULL`
- **WHEN** the owner POSTs to `/api/meetings/{id}/rerun_asr`
- **THEN** the response SHALL be HTTP 410 with body `{"error_code": "rerun.recording_expired"}`

#### Scenario: POST on a meeting with status != completed returns 422

- **GIVEN** a meeting with `status = "in_progress"`
- **WHEN** the owner POSTs to `/api/meetings/{id}/rerun_asr`
- **THEN** the response SHALL be HTTP 422 with body `{"error_code": "rerun.not_completed"}`

#### Scenario: POST while a re-run task is already in-flight returns 409 rerun.busy

- **GIVEN** an existing in-flight rerun task for the meeting
- **WHEN** the owner POSTs again
- **THEN** the response SHALL be HTTP 409 with body `{"error_code": "rerun.busy"}` AND no second task SHALL spawn

#### Scenario: Successful background task replaces transcript_chunk rows atomically

- **GIVEN** a meeting with 5 existing `transcript_chunk` rows from a Whisper session
- **WHEN** the owner POSTs `/rerun_asr` and the background task completes (mocked Qwen3 returning 4 new chunks)
- **THEN** the database SHALL contain exactly 4 `transcript_chunk` rows for the meeting; ALL 5 original rows SHALL be gone (single transaction); each new row's `asr_provider_used` SHALL match the meeting's current `asr_provider`

#### Scenario: Background task failure leaves existing transcript intact

- **GIVEN** a meeting with 5 existing `transcript_chunk` rows AND a mocked provider that raises on the second chunk
- **WHEN** the background task runs
- **THEN** the database SHALL still contain those exact 5 original rows AND `rerun.runtime.is_pending(meeting_id)` SHALL return `False` AND the backend log SHALL contain the exception traceback


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
### Requirement: GET /api/meetings/{id}/rerun_asr_status returns polling-friendly progress shape

The backend SHALL expose `GET /api/meetings/{meeting_id}/rerun_asr_status` requiring the same `X-User-Id` ownership gate. The response SHALL always be HTTP 200 with body `{status: "idle" | "pending" | "failed", chunks_processed: int, chunks_total: int}`, where:

- `status = "pending"` iff `rerun.runtime.is_pending(meeting_id)` is True.
- `status = "failed"` iff the most recent task for this meeting raised an exception AND no new task has spawned since (registry tracks last-failure flag).
- `status = "idle"` otherwise (no task ever ran, or last task succeeded and registry is clean).
- `chunks_processed` and `chunks_total` come from the in-flight progress counter; both 0 when status is `"idle"`.

The endpoint SHALL NOT return 404 for a meeting that has never been re-run — `idle` is the canonical "no rerun in flight" state. Non-owner / non-existent meeting still returns HTTP 404 `meeting.not_found`.

#### Scenario: Idle meeting returns idle status with zero counters

- **GIVEN** a meeting with no current or past re-run attempt
- **WHEN** the owner GETs `/rerun_asr_status`
- **THEN** the response SHALL be HTTP 200 with body `{"status": "idle", "chunks_processed": 0, "chunks_total": 0}`

#### Scenario: In-flight meeting returns pending status with progress counters

- **GIVEN** a meeting whose re-run task has processed 12 of 45 chunks
- **WHEN** the owner GETs `/rerun_asr_status`
- **THEN** the response SHALL be HTTP 200 with body `{"status": "pending", "chunks_processed": 12, "chunks_total": 45}`

#### Scenario: Failed task surfaces failed status until next spawn

- **GIVEN** a meeting whose most recent re-run task raised an exception
- **WHEN** the owner GETs `/rerun_asr_status`
- **THEN** the response SHALL be HTTP 200 with body `{"status": "failed", ...}`; subsequent successful POST `/rerun_asr` SHALL reset the registry so the next GET shows `"pending"` then `"idle"`

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