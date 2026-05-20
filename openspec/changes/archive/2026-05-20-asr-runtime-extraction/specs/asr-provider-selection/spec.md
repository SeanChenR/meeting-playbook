## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: WhisperProvider is offered alongside Qwen3

**Reason**: Sean's machine cannot run Whisper Large v3 efficiently; the dual-engine option created maintenance overhead (two provider classes, two test fixtures, two settings cards, two i18n keys) without delivering value. ASR runtime extraction is the natural moment to retire it.

**Migration**: Historical meetings persisted with `asr_provider = "whisper"` continue to load (factory coerces to `"qwen3"` with a warning log). Frontend dropdown / settings preferences card / provider PNG logo are removed. `WHISPER_*` env vars are deleted from `.env.example` (no documented default = no expected source of overrides). No Alembic migration is written — the historical column value is preserved as a record of what the original transcription engine was.

#### Scenario: Post-removal migration path resolves legacy whisper rows

- **GIVEN** a meeting row persisted before the change with `asr_provider = "whisper"`
- **WHEN** the meeting is loaded after the change ships
- **THEN** the factory SHALL coerce the value to `"qwen3"` and emit a structlog warning of the form `asr_provider_coerced from="whisper" to="qwen3" meeting_id=<id>`
- **AND** the WebSocket session SHALL still start successfully (no crash, no user-facing error)
- **AND** the underlying DB column value SHALL remain `"whisper"` (no Alembic migration overwrites it)
