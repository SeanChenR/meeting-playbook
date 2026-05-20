# ADR-0030: Extract ASR into a standalone `asr-runtime` micro-service

- **Status**: Accepted
- **Date**: 2026-05-20
- **Decider**: Sean

## Context

`Qwen3ASRProvider` (per ADR-0028) loaded the Qwen3-ASR-1.7B model directly
inside the `packages/backend` FastAPI worker. Three things hurt in
practice:

1. **Memory pressure**. The model weighs ~5 GB once loaded. Sharing the
   FastAPI process with SQLAlchemy's connection pool, Better Auth gateway
   client, Gemini SDK, and the WebSocket message bus pushed the Mac M3 Pro
   18 GB host into swap on day-to-day workflows.
2. **Failure connaissance**. Model load could (and did) crash the backend
   worker — `accelerate`'s meta-tensor dispatch raises
   `NotImplementedError: Cannot copy out of meta tensor` on MPS, and
   Hugging Face download interruptions surface as long stack traces that
   take the WebSocket session down with them. Every transient ASR failure
   killed the in-flight `meeting_session` WS.
3. **Reload tax**. Backend code edits triggered uvicorn `--reload`, which
   re-loaded the 5 GB model on every reload — ~30 seconds before the next
   ASR call could land.

Plus Sean's hardware can't realistically run `Whisper Large v3` either,
which left the Whisper code path as maintenance overhead with no actual
users.

## Decision

Extract ASR into a dedicated `packages/asr-runtime/` micro-service:

- Separate uvicorn process on `127.0.0.1:8100` (overridable via
  `ASR_RUNTIME_PORT`), launched by the root dev script via
  `concurrently` alongside `web`, `auth`, `backend`.
- Talks JSON over WebSocket (`/v1/transcribe/stream`) for realtime
  `meeting-session` traffic and HTTP (`POST /v1/transcribe/chunk`) for
  offline ingest. Frame schemas mirror what `ASRProvider.transcribe_chunk`
  already produced.
- `packages/backend` ships a single concrete `ASRProvider`:
  `RemoteAsrRuntimeClient`. The factory rejects environments without
  `ASR_RUNTIME_URL` (no in-process fallback — Whisper is gone).
- Whisper is removed entirely: provider class, test, settings card,
  PNG logo, i18n key, and the `whisper` enum value all delete. Historical
  meetings persisted with `asr_provider = "whisper"` keep working via a
  read-time coercion to `qwen3` (logged so operators can spot stale rows).
- New env vars: `ASR_RUNTIME_URL`, `ASR_RUNTIME_PORT`,
  `ASR_RUNTIME_DEVICE`, `ASR_RUNTIME_MODEL_REPO`,
  `ASR_RUNTIME_WARMUP_ON_BOOT`. All documented in `.env.example`.

## Consequences

### Positive

- `backend` reload no longer reloads the model. The runtime stays warm
  across editing cycles.
- ASR failure modes are now structured: the runtime returns
  `error_code: asr.runtime_unavailable` and the backend translates that
  into a WebSocket error frame instead of dropping the socket.
- `accelerate` meta-tensor bug is contained — the runtime's
  `Qwen3Runner._load_qwen3_model` loads weights to CPU first and then
  `.to(device)`, sidestepping the failing path. Move it to a single file
  and we won't accidentally rediscover the bug from another call site.
- Offline ingest gets bounded retry on `asr.runtime_unavailable`
  (2 / 4 / 8 s exponential backoff before marking the job `failed`).

### Negative

- One more port to manage in the dev environment. The root dev script
  abstracts this away; `ASR_RUNTIME_PORT` exists for the rare collision.
- No automatic restart on crash. If the runtime process exits, the user
  has to relaunch the dev script (concurrently surfaces this loudly
  enough that you can't miss it; production deploys aren't part of this
  ADR's scope yet).
- WebSocket hop adds ~5–20 ms latency vs. in-process inference. Real
  inference is 1–3 seconds per chunk, so the hop is rounding error.

### Compatibility with other ADRs

- **ADR-0005** (pluggable `ASRProvider` Protocol) — preserved. We swap
  the concrete class behind the protocol; everything else stays the
  same.
- **ADR-0026** (VibeVoice runtime spike) and **ADR-0028** (Qwen3-ASR
  replaces VibeVoice) — both consistent. Qwen3-ASR is still the chosen
  engine; this ADR only changes where the inference happens.
- **ADR-0029** (hybrid speaker attribution) — unchanged. Speaker
  attribution still runs against the transcript chunks emitted by the
  runtime; the runtime is dumb about speakers.
- If/when a future engine joins (VibeVoice v2, a Vertex AI ASR endpoint,
  ...) it can either land as another runtime instance or — if the
  inference is cheap enough — as an in-process provider behind the same
  `ASRProvider` interface. Both paths are open.

## Alternatives considered

- **Sub-process sidecar managed by backend**. Backend would spawn a child
  Python process via `subprocess` + JSON-RPC over stdin/stdout. Rejected
  — lifecycle is fiddly (heartbeat, restart, signal handling) and the
  failure mode where backend crashes leaves an orphan child.
- **gRPC bidirectional streaming**. Better typed contracts, no
  meaningful throughput gain on localhost. Rejected — no protobuf
  toolchain elsewhere in the repo, and the cost of bringing one in
  outweighs the benefit at single-user scale.
- **Unix domain socket RPC**. Fast on localhost but worse cross-platform
  story. Rejected — saves ~1 ms per chunk, not worth the operational
  divergence.
- **Keep Whisper as the fallback engine**. Whisper Large v3 doesn't run
  fast enough on Sean's machine to use day-to-day; small variants don't
  meet the WER bar (per ADR-0028 numbers). Rejected — empty fallback
  isn't a fallback.

## Migration

Historical meeting rows persisted with `asr_provider = "whisper"` continue
to load. The factory at
`packages/backend/meeting_playbook/asr/factory.py::_coerce_provider_name`
emits a `structlog.warning` with `from_value=whisper, to_value=qwen3` and
returns a `RemoteAsrRuntimeClient` instance. No Alembic migration changes
the DB value — the historical column records what engine generated those
transcripts at the time and is left intact.

If the runtime is not running (env var missing or service down), the
factory raises `AsrRuntimeUnavailableError`. The session router turns
that into an `asr.runtime_unavailable` error frame and closes the
WebSocket cleanly so the user sees a structured error instead of a
generic connection drop.

## References

- Spectra change: `openspec/changes/asr-runtime-extraction/` (proposal +
  design + specs + tasks).
- New capability spec: `openspec/specs/asr-runtime/spec.md`.
- Related ADRs: 0005 (ASRProvider keystone), 0026, 0028, 0029.
