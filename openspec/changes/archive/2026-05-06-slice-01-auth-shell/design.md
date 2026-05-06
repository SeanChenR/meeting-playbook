## Context

這是 meeting-playbook MVP 的第一個 vertical slice。目標：bootstrap 三 process localhost 架構（Vite + Bun.serve + FastAPI），跑通 Better Auth Google OAuth + TOTP 2FA 登入，驗證從 browser → gateway → backend 的 X-User-Id 注入合約。

**為什麼是這個架構**：
- ADR-0021 規定 Bun.serve 是唯一 ingress，FastAPI 不自驗 auth
- ADR-0025 規定 Better Auth 直接吃 `pg.Pool`，不引入 TS ORM
- ADR-0012 規定 PostgreSQL + SQLAlchemy 2.0 async + Alembic
- ADR-0007 / ADR-0008 規定 backend Python / frontend React+Bun
- ADR-0013 規定 monorepo + concurrently dev

**目前狀態**（slice 開始前）：
- repo 只有 scaffold（root `package.json`、`packages/{web,auth,backend}/` 三個空 package、`docs/adr/` 25 條 ADR、`CONTEXT.md`、`CLAUDE.md`、Spectra config）
- 沒有任何實作 code，dev 啟動只會印 placeholder

**Constraints**：
- 必須在 macOS（Apple Silicon）上跑通；Sean 開發機是 M3 Pro 18GB
- PostgreSQL 已透過 Homebrew 安裝（`brew services start postgresql@16`）
- 必須走 mocked OAuth callback 做 integration test，不打 Google 真實網路

**Stakeholders**：Sean（單一使用者）；未來可能 deploy。

## Goals / Non-Goals

**Goals**：
- 跑通 Google OAuth + TOTP 2FA 登入
- 驗證 X-User-Id 注入合約 end-to-end
- 為後續 12 個 slice 奠定 ingress 模式
- 所有依賴都從 `.env.example` + README 一次到位、onboarding 文件齊備

**Non-Goals**（mirror agent brief 的 Out of scope）：
- 任何業務 entity（meeting、playbook、transcript）
- 前端 i18n（Slice 2）
- Calendar OAuth scope（Slice 5）
- production hosting / TLS / rate limit / audit log
- 真打 Google OAuth 網路測試
- cross-browser 測試（只目標 Chrome latest）

## Decisions

### 三 process 拓撲與 port 配置

```
[Browser] ──┐
            ├─→ http://localhost:3001 (Bun.serve, gateway)
            │     ├── /api/auth/*  → Better Auth handler
            │     └── /api/*       → fetch(http://localhost:8000${path}, headers + X-User-Id)
            │
            └─→ http://localhost:5173 (Vite dev server, frontend with HMR)
                  └── proxy /api/* → http://localhost:3001

[FastAPI]   ←── http://localhost:8000  (only Bun gateway calls here, bound to 127.0.0.1)
              └── /api/me, /api/health
```

Dev mode：3 個 process 由 root 的 dev script 透過 `concurrently` 起，logs 用 `-n web,auth,backend -c blue,green,yellow` 上色。Prod mode（未來）：2 個 process（Bun 同時 serve `packages/web/dist/` + auth + proxy；FastAPI 單獨）。

**Alternatives**：把 Vite 跟 Better Auth 合進同一個 Bun process（用 `vite.createServer({ middlewareMode: true })` 嵌進 fetch handler）— 拒絕，dev mode HMR 設定複雜度上升、debug 困難；3 process 是 dev 階段最透明的選擇。

### Bun.serve fetch handler 結構

`packages/auth/src/server.ts` 實作以下流程：

1. 解析 URL；若 path 以 `/api/auth/` 開頭 → 直接呼叫 Better Auth 的 `auth.handler(req)` 並回傳
2. 若 path 以 `/api/` 開頭（且非 auth）→ 呼叫 `auth.api.getSession({ headers: req.headers })` 驗 session；無效或 expired 直接回 401
3. 重組 headers：strip Better Auth session cookie，set `X-User-Id: <session.user.id>`（覆蓋任何 client-supplied 值）
4. 用 `fetch()` 將 request 轉送到 `process.env.BACKEND_URL ?? "http://localhost:8000"`，preserve method / body / query
5. 其他 path 回 404

