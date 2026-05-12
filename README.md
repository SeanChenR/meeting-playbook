<p align="center">
  <img src="assets/meeting-playbook-logo.png" alt="meeting-playbook logo" width="180" />
</p>

<h1 align="center">meeting-playbook</h1>

<p align="center">
  Personal AI meeting assistant — pre-meeting <strong>playbook</strong>, in-meeting realtime transcription with <strong>tactical advisor</strong>, post-meeting summary with action items.
</p>

<p align="center">
  <a href="#english">English</a> · <a href="#繁體中文">繁體中文</a>
</p>

---

<a id="english"></a>

## English

Inspired by [yu-wenhao.com/zh-TW/blog/ai-meeting-notes](https://yu-wenhao.com/zh-TW/blog/ai-meeting-notes/).

### Status

Active personal project — 11 vertical slices shipped (auth, i18n, meeting CRUD, playbook editor, calendar + LLM playbook generation, mic transcript session, dual-stream capture, tactical advisor, advisor chatbox, post-meeting summary, ASR + retention) plus a UI overhaul (claude-design dual-theme), animate-ui icon swap, and meetings UX revamp.

See `openspec/specs/` for live capability specs, `openspec/changes/archive/` for completed change history, and `docs/adr/` for architectural decisions.

### Stack

- **Frontend**: React + Vite + Bun + shadcn/ui + Tailwind + i18n (zh-TW + en) + dual-theme claude-design
- **Auth**: Bun.serve + Better Auth (Google OAuth + TOTP 2FA)
- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic
- **DB**: PostgreSQL
- **Audio**: BlackHole 2ch dual-stream capture
- **ASR**: faster-whisper (local) + Qwen3-ASR (local-first via MPS, cloud fallback)
- **LLM**: Vertex AI — Gemini Flash (realtime tactical advisor) + Gemini 2.5 Pro (summary + playbook generation)

### First-time setup

These steps are one-time. Once done, daily development is just `bun run dev`.

#### 1. macOS prerequisites

```bash
brew install postgresql@16
brew services start postgresql@16

curl -fsSL https://bun.sh/install | bash         # Bun (TS runtime + package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh  # uv (Python package manager)

brew install blackhole-2ch                        # Dual-stream audio capture
```

#### 2. Create the local database

```bash
createdb meeting_playbook
```

#### 3. Configure GCP — OAuth Web Client + Vertex AI project

In the Google Cloud Console:

1. Create (or pick) a GCP project.
2. Enable the **OAuth consent screen** (External, set yourself as a test user).
3. Create an **OAuth 2.0 Client ID** of type **Web application**:
   - Authorized JavaScript origin: `http://localhost:3001`
   - Authorized redirect URI: `http://localhost:3001/api/auth/callback/google` (exact port matters)
4. Copy the **Client ID** and **Client secret**.
5. Enable the **Vertex AI API** and create a service-account JSON key (required for playbook generation, advisor, and summary).

#### 4. Environment file

```bash
cp .env.example .env
```

Fill in:

- `BETTER_AUTH_SECRET` — generate with `openssl rand -base64 32`
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` — from step 3
- `BETTER_AUTH_URL` — leave as `http://localhost:3001`
- `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEX_PROJECT`, `VERTEX_LOCATION` — from step 3.5

#### 5. Install dependencies

```bash
bun install
(cd packages/backend && uv sync)
```

#### 6. Initialize Better Auth schema

```bash
bunx @better-auth/cli generate --y
bunx @better-auth/cli migrate --y
```

#### 7. Run Alembic migrations

```bash
(cd packages/backend && uv run alembic upgrade head)
```

#### 8. First TOTP enrollment

```bash
bun run dev
# Open http://localhost:3001 in Chrome
# 1. Click "Sign in with Google"
# 2. Scan the TOTP QR code with Authy / Google Authenticator / 1Password
# 3. Enter the 6-digit code → land on /home
```

### Daily development

```bash
bun run dev
```

Starts three processes via `concurrently` with color-tagged logs:

- **web** (blue) — Vite dev server, <http://localhost:5173>
- **auth** (green) — Bun.serve gateway with Better Auth, <http://localhost:3001>
- **backend** (yellow) — FastAPI, <http://localhost:8000> (localhost-bound, only reachable through the gateway, per ADR-0021)

Open <http://localhost:3001> in the browser — the gateway is the canonical origin.

### Tests

```bash
bun run test                              # TS (bun test) + Python (pytest) in parallel
bun --filter @meeting-playbook/web test   # web only
(cd packages/backend && uv run pytest)    # backend only
```

### Layout

```
packages/
  web/      — React frontend (Vite, port 5173)
  auth/     — Better Auth + API gateway (Bun.serve, port 3001)
  backend/  — FastAPI service (port 8000)
docs/
  adr/      — Architecture Decision Records
openspec/
  specs/    — live capability specs
  changes/  — Spectra change proposals (+ archive/)
CONTEXT.md  — domain language, project goals
CLAUDE.md   — instructions for AI assistants
```

### License

Private. Not for redistribution.

---

<a id="繁體中文"></a>

## 繁體中文

個人 AI 會議助理 — 會前自動產出 **playbook**、會中即時逐字稿加 **tactical advisor**、會後摘要與行動項目。

靈感來自 [yu-wenhao.com/zh-TW/blog/ai-meeting-notes](https://yu-wenhao.com/zh-TW/blog/ai-meeting-notes/)。

### 目前狀態

個人持續開發中 — 已完成 11 個 vertical slice（auth、i18n、會議 CRUD、playbook 編輯器、Google Calendar 整合 + LLM playbook 生成、麥克風逐字稿、雙聲道擷取、tactical advisor、advisor 聊天框、會後摘要、ASR + 30 天 retention），加上 UI 全面改版（claude-design 雙主題）、animate-ui icon 換裝、會議列表 UX 重整。

`openspec/specs/` 是當前能力規格、`openspec/changes/archive/` 是已完成的 change 歷史、`docs/adr/` 是架構決策。

### 技術棧

- **前端**：React + Vite + Bun + shadcn/ui + Tailwind + i18n（繁中預設 + 英文）+ 雙主題 claude-design
- **驗證**：Bun.serve + Better Auth（Google OAuth + TOTP 雙因子）
- **後端**：Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic
- **資料庫**：PostgreSQL
- **錄音**：BlackHole 2ch 雙聲道擷取
- **ASR**：faster-whisper（本機）+ Qwen3-ASR（本機優先走 MPS、失敗時回退雲端）
- **LLM**：Vertex AI — Gemini Flash（即時 tactical advisor）+ Gemini 2.5 Pro（摘要與 playbook 生成）

### 初次設定

以下步驟只需做一次，之後日常開發只要 `bun run dev`。

#### 1. macOS 前置

```bash
brew install postgresql@16
brew services start postgresql@16

curl -fsSL https://bun.sh/install | bash         # Bun（TS 執行環境 + 套件管理）
curl -LsSf https://astral.sh/uv/install.sh | sh  # uv（Python 套件管理）

brew install blackhole-2ch                        # 雙聲道錄音必裝
```

#### 2. 建立本機資料庫

```bash
createdb meeting_playbook
```

#### 3. 設定 GCP — OAuth Web Client + Vertex AI

到 Google Cloud Console：

1. 建立（或挑一個）GCP 專案。
2. 啟用 **OAuth 同意畫面**（External，把自己加為測試使用者）。
3. 建立 **Web 應用程式** 類型的 **OAuth 2.0 用戶端 ID**：
   - Authorized JavaScript origin：`http://localhost:3001`
   - Authorized redirect URI：`http://localhost:3001/api/auth/callback/google`（port 一定要對）
4. 複製 **Client ID** 與 **Client secret**。
5. 啟用 **Vertex AI API** 並建立 service account JSON key（playbook 生成、advisor、摘要都需要）。

#### 4. 環境變數

```bash
cp .env.example .env
```

填入：

- `BETTER_AUTH_SECRET` — 用 `openssl rand -base64 32` 產生
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` — 來自步驟 3
- `BETTER_AUTH_URL` — 本機開發保留 `http://localhost:3001`
- `GOOGLE_APPLICATION_CREDENTIALS`、`VERTEX_PROJECT`、`VERTEX_LOCATION` — 來自步驟 3.5

#### 5. 安裝相依套件

```bash
bun install
(cd packages/backend && uv sync)
```

#### 6. 初始化 Better Auth schema

```bash
bunx @better-auth/cli generate --y
bunx @better-auth/cli migrate --y
```

#### 7. 跑 Alembic migration

```bash
(cd packages/backend && uv run alembic upgrade head)
```

#### 8. 首次 TOTP 註冊

```bash
bun run dev
# 用 Chrome 打開 http://localhost:3001
# 1. 點「Sign in with Google」
# 2. 用 Authy / Google Authenticator / 1Password 掃描 TOTP QR code
# 3. 輸入 6 位數驗證碼 → 進入 /home
```

### 日常開發

```bash
bun run dev
```

透過 `concurrently` 同時起三個 process，各自有顏色標籤：

- **web**（藍）— Vite dev server，<http://localhost:5173>
- **auth**（綠）— Bun.serve gateway 配 Better Auth，<http://localhost:3001>
- **backend**（黃）— FastAPI，<http://localhost:8000>（只綁 localhost，僅透過 gateway 進入，見 ADR-0021）

瀏覽器請開 <http://localhost:3001>（gateway 是唯一正式入口）。

### 測試

```bash
bun run test                              # TS（bun test）+ Python（pytest）並行
bun --filter @meeting-playbook/web test   # 只跑 web
(cd packages/backend && uv run pytest)    # 只跑後端
```

### 檔案結構

```
packages/
  web/      — React 前端（Vite，port 5173）
  auth/     — Better Auth + API gateway（Bun.serve，port 3001）
  backend/  — FastAPI 服務（port 8000）
docs/
  adr/      — 架構決策記錄
openspec/
  specs/    — 當前能力規格
  changes/  — Spectra change proposal（含 archive/）
CONTEXT.md  — 領域語彙、專案目標
CLAUDE.md   — 給 AI 助手的說明
```

### 授權

私人專案，禁止重新散布。
