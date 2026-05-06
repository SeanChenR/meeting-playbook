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

## First-time setup

These steps are one-time. Once done, daily development is just `bun run dev`.

### 1. macOS prerequisites

```bash
# PostgreSQL 16
brew install postgresql@16
brew services start postgresql@16

# Bun (TypeScript runtime + package manager)
curl -fsSL https://bun.sh/install | bash

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# BlackHole 2ch — used by Slice 7 for dual-stream audio capture; install
# now to avoid blocking later. Configuration steps live in
# docs/BLACKHOLE_SETUP.md (added when Slice 7 lands).
brew install blackhole-2ch
```

### 2. Create the local database

```bash
createdb meeting_playbook
```

### 3. Configure GCP — OAuth Web Client + Vertex AI project

In the Google Cloud Console:

1. Create (or pick) a GCP project.
2. Enable the **Google Cloud OAuth consent screen** (External, set yourself as a test user).
3. Create an **OAuth 2.0 Client ID** of type **Web application**:
   - Authorized JavaScript origin: `http://localhost:3001`
   - Authorized redirect URI: `http://localhost:3001/api/auth/callback/google` (this exact value — port matters)
4. Copy the **Client ID** and **Client secret**.
5. (Optional, for Slice 5+) Enable the **Vertex AI API** and create a service account JSON key.

### 4. Environment file

```bash
cp .env.example .env
```

Then edit `.env` and fill in:

- `BETTER_AUTH_SECRET` — generate with `openssl rand -base64 32`
- `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` — from step 3
- `BETTER_AUTH_URL` — leave as `http://localhost:3001` for local dev

The Vertex AI placeholders can stay empty until Slice 5.

### 5. Install dependencies

```bash
bun install
(cd packages/backend && uv sync)
```

### 6. Initialize the Better Auth schema

Better Auth manages its own user / session / account / verification / 2FA tables. From the repo root:

```bash
bunx @better-auth/cli generate --y
bunx @better-auth/cli migrate --y
```

(See <https://www.better-auth.com/docs/concepts/cli> for the latest flags. The `--y` skips interactive prompts.)

### 7. Run the Alembic baseline (no-op for Slice 1)

```bash
(cd packages/backend && uv run alembic upgrade head)
```

This is a no-op today (no application tables yet). Slice 3 introduces the first real migration.

### 8. First TOTP enrollment

```bash
bun run dev
# Open http://localhost:3001 in Chrome
# 1. Click "Sign in with Google" → complete the Google consent screen
# 2. Scan the TOTP QR code with Authy / Google Authenticator / 1Password
# 3. Enter the 6-digit code → land on /home and see "Hello, <your name>"
```

## Daily development

```bash
bun run dev
```

This starts three processes via `concurrently` with color-tagged logs:

- **web** (blue) — Vite dev server, frontend, <http://localhost:5173>
- **auth** (green) — Bun.serve gateway with Better Auth, <http://localhost:3001>
- **backend** (yellow) — FastAPI, <http://localhost:8000> (bound to localhost only — never reachable from the network; the gateway is the sole ingress, per ADR-0021)

In a browser, open <http://localhost:3001> (the gateway origin). The Vite dev server at 5173 also works during HMR but proxies API calls back to the gateway anyway.

## Tests

```bash
bun run test          # runs both bun test (TS) and pytest (Python) in parallel
bun --filter '*' test # TS only
(cd packages/backend && uv run pytest) # Python only
```

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
