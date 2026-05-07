- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/6
- Agent Brief：https://github.com/SeanChenR/meeting-playbook/issues/6#issuecomment-4386426380

## Why

Slice 3 已落地 Meeting CRUD，但 detail 頁只看得到 metadata。每場 meeting 都需要一份「playbook」承載會前準備（目標 / 對方輪廓 / 預期主題 / 預期反對 / 談話要點 / 紅線），且這份 playbook 是後續 slice 的基石：Slice 5 用 LLM 自動生成、Slice 6 advisor 在會中讀它做決策、Slice 8 在會議室畫面顯示。本 slice 先把資料層 + 編輯器立起來，使用者可以手動填，不依賴 LLM。

## What Changes

- 新增 `playbook` table（Alembic migration），FK → `meeting.id` ON DELETE CASCADE，含 `free_form_markdown` 與六個結構化欄位（皆為 markdown text）+ `updated_at`；UNIQUE(meeting_id) 確保一場會議至多一份
- FastAPI 兩個 endpoint：
  - `GET /api/meetings/{id}/playbook` — 不存在時自動建立空 row 後回傳，永遠 200（不會 404）
  - `PUT /api/meetings/{id}/playbook` — full upsert，所有欄位選填，缺漏視為空字串
- 兩個 endpoint 都先過 meeting ownership：他人 meeting 仍回 404（不洩漏存在）
- 新增 `PlaybookRepository`（async SQLAlchemy 2.0），暴露 `get_or_create_for_meeting` / `upsert_for_meeting`
- React `PlaybookPane` 元件：view-mode toggle（free-form ↔ structured），切換不丟失未存檔內容；free-form 用 `<textarea>`（v1 簡單方案）；structured 顯示六個 labeled markdown textarea
- 從 `/meetings/:id` detail 頁串到 PlaybookPane（同頁 inline 或 sub-route，由 design 決定）
- 「儲存」按鈕呼叫 PUT；保留 auto-save on blur 的擴充空間但不強制
- TanStack Query：`playbookQueryOptions(meetingId)` + `useUpsertPlaybookMutation`，存後 invalidate `["playbook", meetingId]`
- i18n keys 雙語齊備（zh-TW + en）

## Non-Goals

- LLM 自動生成 playbook 內容（Slice 5 / Issue #7）
- Versioning / undo / history（只保留最新存檔）
- 即時協作 / 多人同時編輯
- 會議進行中即時同步 playbook（Slice 8 / Issue #10 在會議室顯示）
- Side-by-side markdown preview（in-place 編輯就夠 v1）
- Templating system（一律從空 record 開始）

## Capabilities

### New Capabilities

- `playbook-management`: playbook 實體生命週期、與 meeting 的 1:1 關係、雙視圖（free-form markdown + 六結構化欄位）的存讀契約、ownership-via-meeting 的授權鏈

### Modified Capabilities

(無)

## Impact

- 新檔：
  - `packages/backend/alembic/versions/0002_create_playbook.py`
  - `packages/backend/meeting_playbook/playbooks/__init__.py`
  - `packages/backend/meeting_playbook/playbooks/models.py`
  - `packages/backend/meeting_playbook/playbooks/repository.py`
  - `packages/backend/meeting_playbook/playbooks/router.py`
  - `packages/backend/meeting_playbook/playbooks/schemas.py`
  - `packages/backend/tests/playbooks/test_repository.py`
  - `packages/backend/tests/playbooks/test_endpoints.py`
  - `packages/backend/tests/playbooks/test_validation.py`
  - `packages/web/src/components/playbook-pane.tsx`
  - `packages/web/src/components/playbook-pane.test.tsx`
  - `packages/web/src/lib/playbook-api.ts`
  - `packages/web/src/lib/playbook-api.queries.test.ts`
  - `packages/web/src/lib/playbook-api.mutations.test.tsx`
  - `openspec/specs/playbook-management/spec.md`（archive 後生成）
- 修改：
  - `packages/backend/meeting_playbook/server.py`（mount playbook router）
  - `packages/backend/tests/conftest.py`（TRUNCATE playbook on teardown）
  - `packages/web/src/routes/meetings/detail.tsx`（嵌入 PlaybookPane）
  - `packages/web/src/locales/zh-TW.json`
  - `packages/web/src/locales/en.json`
  - `packages/web/src/locales/locales.test.ts`
- 不動：`packages/auth/`、`openspec/specs/{auth-gateway-contract,meeting-management}/`、i18n / locale-toggle
- 依賴：沿用現有 `auth-gateway-contract`（`X-User-Id`）與 `meeting-management`（`MeetingRepository.get_for_user` 做 ownership gate），無新 npm/pypi 套件
