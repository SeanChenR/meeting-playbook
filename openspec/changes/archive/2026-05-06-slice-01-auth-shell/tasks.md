## 1. 環境與依賴

- [x] 1.1 [P] [AC-1] 新增 packages/web/package.json deps（react、react-dom、react-router、vite、better-auth、@types/react），執行 `bun install` 通過
- [x] 1.2 [P] [AC-1] 新增 packages/auth/package.json deps（better-auth、pg、@types/pg），執行 `bun install` 通過
- [x] 1.3 [P] [AC-2] 在 packages/backend/pyproject.toml 加 deps（fastapi、uvicorn、structlog、sqlalchemy[asyncio]、asyncpg、alembic、pydantic-settings、pytest-asyncio、httpx），執行 `uv sync` 通過
- [x] 1.4 [P] [AC-15] 寫 `.env.example` 內容 — 涵蓋 DATABASE_URL、BETTER_AUTH_SECRET、GOOGLE_OAUTH_CLIENT_ID、GOOGLE_OAUTH_CLIENT_SECRET、GOOGLE_APPLICATION_CREDENTIALS、VERTEX_AI_PROJECT、VERTEX_AI_LOCATION、BACKEND_URL、LOG_LEVEL，所有 placeholder 都要可辨識（如 `<from GCP console>`）

## 2. Backend baseline

- [x] 2.1 [P] [AC-12] 寫 structlog 設定（packages/backend/meeting_playbook/logging.py）：TTY-aware renderer。pytest 覆蓋兩個情境：(a) stderr 是 TTY 時用 ConsoleRenderer，(b) 非 TTY 時用 JSONRenderer
- [x] 2.2 [P] [AC-13] 寫 packages/backend/meeting_playbook/config.py：pydantic-settings Settings class 從 env 載入。pytest 覆蓋 missing required field 拋例外
- [x] 2.3 [AC-13] 寫 packages/backend/meeting_playbook/preflight.py：PostgreSQL ping + 必要 env vars 檢查。pytest 覆蓋每個 failure mode（DB 不通、env 缺、Vertex AI 缺只 warn）
- [x] 2.4 [AC-9][AC-10] 寫 FastAPI app 結構（packages/backend/meeting_playbook/server.py）：/api/health 與 /api/me。pytest 覆蓋 spec requirement「FastAPI backend trusts X-User-Id without re-validation」：(a) `GET /api/me` 帶 `X-User-Id: usr_abc` → 200 + body `{"user_id":"usr_abc"}`，(b) 沒帶 header → 401 + `error_code: auth.gateway_bypass`
- [x] 2.5 [P] [AC-2] 寫 Alembic baseline（packages/backend/alembic.ini + alembic/env.py + alembic/script.py.mako）：async engine 從 Settings.DATABASE_URL 取，target_metadata=None。`uv run alembic upgrade head` 無 op 通過

## 3. Auth gateway

