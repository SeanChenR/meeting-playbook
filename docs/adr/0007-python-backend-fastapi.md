# ADR-0007: Python 3.12 backend with FastAPI, uv, ruff

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
The backend handles audio capture (`sounddevice`), ASR (faster-whisper, transformers/MPS for VibeVoice-ASR), LLM calls (`google-genai`), and persistence. Most of the AI/audio ecosystem is Python-native. The user's stack preference for AI work is Python.

## Decision
- Language: Python 3.12
- Framework: FastAPI (async-native, excellent WebSocket support)
- Package manager: `uv`
- Lint + format: `ruff`
- Test runner: `pytest` (ADR-0011)
- ASGI server in dev: `fastapi dev` (uvicorn under the hood)

## Consequences
- All ML / audio code lives in Python with first-class library support.
- WebSocket endpoints (ADR-0014) co-locate cleanly with HTTP endpoints under FastAPI.
- The TS frontend communicates with the backend via the auth gateway proxy (ADR-0021), keeping cross-language wire format simple (JSON over WebSocket / HTTP).

## Alternatives considered
- **Bun + TypeScript backend** — would force ASR via cloud (no mature `faster-whisper` equivalent in TS) and split AI tooling away from the user's mental model.
- **Go backend** — clean but ML library support is weak; would still need Python sidecars for ASR.
