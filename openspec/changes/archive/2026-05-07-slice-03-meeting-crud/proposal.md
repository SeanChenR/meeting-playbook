## Why

GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/5
Agent Brief: https://github.com/SeanChenR/meeting-playbook/issues/5#issuecomment-4386426085

Slice 1（auth shell）與 Slice 2（i18n foundation）已完成；登入後使用者只看到 `Hello, <name>` 頁面，系統尚未有任何「Meeting」概念。後續每一個 vertical slice（playbook、transcript、audio、advisor）都需要 FK 到 Meeting，因此先把 Meeting 的資料層、REST 與 UI 端到端立起來，是接下來所有功能的前置條件。

## What Changes

- 新增 `meeting` table（Alembic migration），FK 到 Better Auth 的 `user.id`，含 title、counterparty/me 雙顯示名稱、status enum、ASR provider 偏好、可空 calendar_event_id、時間戳。
- FastAPI 新增 `POST/GET list/GET id/DELETE /api/meetings`，全部以 `X-User-Id` 為授權主體；他人資料一律回 404（不洩漏存在）。
- 新增 `MeetingRepository`（SQLAlchemy 2.0 async），所有後續 slice 透過此模組存取 meeting。
- React 新增 `/meetings`（list）、`/meetings/new`（form）、`/meetings/:id`（detail+delete）三個 route，串 i18n 字串到 `zh-TW.json` 與 `en.json`。

## Non-Goals

- 編輯既有 meeting（無 PATCH，僅 create-only）。
- Playbook / transcript / audio / advisor 等子實體（後續 slice）。
- Status 從 `scheduled` 進入 `in_progress`/`completed` 的轉移（Slice 6）。
- Calendar event 連結填值（Slice 5）。
- 列表分頁、搜尋、批次操作。

## Capabilities

### New Capabilities

- `meeting-management`: Meeting 實體生命週期、擁有者隔離、雙顯示名稱、status / ASR provider 預設值與唯一存取路徑（MeetingRepository）。

### Modified Capabilities

（無）

## Impact

- 新檔：`packages/backend/alembic/versions/<rev>_create_meeting.py`、`packages/backend/meeting_playbook/meetings/{models,repository,router,schemas}.py`、`packages/web/src/routes/meetings/{list,new,detail}.tsx`、相關測試與 i18n key。
- 修改：`packages/backend/meeting_playbook/server.py`（掛載 router）、`packages/web/src/App.tsx`（route table）、`packages/web/src/i18n/locales/{zh-TW,en}.json`。
- 依賴：沿用現有 `auth-gateway-contract`（`X-User-Id` header）；無新套件。
