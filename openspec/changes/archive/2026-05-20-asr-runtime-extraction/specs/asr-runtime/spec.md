## ADDED Requirements

### Requirement: ASR runtime process isolation

The system SHALL run a dedicated ASR runtime service in a separate OS process from the backend FastAPI service. The runtime SHALL load the Qwen3-ASR model into its own memory space exactly once per process lifetime, regardless of how many times the backend process reloads.

#### Scenario: Backend reload preserves model state

- **WHEN** the developer edits a backend Python file and uvicorn reloads the backend process
- **THEN** the ASR runtime process SHALL remain running with the model still loaded
- **AND** the next session start SHALL skip the cold-start model download / load step

#### Scenario: ASR runtime crash isolated from backend

- **WHEN** the ASR runtime process exits unexpectedly
- **THEN** the backend session WebSocket SHALL remain open
- **AND** the backend SHALL surface `error_code: asr.runtime_unavailable` to the frontend rather than dropping the session

### Requirement: WebSocket realtime transcription endpoint

The ASR runtime SHALL expose `/v1/transcribe/stream` as a WebSocket endpoint for realtime session transcription. The endpoint SHALL accept a one-shot config frame followed by zero-or-more audio chunk frames, and SHALL emit one ready frame plus zero-or-more transcript chunk frames in response.

#### Scenario: Client opens stream and receives ready signal

- **WHEN** a backend client opens a WebSocket to `/v1/transcribe/stream` and sends `{"type": "config", "sample_rate_hz": 16000, "language_hint": "zh"}`
- **THEN** the runtime SHALL respond with `{"type": "ready"}` once the model is warm
- **AND** subsequent `{"type": "audio_chunk", "audio_bytes_b64": "...", "sequence": N}` frames SHALL be accepted

#### Scenario: Audio chunk produces transcript chunk

- **WHEN** the client sends an `audio_chunk` frame with valid base64-encoded PCM bytes
- **THEN** the runtime SHALL produce a `{"type": "transcript_chunk", "sequence": N, "text": "...", "started_at": "...", "ended_at": "..."}` response within the inference latency budget
- **AND** the `sequence` value SHALL match the input chunk's `sequence`

#### Scenario: Server closes connection on error

- **WHEN** model inference fails for a chunk
- **THEN** the runtime SHALL emit `{"type": "error", "error_code": "asr.runtime_unavailable", "message": "...", "retriable": false}`
- **AND** the runtime SHALL close the WebSocket connection with a normal-close code

### Requirement: HTTP chunk transcription endpoint

The ASR runtime SHALL expose `POST /v1/transcribe/chunk` as an HTTP endpoint accepting a single audio chunk and returning a single transcript chunk synchronously. This endpoint SHALL be used by the offline ingest batch path.

#### Scenario: Successful chunk transcription via HTTP

- **WHEN** a client posts `{"audio_bytes_b64": "...", "sample_rate_hz": 16000, "language_hint": "zh"}`
- **THEN** the runtime SHALL respond with HTTP 200 and body `{"text": "...", "started_at": "...", "ended_at": "..."}`

#### Scenario: Failed chunk returns structured error

- **WHEN** the runtime fails to process the audio (model error, invalid base64, etc.)
- **THEN** the response SHALL be HTTP 5xx with body `{"error_code": "asr.runtime_unavailable", "message": "...", "retriable": <bool>}`

### Requirement: Health check endpoint reports model load state

The ASR runtime SHALL expose `GET /healthz` returning JSON with at minimum `status`, `model_repo`, `device`, and `uptime_seconds` fields. The `status` field SHALL be one of `loading`, `ready`, or `error`.

#### Scenario: Health check during cold start

- **WHEN** the runtime is still loading the model
- **THEN** `GET /healthz` SHALL return HTTP 200 with `{"status": "loading", ...}`

#### Scenario: Health check after warmup

- **WHEN** the model has finished loading and warmup inference has succeeded
- **THEN** `GET /healthz` SHALL return HTTP 200 with `{"status": "ready", ...}`

#### Scenario: Health check after model failure

- **WHEN** the model load or warmup raises an exception
- **THEN** `GET /healthz` SHALL return HTTP 200 with `{"status": "error", ...}` and the error message SHALL appear in a `last_error` field

### Requirement: Optional startup warmup

The ASR runtime SHALL run a model warmup pass during uvicorn lifespan startup when `ASR_RUNTIME_WARMUP_ON_BOOT` env var is set to `1` (the default). Warmup SHALL feed a fixed 0.5-second silent audio buffer through the model so the first real chunk does not pay cold-start cost.

#### Scenario: Warmup enabled by default

- **WHEN** the runtime starts with no env override
- **THEN** the runtime SHALL run warmup before reporting `status: ready`

#### Scenario: Warmup can be disabled for fast iteration

- **WHEN** the runtime starts with `ASR_RUNTIME_WARMUP_ON_BOOT=0`
- **THEN** the runtime SHALL transition to `status: ready` immediately after the model finishes loading
- **AND** the first real chunk MAY incur the cold-start inference cost

### Requirement: Runtime configured via env vars only

The ASR runtime SHALL read all configuration from environment variables: `ASR_RUNTIME_PORT`, `ASR_RUNTIME_DEVICE`, `ASR_RUNTIME_MODEL_REPO`, `ASR_RUNTIME_WARMUP_ON_BOOT`. All five env vars SHALL have documented defaults in `.env.example`.

#### Scenario: Default config matches dev environment

- **WHEN** the runtime starts with no env overrides
- **THEN** the runtime SHALL listen on `127.0.0.1:8100`
- **AND** SHALL select device `mps`
- **AND** SHALL load model `Qwen/Qwen3-ASR-1.7B`

#### Scenario: Port override respected

- **WHEN** `ASR_RUNTIME_PORT=8200` is set
- **THEN** the runtime SHALL listen on port `8200` instead

### Requirement: Model loading sidesteps accelerate meta-tensor dispatch

The ASR runtime SHALL load the Qwen3 model with `Qwen3ASRModel.from_pretrained(...)` WITHOUT passing `device_map=...`, then call `.to(device)` manually after weights are materialised. This avoids the `NotImplementedError: Cannot copy out of meta tensor` exception that the `accelerate.dispatch_model` code path raises when moving meta-tensor modules to MPS.

#### Scenario: Model loads on MPS without meta-tensor error

- **WHEN** the runtime starts with `ASR_RUNTIME_DEVICE=mps`
- **THEN** the model SHALL load successfully on the MPS device
- **AND** no `Cannot copy out of meta tensor` error SHALL appear in the log

### Requirement: Runtime concurrency serialised via asyncio Lock

The ASR runtime's internal `Qwen3Runner.transcribe(...)` SHALL serialise inference calls through an `asyncio.Lock` so multiple concurrent chunk requests do not race on shared model state. The lock SHALL be released as soon as the inference call returns.

#### Scenario: Concurrent chunks process in arrival order

- **GIVEN** two backend WebSocket clients each push an audio chunk at roughly the same time
- **WHEN** both chunks arrive at the runtime
- **THEN** the runtime SHALL process them one at a time
- **AND** each client SHALL receive its own transcript chunk back in arrival order
