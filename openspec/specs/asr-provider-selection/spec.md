# asr-provider-selection Specification

## Purpose

TBD - created by archiving change 'slice-11-asr-and-retention'. Update Purpose after archive.

## Requirements

### Requirement: Qwen3ASRProvider implements ASRProvider Protocol via MLX 8-bit model

The backend SHALL provide a `RemoteAsrRuntimeClient` at `packages/backend/meeting_playbook/asr/remote_runtime_client.py` that implements the existing `ASRProvider` Protocol (slice-6 ADR-0005): `name -> str`, `transcribe_chunk(audio_bytes, sample_rate_hz, language_hint) -> TranscriptChunk`, and `warmup() -> None`. The implementation SHALL delegate all transcription to the standalone ASR runtime service over WebSocket (for realtime session paths) or HTTP (for the offline ingest path); the backend process SHALL NOT load the Qwen3-ASR model into its own memory space anymore.

The client SHALL accept a `stream` parameter (`"me" | "counterparty"`) so per-stream sessions can be opened independently to the runtime, and a `runtime_url` parameter resolved from the `ASR_RUNTIME_URL` environment variable. The legacy in-process `Qwen3ASRProvider` (which loaded the MLX 8-bit model directly) SHALL be removed; its responsibilities migrate to the asr-runtime micro-service. Empty / silent audio SHALL return a `TranscriptChunk` with empty `text` (preserves the prior provider's behavior).

#### Scenario: RemoteAsrRuntimeClient satisfies the ASRProvider Protocol

- **GIVEN** a `RemoteAsrRuntimeClient(stream="me", runtime_url="http://127.0.0.1:8100")` instance
- **WHEN** Python's `isinstance(provider, ASRProvider)` runs (the Protocol is `@runtime_checkable`)
- **THEN** the check SHALL return `True`

#### Scenario: First transcribe_chunk opens runtime connection; subsequent calls reuse it

- **GIVEN** a freshly constructed `RemoteAsrRuntimeClient`
- **WHEN** `transcribe_chunk(audio_bytes=<10s of int16 PCM>, sample_rate_hz=16000)` runs the first time
- **THEN** the client SHALL open a connection to the ASR runtime (HTTP or WebSocket) and return a `TranscriptChunk`
- **AND** a second call to `transcribe_chunk(...)` SHALL reuse the connection without re-handshaking

#### Scenario: warmup() pings the runtime healthz endpoint

- **GIVEN** a freshly constructed `RemoteAsrRuntimeClient`
- **WHEN** `warmup()` is called
- **THEN** the client SHALL poll `GET /healthz` against the runtime until `status` is `ready`, with a per-attempt timeout, and SHALL return without raising once ready

#### Scenario: Runtime unavailable surfaces a structured error

- **WHEN** the runtime returns HTTP 5xx or its WebSocket closes with an error frame containing `error_code: asr.runtime_unavailable`
- **THEN** the client SHALL raise `AsrRuntimeUnavailableError` carrying the same `error_code`
- **AND** the caller (session router or offline ingest job) SHALL receive that exception to handle in its own retry / surface logic


<!-- @trace
source: asr-runtime-extraction
updated: 2026-05-20
code:
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/server.py
  - packages/asr-runtime/uv.lock
  - packages/asr-runtime/meeting_playbook_asr_runtime/__init__.py
  - packages/backend/meeting_playbook/asr/factory.py
  - docs/adr/0030-asr-runtime-extraction.md
  - packages/backend/meeting_playbook/asr/remote_runtime_client.py
  - packages/web/src/components/meeting-detail-action-bar.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/schemas.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/asr-runtime/pyproject.toml
  - packages/asr-runtime/meeting_playbook_asr_runtime/errors.py
  - packages/asr-runtime/meeting_playbook_asr_runtime/routes/transcribe.py
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - package.json
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/backend/meeting_playbook/sessions/router.py
  - README.md
  - packages/asr-runtime/meeting_playbook_asr_runtime/qwen3_runner.py
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/routes/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - .env.example
tests:
  - packages/backend/tests/asr/test_factory.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/asr-runtime/tests/test_transcribe_http.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/asr-runtime/tests/test_transcribe_ws.py
  - packages/asr-runtime/tests/__init__.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/asr-runtime/tests/test_health.py
  - packages/backend/tests/asr/test_remote_runtime_client.py
  - packages/asr-runtime/tests/test_schemas.py
  - packages/asr-runtime/tests/test_qwen3_runner.py
-->

---
### Requirement: ASR factory selects provider per meeting at WebSocket connect time

The backend SHALL provide `packages/backend/meeting_playbook/asr/factory.py` exporting `get_asr_providers_for_meeting(provider_name: str) -> dict[Stream, ASRProvider]`. The function SHALL return a dict with keys `"me"` and `"counterparty"`, each mapping to a process-scoped singleton `RemoteAsrRuntimeClient` instance for that stream (using `functools.lru_cache` on a private helper). Only `provider_name = "qwen3"` SHALL be supported; the historical Whisper code path is removed.

Unknown or legacy `provider_name` values (e.g. `"whisper"`, `"vibevoice"`) SHALL be coerced to `"qwen3"` at the factory boundary so that meetings persisted with deprecated names still resolve to a working provider. A `structlog` warning SHALL be emitted for any coerced name so operators can spot stale rows.

The session WebSocket handler `meeting_session_endpoint` SHALL keep the inline call to `get_asr_providers_for_meeting(meeting.asr_provider)` AFTER the meeting row is loaded and ownership verified, unchanged from the prior contract.

#### Scenario: Factory returns RemoteAsrRuntimeClient instances when meeting.asr_provider is "qwen3"

- **GIVEN** a meeting with `asr_provider = "qwen3"`
- **WHEN** the WS handler calls `get_asr_providers_for_meeting("qwen3")`
- **THEN** the returned dict SHALL contain two `RemoteAsrRuntimeClient` instances (one per stream); calling the function again with the same args SHALL return the same instances (singleton)

#### Scenario: Legacy provider names coerce to qwen3 with a warning

- **GIVEN** a meeting with `asr_provider = "whisper"` (historical row from a meeting persisted before this change)
- **WHEN** the WS handler calls `get_asr_providers_for_meeting("whisper")`
- **THEN** the returned dict SHALL contain `RemoteAsrRuntimeClient` instances (qwen3-backed)
- **AND** the structured log SHALL include a warning like `asr_provider_coerced from="whisper" to="qwen3" meeting_id=...`

#### Scenario: Runtime URL missing raises an explicit error

- **GIVEN** the env var `ASR_RUNTIME_URL` is unset or empty
- **WHEN** `get_asr_providers_for_meeting("qwen3")` runs
- **THEN** it SHALL raise `AsrRuntimeUnavailableError` before returning any provider instances
- **AND** the WS handler SHALL relay the error to the frontend via the existing session error path


<!-- @trace
source: asr-runtime-extraction
updated: 2026-05-20
code:
  - packages/web/public/icons/whisper.png
  - packages/backend/meeting_playbook/config.py
  - packages/web/src/components/asr-provider-selector.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/server.py
  - packages/asr-runtime/uv.lock
  - packages/asr-runtime/meeting_playbook_asr_runtime/__init__.py
  - packages/backend/meeting_playbook/asr/factory.py
  - docs/adr/0030-asr-runtime-extraction.md
  - packages/backend/meeting_playbook/asr/remote_runtime_client.py
  - packages/web/src/components/meeting-detail-action-bar.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/schemas.py
  - packages/web/src/routes/settings/preferences.tsx
  - packages/asr-runtime/pyproject.toml
  - packages/asr-runtime/meeting_playbook_asr_runtime/errors.py
  - packages/asr-runtime/meeting_playbook_asr_runtime/routes/transcribe.py
  - packages/backend/meeting_playbook/asr/qwen3_provider.py
  - package.json
  - packages/backend/meeting_playbook/asr/whisper_provider.py
  - packages/backend/meeting_playbook/sessions/router.py
  - README.md
  - packages/asr-runtime/meeting_playbook_asr_runtime/qwen3_runner.py
  - packages/web/src/components/asr-engine-hint.tsx
  - packages/asr-runtime/meeting_playbook_asr_runtime/routes/__init__.py
  - packages/backend/meeting_playbook/offline_ingest/pipeline.py
  - .env.example
tests:
  - packages/backend/tests/asr/test_factory.py
  - packages/web/src/components/asr-provider-selector.test.tsx
  - packages/asr-runtime/tests/test_transcribe_http.py
  - packages/backend/tests/asr/test_qwen3_provider.py
  - packages/backend/tests/sessions/test_router.py
  - packages/backend/tests/conftest.py
  - packages/backend/tests/offline_ingest/test_runtime.py
  - packages/asr-runtime/tests/test_transcribe_ws.py
  - packages/asr-runtime/tests/__init__.py
  - packages/backend/tests/asr/test_whisper_provider.py
  - packages/asr-runtime/tests/test_health.py
  - packages/backend/tests/asr/test_remote_runtime_client.py
  - packages/asr-runtime/tests/test_schemas.py
  - packages/asr-runtime/tests/test_qwen3_runner.py
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