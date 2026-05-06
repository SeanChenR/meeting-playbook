# Meeting Playbook — Notes for Claude

## Read these first
- `CONTEXT.md` — project purpose, domain glossary, boundaries
- `docs/adr/` — every architectural decision; read the relevant ADRs before changing code in that area

## Domain glossary — use these exact terms in code, comments, and PRs
- **Playbook** (not "prep doc", "brief", "agenda")
- **Counterparty (對方)** / **Me (我方)** (not "speaker A/B", "host/guest")
- **Pre-meeting / In-meeting / Post-meeting** (not "before/during/after")
- **Tactical advisor** (not "AI suggestion", "assistant", "helper")
- **ASR Provider** (not "transcriber", "speech engine")
- **Dual-channel capture** (not "stereo recording")
- **Recording window** (the 30-day retention; not "TTL", "expiry")

## Workflow conventions (per user's global config)
1. New feature → invoke `grill-with-docs` first (CONTEXT.md + ADRs exist)
2. PRD → invoke `to-prd`
3. Issues → invoke `to-issues`
4. Implementation → invoke `tdd` (vertical slice, red-green-refactor)
5. Bugs → invoke `diagnose`
6. Architecture changes → invoke `improve-codebase-architecture`
7. Pause for confirmation before file edits unless trivially reversible

## Tech overview
- Monorepo: Bun workspaces + `concurrently` for parallel dev
- `packages/web` — React + Vite + Bun + shadcn/ui + Tailwind + react-i18next (zh-TW default + en)
- `packages/auth` — Bun.serve + Better Auth (Google OAuth + TOTP 2FA) using `pg.Pool` directly (no TS ORM); also the API gateway proxying non-auth `/api/*` to backend
- `packages/backend` — Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic + uv + ruff
- Storage: PostgreSQL — Better Auth manages user/session/account tables, Alembic manages business tables (meetings, transcripts, playbooks, recordings)
- Audio: BlackHole 2ch + microphone, captured in Python via `sounddevice`; two synchronized streams, no diarization
- ASR: pluggable `ASRProvider` interface; current implementations: faster-whisper (local) + VibeVoice-ASR (local-first via transformers+MPS, cloud fallback via HuggingFace Inference)
- LLM: Vertex AI via `google-genai` SDK — Gemini Flash for realtime tactical advisor, Gemini 2.5 Pro for summaries and playbook generation

## Test discipline
- Target 80%+ coverage
- Python: `pytest`
- TS: `bun test`
- ASR-related: integration tests must use real audio fixtures, not mocks (mocked ASR hides quality regressions)

## Lint / format
- Python: `ruff` (lint + format)
- TS: `oxlint` + `oxfmt`
- Pre-commit hooks via `lefthook`

## Things that are NOT yet implemented
- Anything beyond `CONTEXT.md`, `CLAUDE.md`, ADRs, and scaffolded config files
- Implementation begins after `to-prd` → `to-issues` → first `tdd` slice

## When in doubt
Read `CONTEXT.md` and the relevant ADR. If the answer isn't there, surface the question to the user before assuming.
