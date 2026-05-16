> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/20
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16

## Why

目前 meeting list 只能靠 title / 時間 / 狀態瀏覽，當 Sean 累積到幾十場會議後，要找「跟同一家客戶的所有會議」或「所有面試類型的會議」沒有任何分類手段。Slice 17 引入 per-user 扁平 Tag (標籤) 系統，讓使用者自訂 tag（如「客戶 X」「面試」「one-on-one」）並掛到 meetings 上，在 list / kanban / calendar 三個視圖都能過濾，並提供 `/settings/tags` 管理頁。

## What Changes

- 新增 schema：`tag(id, user_id, name, color, created_at)` 加 unique constraint `(user_id, lower(name))`；junction table `meeting_tag(meeting_id, tag_id, attached_at)` 複合主鍵。
- 新 `TagRepository` (deep module, TDD)：per-user 唯一、case-insensitive name、attach / detach、hard delete cascade junction。
- 新 endpoints：`GET / POST / PATCH / DELETE /api/tags`、`POST /api/meetings/{id}/tags`、`DELETE /api/meetings/{id}/tags/{tag_id}`。
- 單一 meeting 最多 10 個 tag；超過時 attach reject 並回有意義 error。
- 前端 UI：`<TagChip>` 顯示於 meeting card / kanban / calendar / detail header；`<TagPicker>` popover（search + inline create）；`<TagFilter>` multi-select 掛 list / kanban / calendar 上方；`/settings/tags` 管理頁（rename / recolor / hard delete 含確認文案動態顯示「將從 N 個會議移除」）。
- Color palette：preset 8–10 色，**不開**使用者自訂顏色。
- `GET /api/meetings` 接受 `?tag_ids=` query param 進行 AND 過濾。
- i18n：所有新字串落在 zh-TW + en；CONTEXT.md glossary 加「Tag (標籤)」。

## Non-Goals

- **Hierarchical tags / nested categories** — 扁平結構不做 parent-child。
- **Auto-tagging by LLM** — 不對 transcript / playbook 內容自動抽 tag；列入 v1.2 backlog。
- **Tag sharing across users** — Single-user 專案；tag 永遠 per-user scope。
- **Tag colors 完全自訂** — preset palette 已足夠，避免一堆 1pt 對比度的「自由色」毀掉 dual-theme。
- **Tag analytics / usage stats** — 不在 `/settings/tags` 顯示「最常用」「最後使用」之類；以後若要做，獨立 slice。
- **Bulk attach / detach UI** — 一次只能對單一 meeting attach / detach；批次操作列入 v1.2 backlog。
- **Smart filters / saved views** — `<TagFilter>` 僅 session-level 狀態，不存到 user preference；之後若做 saved views 走獨立 capability。

## Capabilities

### New Capabilities

- `tag-system`: per-user 扁平 tag 的 schema、repository、CRUD API、meeting attach/detach API、`<TagChip>` / `<TagPicker>` / `<TagFilter>` 三個 UI 元件、`/settings/tags` 管理頁面與 i18n。

### Modified Capabilities

- `meeting-management`: `GET /api/meetings` 與 `GET /api/meetings/{id}` payload 加入 `tags: [{id, name, color}]` 陣列；list endpoint 新增 `?tag_ids=` query 參數作 AND 過濾。

## Impact

- Affected specs:
  - New: `openspec/specs/tag-system/spec.md`
  - Modified: `openspec/specs/meeting-management/spec.md`
- Affected code:
  - New: `packages/backend/meeting_playbook/tags/__init__.py`, `packages/backend/meeting_playbook/tags/models.py`, `packages/backend/meeting_playbook/tags/repository.py`, `packages/backend/meeting_playbook/tags/router.py`, `packages/backend/alembic/versions/XXXX_tag_system.py`, `packages/backend/tests/test_alembic_tag_system.py`, `packages/backend/tests/tags/test_repository.py`, `packages/backend/tests/tags/test_router.py`, `packages/web/src/components/tags/tag-chip.tsx`, `packages/web/src/components/tags/tag-picker.tsx`, `packages/web/src/components/tags/tag-filter.tsx`, `packages/web/src/components/tags/tag-chip.test.tsx`, `packages/web/src/components/tags/tag-picker.test.tsx`, `packages/web/src/components/tags/tag-filter.test.tsx`, `packages/web/src/routes/settings/tags.tsx`, `packages/web/src/routes/settings/tags.test.tsx`, `packages/web/src/lib/tags-api.ts`
  - Modified: `packages/backend/meeting_playbook/meetings/models.py`, `packages/backend/meeting_playbook/meetings/repository.py`, `packages/backend/meeting_playbook/meetings/router.py`, `packages/backend/meeting_playbook/server.py`, `packages/backend/tests/test_meetings_router.py`, `packages/web/src/routes/meetings/list.tsx`, `packages/web/src/routes/meetings/kanban.tsx`, `packages/web/src/routes/meetings/calendar.tsx`, `packages/web/src/routes/meetings/detail.tsx`, `packages/web/src/route-tree.tsx`, `packages/web/src/locales/zh-TW.json`, `packages/web/src/locales/en.json`, `CONTEXT.md`
  - Removed: (none)
