# ADR-0014: WebSocket for backend ↔ frontend realtime

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The in-meeting experience requires:
- Live transcript chunks streamed from backend to frontend (~10s cadence).
- The frontend pushing "Get Advice" requests and chatbox messages.
- The backend pushing tactical advisor responses (potentially streaming token-by-token).

## Decision
Use WebSocket for the in-meeting session. Message format: JSON with a `type` discriminator field, e.g.:

```
{"type": "transcript_chunk", "data": {...}}
{"type": "advice_request", "data": {...}}
{"type": "advice_chunk", "data": {...}}
{"type": "advice_done", "data": {...}}
```

One WebSocket per active meeting; closed when the meeting ends.

Pre-meeting (Calendar fetch, playbook generation) and post-meeting (summary generation) operations remain regular HTTP — they are request/response with no streaming need.

## Consequences
- The auth gateway (Bun.serve, ADR-0021) must proxy WebSocket upgrades to the FastAPI backend.
- A discriminated union type for messages lives in a shared TS schema; the Python side mirrors it (manually for now; codegen later if it churns).

## Alternatives considered
- **Server-Sent Events** — one-directional only; the bidirectional advisor flow makes WS the cleaner fit.
- **HTTP polling** — wasteful; would feel laggy for the live transcript.
