## MODIFIED Requirements

### Requirement: ASR runs through one ASRProvider instance per stream with parallel warmup

The `SessionService` SHALL maintain a mapping from stream identifier (`me` / `counterparty`) to an `ASRProvider` instance. After the asr-runtime extraction the concrete implementation SHALL be `RemoteAsrRuntimeClient` (one per stream) rather than an in-process model class — each stream owns its own WebSocket connection to the standalone ASR runtime so per-stream inference can proceed concurrently without sharing a single back-pressure queue.

Each `ASRProvider` SHALL expose an idempotent `warmup()` async method. For `RemoteAsrRuntimeClient`, `warmup()` SHALL poll `GET /healthz` against the runtime until `status == "ready"` (with a configurable timeout). During the connecting phase the session SHALL invoke both providers' `warmup()` calls in parallel via `asyncio.gather` so the first chunks are available without serial cold-start delay. Each captured `AudioChunk` SHALL be transcribed only by the provider mapped to that chunk's stream label.

#### Scenario: Warmup runs both providers in parallel

- **GIVEN** the session is starting and the runtime reports `status: loading` on first poll
- **WHEN** the session enters the connecting phase
- **THEN** both `provider.warmup()` calls SHALL be awaited via `asyncio.gather` (concurrently) and each provider SHALL stop polling as soon as the runtime reports `status: ready`

#### Scenario: Per-stream chunk routing

- **GIVEN** an active dual-stream session with provider A mapped to `me` and provider B mapped to `counterparty`
- **WHEN** the `me` capture emits five chunks and the `counterparty` capture emits five chunks
- **THEN** provider A SHALL receive exactly the five `me` chunks (and zero `counterparty` chunks) and provider B SHALL receive exactly the five `counterparty` chunks (and zero `me` chunks)

#### Scenario: Runtime unavailable during connecting phase aborts session start

- **GIVEN** the runtime process is not running (no listener on `ASR_RUNTIME_URL`)
- **WHEN** the WebSocket handler enters the connecting phase and calls `warmup()` on either provider
- **THEN** the provider SHALL raise `AsrRuntimeUnavailableError` within its configured warmup timeout
- **AND** the session handler SHALL emit a final `{"type": "error", "error_code": "asr.runtime_unavailable", ...}` frame and close the WebSocket cleanly
- **AND** no `transcript_chunk` frames SHALL be sent

#### Scenario: Runtime failure on a single chunk does not tear down the session

- **GIVEN** an active in-progress session with both providers warm
- **WHEN** the runtime returns `error_code: asr.runtime_unavailable` for one specific chunk (e.g. transient model error)
- **THEN** the session handler SHALL drop the failing chunk, emit a structlog warning carrying the chunk's `sequence`, and continue accepting subsequent chunks
- **AND** the WebSocket SHALL remain open