- [x] 3.1 [AC-4] 寫 Better Auth 配置（packages/auth/src/auth.ts）：betterAuth() with pg.Pool、Google socialProvider、twoFactor plugin、session cookie httpOnly+sameSite=lax。bun test 覆蓋 createAuth() 不丟例外、handler 是 function
- [x] 3.2 [AC-5] 寫 Bun.serve fetch handler 結構（packages/auth/src/server.ts）— 實作 spec requirement「Gateway routes auth-namespace requests to Better Auth handler」：path 起頭 `/api/auth/` 直接交給 auth.handler。bun test 覆蓋 (a) `POST /api/auth/sign-in/social` 由 auth.handler 處理 (b) `POST /api/auth/two-factor/enable` 同樣交付
- [x] 3.3 [AC-9] 擴 server.ts 實作 spec requirement「Gateway authenticates non-auth /api/* requests」：path 起頭 `/api/` 但非 `/api/auth/` → `auth.api.getSession()` 驗證；無效或 expired → 401。bun test 覆蓋 (a) valid session 進 proxy 路徑 (b) 無 session 直接 401 (c) expired session 直接 401
- [x] 3.4 [AC-9] 擴 server.ts 實作 spec requirement「Gateway injects X-User-Id header on forwarded requests」：forward request 時 set `X-User-Id` from session.user.id，**覆寫** client-supplied 的同名 header。bun test 覆蓋 (a) 注入正確 user id (b) client 帶假的 X-User-Id 被蓋掉
- [x] 3.5 [AC-9] 擴 server.ts 實作 spec requirement「Forwarded requests preserve client request metadata」：preserve method / body / query / 其他 headers；strip Better Auth session cookie。bun test 覆蓋 POST body byte-equal、query 完整保留、Better Auth cookie 在 forwarded request 中不存在
- [x] 3.6 [AC-9] 擴 server.ts 實作 spec requirement「WebSocket upgrades carry X-User-Id」：對 non-auth /api/* 的 WS upgrade，proxy 給 FastAPI 時帶上 X-User-Id；無 session → 401 拒絕 upgrade。bun test 覆蓋 (a) 有效 session 的 WS upgrade 被 proxy (b) 無 session 的 upgrade 被 reject

## 4. Frontend 路由與 auth client

- [x] 4.1 [P] [AC-5] 建 Vite scaffold：packages/web/index.html、main.tsx、App.tsx、vite.config.ts（dev proxy `/api` → `http://localhost:3001`，含 `ws: true`）。bun test 覆蓋 App component renders without crash
- [x] 4.2 [P] [AC-5] 寫 packages/web/src/lib/auth-client.ts：createAuthClient({ baseURL: gateway origin })。bun test 覆蓋 client 物件結構 OK
- [x] 4.3 [AC-5][AC-11] 寫 packages/web/src/routes/login.tsx：「Sign in with Google」按鈕；onClick 呼叫 authClient.signIn.social({ provider: "google" })。bun test 覆蓋 click 觸發 social signin dispatch
- [x] 4.4 [P] [AC-6][AC-7] 寫 packages/web/src/routes/totp/enroll.tsx 與 totp/verify.tsx：QR code 顯示 + 6-digit input form；submit 呼叫對應 Better Auth client 方法。bun test 覆蓋 form submit dispatch
- [x] 4.5 [AC-8][AC-9] 寫 packages/web/src/routes/home.tsx：受保護路由 fetch `/api/me`，render「Hello, &lt;name&gt;」。bun test 覆蓋 with mocked /api/me response
- [x] 4.6 [AC-11] 在 home.tsx 加 logout 按鈕：呼叫 authClient.signOut()，redirect 去 `/login`。bun test 覆蓋 logout dispatch + redirect

## 5. End-to-end + onboarding docs

- [x] 5.1 [AC-3] 驗證 root dev script — 三 process 拓撲與 port 配置：concurrently 同時起 vite (5173)、bun.serve (3001)、fastapi (8000)，logs 上色標記。手動 smoke test 三 process 各自 reachable
- [x] 5.2 [AC-16] 寫 integration test：mocked OAuth callback 模擬完整登入流程，assert request 經 gateway 後到 FastAPI 帶 `X-User-Id`，`/api/me` 回對應 user_id
- [x] 5.3 [AC-14] 寫 README「First-time setup」section：GCP OAuth Web Client 步驟（含 redirect URI `http://localhost:3001/api/auth/callback/google`）、`createdb meeting_playbook`、env file 複製、Better Auth schema push 確切命令、`uv run alembic upgrade head`

## 6. 驗收

- [x] 6.1 對照 [GitHub Issue #2](https://github.com/SeanChenR/meeting-playbook/issues/2) 的 [agent brief](https://github.com/SeanChenR/meeting-playbook/issues/2#issuecomment-4386345972) 16 條 acceptance criteria 全打勾於 GitHub Issue
