# ADR-0023: Logging — structlog (Python) + console (TypeScript)

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
Local-first personal project. No remote log aggregation needed. Logs are for dev debugging and post-incident inspection on the user's own machine.

## Decision
- Python backend: `structlog` with a JSON renderer in non-TTY mode and a colorized console renderer in TTY.
- TypeScript packages: native `console.log` / `console.error` for dev; structured logging deferred until a real need arises.
- No Sentry / DataDog / Honeycomb. No log shipping.
- Logs go to stderr; the user can pipe to a file if needed.

## Consequences
- Zero external dependencies for observability.
- If we later deploy publicly, ADR revision can layer in a real logging backend.

## Alternatives considered
- **Sentry / Honeycomb** — overkill for one user on localhost.
- **stdlib logging only (Python)** — workable but loses the structured fields that make grep / jq useful.
