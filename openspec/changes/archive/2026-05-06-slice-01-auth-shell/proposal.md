> Source: GitHub Issue [#2](https://github.com/SeanChenR/meeting-playbook/issues/2) · [Agent Brief](https://github.com/SeanChenR/meeting-playbook/issues/2#issuecomment-4386345972)

## Why

MVP 的首個 vertical slice — bootstrap 三 process 架構（Vite + Bun.serve + FastAPI），驗證 auth gateway → X-User-Id 注入 → backend 的端到端契約能通。後續 12 個 slice 都建在這條 pipe 上，沒這片動不了。

## What Changes

- 新增 Bun.serve gateway，掛 Better Auth（Google OAuth + TOTP 2FA），對非 auth 的 /api/* 驗 session、注入 X-User-Id 後 proxy 給 FastAPI
- 新增 FastAPI app 提供 GET /api/me（回 user_id）+ healthcheck，logs 走 structlog；TTY 時 console renderer，否則 JSON
- 新增 React + Vite frontend，登入流程完成後顯示 "Hello, <name>"
- 啟動 pre-flight：PostgreSQL 連線 + 必要 env vars 缺什麼明確報錯
- 補齊 README「First-time setup」+ .env.example

## Non-Goals

- 業務 entity（meeting / playbook / transcript / audio / LLM）— 後續 slices
- 前端 i18n（Slice 2 / Issue #4）
- Calendar OAuth scope（Slice 5 / Issue #7）
- production hosting / TLS / domain
- rate limit、audit log、Better Auth 預設外的 CSRF
- 真打 Google OAuth 網路的測試（只 mocked callback）

## Capabilities

### New Capabilities

- `auth-gateway-contract`: Bun.serve 驗 Better Auth session、注入 X-User-Id header、proxy 給 FastAPI 的 ingress 契約；FastAPI 不自驗 auth。後續所有 slice 共用此邊界。

### Modified Capabilities

(none)

## Impact

- Affected specs: auth-gateway-contract（新）
- Affected code:
  - New:
    - packages/auth/src/server.ts
    - packages/auth/src/auth.ts
    - packages/auth/tsconfig.json
    - packages/web/src/main.tsx
    - packages/web/src/App.tsx
    - packages/web/src/routes/login.tsx
    - packages/web/src/routes/home.tsx
    - packages/web/src/lib/auth-client.ts
    - packages/web/index.html
    - packages/web/vite.config.ts
    - packages/web/tsconfig.json
    - packages/backend/meeting_playbook/server.py
    - packages/backend/meeting_playbook/logging.py
    - packages/backend/meeting_playbook/preflight.py
    - packages/backend/meeting_playbook/config.py
    - packages/backend/alembic.ini
    - packages/backend/alembic/env.py
    - packages/backend/alembic/script.py.mako
    - packages/backend/tests/test_api_me.py
    - packages/auth/src/__tests__/gateway.test.ts
    - .env.example
  - Modified:
    - packages/web/package.json
    - packages/auth/package.json
    - packages/backend/pyproject.toml
    - README.md
  - Removed: (none)
- Dependencies (TS): better-auth, pg, react, react-dom, react-router, vite
- Dependencies (Python): fastapi, uvicorn, structlog, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings
