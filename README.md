# meeting-playbook

Personal AI meeting assistant — pre-meeting playbook generation, in-meeting realtime transcription with tactical advisor, post-meeting summary with action items.

Inspired by [yu-wenhao.com/zh-TW/blog/ai-meeting-notes](https://yu-wenhao.com/zh-TW/blog/ai-meeting-notes/).

## Status
Greenfield. See `docs/adr/` for decisions and `CONTEXT.md` for project goals.

## Stack
- **Frontend**: React + Vite + Bun + shadcn/ui + Tailwind + i18n (zh-TW + en)
- **Auth**: Bun.serve + Better Auth (Google OAuth + TOTP 2FA)
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic
- **DB**: PostgreSQL
- **Audio**: BlackHole 2ch dual-stream capture
- **ASR**: faster-whisper (local) + VibeVoice-ASR (local-first, cloud fallback)
- **LLM**: Vertex AI — Gemini Flash (realtime) + Gemini 2.5 Pro (summary / playbook gen)

## Prerequisites (one-time)
1. macOS (Apple Silicon)
2. PostgreSQL: `brew install postgresql@16 && brew services start postgresql@16`
3. BlackHole: `brew install blackhole-2ch`, then in Audio MIDI Setup create a Multi-Output Device routing to both speakers and BlackHole
4. GCP project with Vertex AI + Google Calendar API enabled
5. Bun: `curl -fsSL https://bun.sh/install | bash`
6. uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Quick start
```bash
bun install
cd packages/backend && uv sync && cd ../..
bun run dev
```

This starts three processes via concurrently:
- Vite dev server (frontend) — http://localhost:5173
- Bun.serve auth + API gateway — http://localhost:3001
- FastAPI backend — http://localhost:8000

## Layout
```
packages/
  web/      — React frontend (Vite, port 5173)
  auth/     — Better Auth + API gateway (Bun.serve, port 3001)
  backend/  — FastAPI service (port 8000)
docs/
  adr/      — Architecture Decision Records
CONTEXT.md  — domain language, project goals
CLAUDE.md   — instructions for AI assistants
```

## License
Private. Not for redistribution.
