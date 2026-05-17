> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/22
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16
> Depends on: 無（可立即開始）

## Why

使用者常需要把多場相關會議串起來（例如「上次同一家客戶的 Q1 啟動會」、「上週的 internal 對齊」）。目前 Playbook 之間互不相通，使用者得自己記哪兩場有關，反覆翻 meetings list 找回脈絡。S21 加一條手動「related」連結：在 meeting detail header 就能看到所有關聯會議並一鍵跳轉。

## What Changes

- 新增 schema `meeting_link(id, from_meeting_id, to_meeting_id, link_type, created_at)`；v1.1 `link_type` 固定為 `"related"`，由欄位先佔位讓 v1.2 可延伸成 `"follow_up"` / `"prep_for"` 等
- 新 `MeetingLinkRepository` deep module：寫一 row、兩邊都查得到（bidirectional）、同對 meeting 去重、刪除單邊操作（任一端發 DELETE 都會清掉那條連結）
- 新 endpoint：
  - `GET /api/meetings/{id}/links` — 回 bidirectional 結果（從 A 看到「A → B」與「B → A」兩種 row 寫法皆視為 A 的 link）
  - `POST /api/meetings/{id}/links` body `{to_meeting_id}` — 建立關聯；同對 meeting 已存在（任一方向）回 HTTP 409
  - `DELETE /api/meetings/{id}/links/{link_id}` — 移除單條連結，rowner 必須擁有兩端 meeting
- 新前端元件：
  - meeting detail header 加 related links 群組（顯示 `N related` + 展開列表 + 跳轉連結）
  - `<MeetingLinkPicker>` typeahead 搜尋既有 meeting（排除當前 meeting 與已連結 meeting）
  - 「+ 關聯」按鈕觸發 picker
- `CONTEXT.md` glossary 加「Meeting link」一條
- i18n 字串雙 locale（zh-TW + en）

## Non-Goals

- 自動推薦 related meetings（v1.2 backlog；可走 LLM 比對 playbook 對象/標題相似度）
- `link_type` 語意化（v1.1 只支援 `"related"`；`"follow_up"` / `"prep_for"` 等留 v1.2 ADR 一次補 UI affordance）
- 跨使用者連結（單一使用者產品，無共享 meeting 概念）
- Bulk link / multi-select picker（picker 一次選一個 meeting，避免誤建大量連結）
- Auto-link by participant overlap / calendar series（依賴 Google Calendar series id，超出 S21 範圍）
- Link 出現在 meetings list / calendar view（v1.1 只在 detail header 顯示）

## Capabilities

### New Capabilities

- `meeting-linking`: 手動建立兩個 meeting 之間的 bidirectional `related` 連結，含 schema、repository、CRUD API、`<MeetingLinkPicker>` 前端元件與 i18n。

### Modified Capabilities

- `meeting-detail-layout`: detail header 在既有 prev/next 群組旁加 related links 區塊；新增 `+ 關聯` 按鈕觸發 `<MeetingLinkPicker>` modal。

## Impact

- Affected specs:
  - New: `openspec/specs/meeting-linking/spec.md`
  - Modified: `openspec/specs/meeting-detail-layout/spec.md`
- Affected code:
  - New:
    - `packages/backend/meeting_playbook/meeting_links/__init__.py`
    - `packages/backend/meeting_playbook/meeting_links/models.py`
    - `packages/backend/meeting_playbook/meeting_links/repository.py`
    - `packages/backend/meeting_playbook/meeting_links/router.py`
    - `packages/backend/meeting_playbook/meeting_links/schemas.py`
    - `packages/backend/alembic/versions/XXXX_meeting_link.py`
    - `packages/backend/tests/meeting_links/test_repository.py`
    - `packages/backend/tests/meeting_links/test_router.py`
    - `packages/backend/tests/test_alembic_meeting_link.py`
    - `packages/web/src/components/meeting-links-section.tsx`
    - `packages/web/src/components/meeting-links-section.test.tsx`
    - `packages/web/src/components/meeting-link-picker.tsx`
    - `packages/web/src/components/meeting-link-picker.test.tsx`
    - `packages/web/src/lib/meeting-links-api.ts`
  - Modified:
    - `packages/backend/meeting_playbook/server.py`
    - `packages/web/src/components/metadata-card.tsx`
    - `packages/web/src/routes/meetings/detail.tsx`
    - `packages/web/src/locales/zh-TW.json`
    - `packages/web/src/locales/en.json`
    - `packages/web/src/lib/i18n-errors.ts`
    - `CONTEXT.md`
  - Removed: (none)
- 不新增 env vars / 外部資源（無新 secret、無 ADR 異動）
