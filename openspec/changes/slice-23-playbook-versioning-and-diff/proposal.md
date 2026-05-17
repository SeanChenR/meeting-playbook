## Why

Slice 20c 的 regenerate 流程目前是「整筆覆蓋」：使用者點重新生成 → 新 AI 草稿
直接蓋掉現有 `free_form_markdown` + 6 個結構化欄位。S20a/c 的 fix 加了一個
**確認 dialog** 警告會覆蓋，但本質上仍然是「全有或全無」的破壞性操作。

實際使用情境中，使用者往往做了大量手動編輯（修錯字、加重點、調整語氣），新
的 AI 草稿因為附件變動所以**部份**內容值得採納（比如 PDF 報價單帶來的新數
字），但**大部份**個人化編輯應該保留。沒有 diff/cherry-pick 的話，使用者只
能在「全部丟掉手動編輯換新版」跟「不用新內容」之間二選一，等於這個 regenerate
功能在實務上沒法用。

S23 補上版本快照 + diff 檢視 + 段落級 cherry-pick，讓 regenerate 從「一次性
覆蓋」進化成「對照後選擇性合併」。

## What Changes

- **Backend：版本快照**
  - 新 Alembic migration：`playbook` 表新增 `previous_free_form_markdown TEXT NULL`、
    `previous_updated_at TIMESTAMPTZ NULL`、`previous_attachment_hash_snapshot TEXT NULL`
  - `PlaybookRepository.snapshot_then_upsert(meeting_id, payload)`：在 upsert
    新版本前，先把當下的 `free_form_markdown` + `updated_at` +
    `attachment_hash_snapshot` 寫進對應的 `previous_*` 欄位。Regenerate 端
    點改呼叫這個方法
  - 既有 `upsert_for_meeting`（user save 路徑）**不**做 snapshot，因為使用者
    自存的中間狀態不算「版本」
- **Backend：兩個新端點**
  - `POST /api/meetings/{meeting_id}/playbook/discard_previous` → 清空
    `previous_*` 三欄位，回傳更新後的 `PlaybookRead`。對應前端「接受新版、
    忘記舊版」按鈕
  - `POST /api/meetings/{meeting_id}/playbook/restore_previous` → 把
    `previous_*` 寫回 `free_form_markdown` + `attachment_hash_snapshot`，
    清空 `previous_*`。對應前端「全部回到舊版」按鈕
- **Backend：PlaybookRead schema**
  - 新增 `previous_free_form_markdown: str | None` 跟
    `previous_updated_at: datetime | None` 兩個欄位（供前端判斷是否要顯示
    「比對舊版」按鈕、計算 diff）
  - 新增 derived flag `has_previous_version: bool`（= `previous_free_form_markdown` 非 None）
- **Frontend：Diff viewer 元件**
  - 新 `<PlaybookDiffViewer>` 元件：line-level diff，紅色刪除、綠色新增、
    白色不變。每個 hunk 旁邊有「保留舊版」「採用新版」「編輯」三個按鈕
  - 用 npm `diff` 套件（jsdiff）算 line-level diff
- **Frontend：Playbook pane 三種模式**
  - `edit`（既有）→ textarea + save
  - `preview`（既有）→ markdown 渲染
  - 新 `diff`（only available when `has_previous_version === true`）→
    `<PlaybookDiffViewer>` + 三個 action 按鈕：「全部採用新版」「全部回到舊版」
    「按 hunk 挑」
- **Frontend：Regenerate 完自動進 diff 模式**
  - Regenerate mutation `onSuccess` → 切到 `diff` mode（如果新舊內容有差）
  - 既有的「重新生成中…」、「重新生成失敗」回饋維持
- **Frontend：i18n + 確認 dialog**
  - 新 keys：`playbook.diff.*`（mode 切換、按鈕、helper 文案）
  - 既有的 regenerate 確認 dialog 文案修一下，從「會被覆蓋」改成「會儲存舊
    版到對照模式，可以挑選保留」

## Non-Goals

- **Summary 不做版本快照**：summary regenerate 走非同步 polling 模式
  （`{status:"pending"}` → `{status:"done", markdown}`），跟 playbook 的同步
  upsert 路徑差太多；硬塞 diff 會破壞 polling 邏輯。Summary 留在原本「全部
  覆蓋」的行為，等以後 single-slice 處理
- **不做完整版本歷史**：只保留「上一版」（單一 snapshot），不堆多版。每次
  regenerate 把 `previous_*` 蓋掉，新的 snapshot 是當下被替換掉的版本
- **不做結構化欄位 diff**：6 個結構化欄位（objective、talking_points 等）目
  前不在 playbook pane 上顯示（per project memory `playbook_field_set_open`），
  做 diff 沒意義。snapshot 只存 `free_form_markdown`
- **不做 word-level / character-level diff**：line-level 對 markdown 已經夠
  細；token-level 在 markdown 場景容易把語意拆碎
- **不做 conflict resolution UI**：cherry-pick 是「選 hunk」不是「3-way
  merge」，沒有 conflict 概念
- **不改後端 generator 本身**：S20c 的 multimodal generator 不動，只在
  upsert 路徑加 snapshot

## Capabilities

### New Capabilities

- `playbook-versioning`: 維護 playbook 的「上一版」快照、提供 regenerate-
  with-snapshot 端點、discard/restore 端點，以及 frontend diff viewer 跟
  per-hunk cherry-pick UI

### Modified Capabilities

- `playbook-management`: `Playbook` schema 多 `previous_*` 三欄；新增兩個
  endpoint（discard_previous、restore_previous）；既有 user-save upsert 維
  持原本 semantics 不變
- `playbook-generation`: regenerate 端點改走 snapshot-then-upsert 路徑；
  generator 本身不動；對外 contract（response shape）多兩個欄位

## Impact

- Affected specs:
  - New: playbook-versioning
  - Modified: playbook-management, playbook-generation
- Affected code:
  - New:
    - packages/backend/alembic/versions/0018_playbook_previous_snapshot.py
    - packages/backend/tests/playbooks/test_versioning_repository.py
    - packages/backend/tests/playbooks/test_restore_endpoint.py
    - packages/backend/tests/playbooks/test_discard_endpoint.py
    - packages/web/src/components/playbook-diff-viewer.tsx
    - packages/web/src/components/playbook-diff-viewer.test.tsx
  - Modified:
    - packages/backend/meeting_playbook/playbooks/models.py
    - packages/backend/meeting_playbook/playbooks/repository.py
    - packages/backend/meeting_playbook/playbooks/router.py
    - packages/backend/meeting_playbook/playbooks/schemas.py
    - packages/web/src/lib/playbook-api.ts
    - packages/web/src/components/playbook-pane.tsx
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
    - packages/web/package.json (new dep: diff)
  - Removed: (none)
