<!-- SPECTRA:START v1.0.2 -->

# Spectra Instructions

This project uses Spectra for Spec-Driven Development(SDD). Specs live in `openspec/specs/`, change proposals in `openspec/changes/`.

## Use `/spectra-*` skills when:

- A discussion needs structure before coding → `/spectra-discuss`
- User wants to plan, propose, or design a change → `/spectra-propose`
- Tasks are ready to implement → `/spectra-apply`
- There's an in-progress change to continue → `/spectra-ingest`
- User asks about specs or how something works → `/spectra-ask`
- Implementation is done → `/spectra-archive`
- Commit only files related to a specific change → `/spectra-commit`

## Workflow

discuss? → propose → apply ⇄ ingest → archive

- `discuss` is optional — skip if requirements are clear
- Requirements change mid-work? Plan mode → `ingest` → resume `apply`

## Parked Changes

Changes can be parked（暫存）— temporarily moved out of `openspec/changes/`. Parked changes won't appear in `spectra list` but can be found with `spectra list --parked`. To restore: `spectra unpark <name>`. The `/spectra-apply` and `/spectra-ingest` skills handle parked changes automatically.

<!-- SPECTRA:END -->

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

## i18n convention (per Slice 2)

Every user-visible string in `packages/web` MUST live in BOTH locale files at
the same time:
- `packages/web/src/locales/zh-TW.json` (default, 繁中)
- `packages/web/src/locales/en.json` (English)

Reading: components import `useTranslation()` from `react-i18next` and call
`t("group.key")`. Backend errors arrive as `{error_code, message}`; the
frontend looks them up via `localizedErrorMessage(errorCode, t)` from
`packages/web/src/lib/i18n-errors.ts` (falls back to `errors.common.unknown`
when the code is not in the locale).

PR contract: a UI string added to one locale file but NOT the other is a
review block. The deep-equal test in `packages/web/src/locales/locales.test.ts`
catches drift in CI.

Minimum example — adding a new "save" button to the auth flow:
- `zh-TW.json`: `"auth": { "common": { "save": "儲存" } }`
- `en.json`:    `"auth": { "common": { "save": "Save"  } }`
- Component: `<Button>{t("auth.common.save")}</Button>`

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
- ASR: pluggable `ASRProvider` interface; current implementations: faster-whisper (local) + Qwen3-ASR (local-first via transformers+MPS, cloud fallback via HuggingFace Inference) — see ADR-0028
- LLM: Vertex AI via `google-genai` SDK — Gemini Flash for realtime tactical advisor, Gemini 2.5 Pro for summaries and playbook generation

## UI conventions (per ui-overhaul-claude-design)
- Dual-theme "claude-design": light = 紫羅蘭 (`--primary-hue: 280`), dark = 暖橘 (`--primary-hue-dark: 50`)
- All colors are `oklch()` CSS variables in `packages/web/src/index.css` — **no raw hex in component class strings**
- Animated icons live in `packages/web/src/components/animate-ui/icons/` (motion variants); plain shadcn / lucide icons for static use only
- Layout primitives: `<Pane>` (single column) composed inside `<Workspace>` (multi-pane). Reuse these instead of ad-hoc flex/grid
- Meetings list has 3 modes: Kanban / Calendar / List (shared `<MeetingsViewTabs>`)
- **No emoji in UI strings** — use an animate-ui icon or shadcn Badge instead

## Dev / test commands (run from repo root)
- `bun run dev` — web + auth + backend concurrently
- `bun run test` — all TS workspace tests + `pytest` (backend) in parallel
- `bun run lint` / `bun run format` — `oxlint` + `ruff`
- Web-only test: `bun --filter @meeting-playbook/web test`
- Backend-only test: `cd packages/backend && uv run pytest`

## Test discipline
- Target 80%+ coverage
- Python: `pytest`
- TS: `bun test`
- ASR-related: integration tests must use real audio fixtures, not mocks (mocked ASR hides quality regressions)

## Lint / format
- Python: `ruff` (lint + format)
- TS: `oxlint` + `oxfmt`
- Pre-commit hooks via `lefthook`

## Current state (read before assuming something is missing)
- 11 vertical slices + follow-up changes archived in `openspec/changes/archive/` — auth, i18n, meeting CRUD, playbook editor, calendar + LLM playbook, mic + transcript session, dual-stream + UI bundle, tactical advisor, advisor chatbox, post-meeting summary, ASR + retention, UI overhaul (claude-design), animate-ui swap, meetings UX revamp
- Live capability specs are in `openspec/specs/` — check there first to see what's already promoted
- New work is Spectra-managed: discuss → propose → apply → archive (see top of this file)

## When in doubt
Read `CONTEXT.md` and the relevant ADR. If the answer isn't there, surface the question to the user before assuming.