WebSocket upgrade 在 Slice 1 不需要實作（下一個用到 WS 的是 Slice 6 mic-transcript），但 fetch handler 的結構必須能擴展支援，避免之後改架構。

### Better Auth 配置

`packages/auth/src/auth.ts` 匯出 `createAuth()`，以 `pg.Pool` 直接接 PostgreSQL（不引入 ORM，per ADR-0025）。
- `socialProviders.google` 配置 client id / secret
- `plugins: [twoFactor()]` 啟用 TOTP
- `session.cookieOptions`: dev 用 `secure: false`，prod 切 `true`；`httpOnly: true`、`sameSite: "lax"` 不變

**Schema 初始化**：Better Auth 提供 CLI（`@better-auth/cli generate` + `migrate` 流程），README 的「First-time setup」記載對應命令。Schema 由 Better Auth 管，Alembic 不碰任何 auth-related 表。

**Alternatives**：使用 Drizzle / Prisma adapter — 拒絕，違反 ADR-0025（不引入 TS ORM）。

### FastAPI app 結構

`packages/backend/meeting_playbook/server.py` 提供：
- `GET /api/health` 回 `{"status": "ok"}` 不檢查 auth（給 deploy probe 用）
- `GET /api/me` 從 `X-User-Id` header 取值；若 header missing → 401 with `{"error_code": "auth.gateway_bypass"}`

`config.py` 用 `pydantic-settings` 讀 env vars。`preflight.py` 在 app startup 跑：
- PostgreSQL 連線測試（用 asyncpg ping）
- 必填 env vars 檢查：`DATABASE_URL`、`BETTER_AUTH_SECRET`、`GOOGLE_OAUTH_CLIENT_ID`、`GOOGLE_OAUTH_CLIENT_SECRET`
- Vertex AI env vars 缺只 warn，不 fail（Slice 5+ 才用到）

FastAPI bind `127.0.0.1:8000` 不 listen `0.0.0.0`，避免被網路上其他主機繞過 gateway 直接打。

**Alternatives**：把 X-User-Id 驗證做成 FastAPI middleware — v1 用 `Header` dependency 即可，過度抽象等真的有第二個 endpoint 需要再說。

### structlog 設定

`packages/backend/meeting_playbook/logging.py` 在 startup 呼叫 `setup_logging()`：
- TTY → `structlog.dev.ConsoleRenderer()` 上色給 dev 看
- 非 TTY → `structlog.processors.JSONRenderer()` 給未來 log shipping
- 預設 INFO 等級；DEBUG 由 env var `LOG_LEVEL` 覆蓋

每個 log 帶 `timestamp`、`level`、`logger_name` 三個基本欄位。

### Alembic baseline

`packages/backend/alembic/env.py` 配置 async engine（用 `Settings().DATABASE_URL`）+ `target_metadata = None`（Slice 1 無 app table）。`alembic.ini` 的 `sqlalchemy.url = ` 留空，env.py 從 settings 載入。

第一個真實 migration 會在 Slice 3（Meeting CRUD）出現。Slice 1 只跑 `alembic upgrade head` 確認 wire 通，會 no-op。

### Frontend 路由與 auth client

`packages/web` 路由（用 `react-router`）：
- `/` → 已登入 redirect 去 `/home`，未登入 redirect 去 `/login`
- `/login` → 顯示「Sign in with Google」按鈕，按下去呼叫 Better Auth client 的 `signIn.social({ provider: "google" })`
- `/totp/enroll` → 第一次登入後，顯示 QR code + 確認輸入 6 位數 code
- `/totp/verify` → 既有 user 後續登入，輸入 6 位數 code
- `/home` → 受保護路由，呼叫 `GET /api/me`，顯示「Hello, &lt;Google display name&gt;」+ 登出按鈕

`packages/web/src/lib/auth-client.ts` 用 Better Auth React client，`baseURL` 指向 gateway origin（`http://localhost:3001`）。

`packages/web/vite.config.ts` 設 dev proxy：所有 `/api/*` 轉發到 `http://localhost:3001`。讓 Vite (5173) 上的 frontend 對 `/api/*` 的呼叫都透過 gateway，跟 prod mode 行為一致。

### `.env.example` 內容

```
DATABASE_URL=postgresql://localhost:5432/meeting_playbook
BETTER_AUTH_SECRET=  # generate via openssl rand -base64 32
GOOGLE_OAUTH_CLIENT_ID=  # from GCP console OAuth Web Client
GOOGLE_OAUTH_CLIENT_SECRET=  # from GCP console OAuth Web Client
GOOGLE_APPLICATION_CREDENTIALS=  # placeholder, 後續 slice 用到 Vertex AI 才填
VERTEX_AI_PROJECT=  # placeholder
VERTEX_AI_LOCATION=us-central1  # placeholder
BACKEND_URL=http://localhost:8000
LOG_LEVEL=INFO
```

## Risks / Trade-offs

[Risk] Better Auth schema 跟 Alembic 共用同一個 DB，未來 migration order 出錯可能拿不到 `user.id`
→ Mitigation：README 記載初始化順序：先 Better Auth schema push（建 user 表），再 `uv run alembic upgrade head`（業務表 FK user.id）。Slice 3 加業務表時嚴格檢查 FK。

[Risk] X-User-Id 信任模型若 backend 直接暴露給網路就破功
→ Mitigation：FastAPI 預設 bind `127.0.0.1:8000` 不 listen `0.0.0.0`；README 警示不可改；spec 已要求「missing X-User-Id 必須回 401」。

[Risk] TOTP 2FA 在 dev 反覆登入很煩
→ Mitigation：Better Auth `twoFactor()` 支援 trusted device flag，可選擇開；v1 不做。dev 一次掃 QR 之後 session 會延續到 cookie expire 為止。

[Risk] Google OAuth client redirect URI 錯誤是 onboarding 最常見問題
→ Mitigation：README「First-time setup」明確列出 redirect URI 必須是 `http://localhost:3001/api/auth/callback/google`，改 port 要同步改 GCP。

[Risk] Bun + Vite + Python 三 process 啟動順序若 Bun 還沒準備好 frontend 就連會報錯
→ Mitigation：Vite dev server 預設會 retry proxy；`concurrently --kill-others-on-fail` 讓單一 process 死掉時不會殭屍化。

[Risk] FastAPI startup pre-flight 失敗訊息可能不夠明確讓 onboarding 痛苦
→ Mitigation：每個檢查項失敗時 raise `RuntimeError` 帶具體缺什麼（變數名 / 連線字串）+ 怎麼修的提示。

## Migration Plan

這是 greenfield slice，無 migration。第一次部署步驟（記載在 README）：

1. `brew install postgresql@16 && brew services start postgresql@16`
2. `createdb meeting_playbook`
3. 複製 `.env.example` 成 `.env` 並填入 GCP OAuth client + secret
4. GCP Console 建 OAuth Web Client，redirect URI 設 `http://localhost:3001/api/auth/callback/google`
5. `bun install`
6. `cd packages/backend && uv sync`
7. Better Auth schema push 命令（README 記載確切指令）建立 user / session / account / verification / 2FA 相關表
8. `cd packages/backend && uv run alembic upgrade head`（baseline，no-op）
9. 從 root 啟動 dev script
10. 開瀏覽器 `http://localhost:3001`，點 Google sign-in，掃 TOTP QR，落到 `/home` 看到 Hello

**Rollback**：
- DB 端 `dropdb meeting_playbook && createdb meeting_playbook` 重來
- Code 端 `git revert` 即可

## Open Questions

- **Better Auth 推薦的 schema push 命令**：是 `@better-auth/cli generate + migrate` 還是直接 SQL? 寫 README 時實測確認。
- **Vite proxy 對 SSE / WS 的支援**：Slice 1 不需要 WS，但 Slice 6 會。預先確認 vite proxy 是否需要 `ws: true` 設定。
- **Bun 的 hot reload 對 `packages/auth`**：用 `bun --watch` 還是其他方式？實測哪個比較穩，README 記下。
