## Context

Slice 20c 加了 multimodal-input regenerate；S20a/c fix 加了 confirm dialog
讓使用者「按確認才覆蓋」。仍然是全有或全無的破壞性 UX。S23 把 regenerate
從「覆蓋」改成「對照後挑選」，需要：

1. **存舊版**：regenerate 要 atomically 把舊內容存進 snapshot 欄位再寫新版
2. **可讀舊版**：API response 攜帶 snapshot，前端才能畫 diff
3. **可選擇性 revert**：兩個 endpoint（全部回到舊版 / 接受新版）+ 前端
   per-hunk 局部選擇
4. **資料模型最小化**：只存「上一版」（單一 snapshot），不堆 N 版

當下 `playbook` 表結構（slice-20c 後）：
- `id`, `meeting_id`, `free_form_markdown`, 6 個結構化欄位
- `created_at`, `updated_at`
- `attachment_hash_snapshot`（slice-20c）

Stakeholder：個人使用者（per CONTEXT.md "Single user"）。沒有 multi-tenant
concurrent edit / locking 顧慮。

## Goals / Non-Goals

**Goals**
- 一次 regenerate 後，舊版本可被讀回來顯示 inline diff
- Discard / restore 為原子操作，回應後狀態一致
- Diff 計算在前端（避免 server roundtrip per render）
- 既有 user-save 路徑（`upsert_for_meeting`）行為完全不變
- Snapshot 只占一份 row column，不開新表

**Non-Goals**
- 多版歷史（只保留上一版）
- 結構化 6 欄位 diff（目前沒顯示）
- Summary 跟 chat_message 的版本管理
- Per-character diff
- 3-way merge / conflict resolution

## Decisions

### D1. Snapshot 存在 row column 不另開表

選擇：在 `playbook` 表加三個 nullable column（`previous_free_form_markdown`、
`previous_updated_at`、`previous_attachment_hash_snapshot`），不開新的
`playbook_version` 表。

**理由**
- 「只保留上一版」的 cardinality 是 0..1，row column 是正確 modeling
- 不會有 cross-row query（如「列出此 meeting 的 N 個歷史版本」）
- 跟現有 `attachment_hash_snapshot` 同一個 row 一致更新，atomicity 免費

**Trade-off**：未來若要堆多版必須 migration 到新表。當下 over-engineering 沒
有實際 user story 支撐。

### D2. Snapshot 只在 regenerate 路徑做，user-save 不做

選擇：新增 `snapshot_then_upsert` repository method，**僅** regenerate
endpoint 呼叫。既有 `upsert_for_meeting`（user save）路徑不動。

**理由**
- User save 是中間狀態，每次按存就 snapshot 會把真正的「上一個 AI 版本」蓋
  掉
- 「snapshot 的對象」概念明確：永遠是「regenerate 之前的版本」
- 簡化：兩個方法、兩個語意，不混淆

### D3. Discard / restore 用兩個 POST 端點，不用一個帶 verb 的 PATCH

選擇：`POST /playbook/discard_previous` + `POST /playbook/restore_previous`，
不用 `PATCH /playbook { action: "discard" | "restore" }`。

**理由**
- 跟既有 `POST /playbook/regenerate` 風格一致（已經有 RPC-style endpoint）
- 個別 endpoint 的 OpenAPI/test 寫起來比 dispatch 邏輯清楚
- 沒有 body 要 dispatch，POST 路徑本身就是 verb

### D4. Diff 計算放前端、用 jsdiff（line-level）

選擇：新增 `diff` npm dep，前端 `<PlaybookDiffViewer>` 用 `diff.diffLines`
算 line-level diff。後端不做 diff 計算，response 只回兩段純文字。

**理由**
- 比對是純 read-only computation，沒必要付 network round-trip 成本
- jsdiff 是 maintenance mode 但 stable（10M+ weekly downloads）
- Line-level 對 markdown 夠用：使用者編輯的單位通常是「一段」「一個 list item」
  ，不是 word
- Server-side diff 反而會卡 streaming（resize、theme 切換要重算）

**Trade-off**：依賴新增。`diff` 套件約 30KB minified，無 runtime overhead。

### D5. Per-hunk cherry-pick 用 local state 累積、最後一次 POST

選擇：使用者在 diff viewer 上每個 hunk 選「保留新版/舊版」→ 前端累積出最終
markdown 字串 → 按「套用」一次 POST 走 `upsert_for_meeting`（user save 路徑）
→ 後端清空 `previous_*`（透過 discard endpoint 顯式呼叫，或在 upsert 時自
動清，待 design 階段決定）。

**選 user-save 路徑 + 顯式 discard**：
- Repository method 不交叉。Cherry-pick 結果本質上是「user 編輯」，走 save
  路徑 + 清 snapshot 兩步驟意圖明確
- 兩個請求對網路成本可忽略

### D6. Regenerate 完自動切到 diff mode

選擇：regenerate mutation `onSuccess` 後，前端比較新 `free_form_markdown`
跟 `previous_free_form_markdown`，**若不同**自動把 pane 切到 `diff` mode。

**理由**
- 如果兩版相同（罕見：附件變動但 generator 產出一樣），自動切 diff 反而怪
- 自動切到 diff 讓使用者立刻看到變化、不用先找按鈕

### D7. PlaybookRead 加 `has_previous_version: bool` derived flag

選擇：response 加一個 `has_previous_version` 純 derived flag（=
`previous_free_form_markdown is not None`），方便前端判斷是否顯示「比對舊版」
mode 按鈕。

**理由**：避免前端做 null check + 為未來換 snapshot 儲存方式（比如 store 在
JSONB）留 abstraction layer。

## Risks / Trade-offs

- **Risk**：jsdiff 算大檔（>500 行 markdown）時可能卡 UI thread
  - **Mitigation**：個人 app + markdown 段數實務上 < 100 行，不需要 worker
- **Risk**：使用者連續多次 regenerate 會把先前 snapshot 蓋掉
  - **Trade-off**：刻意設計。「只保留上一版」就是這個語意。UI 上 confirm
    dialog 應該講清楚
- **Risk**：cherry-pick 累積結果跟 regenerate 後的內容差很多時，使用者可能
  以為「我選新版這個 hunk」但實際上 hunk 邊界讓相鄰文字也帶過來
  - **Mitigation**：diff viewer 每個 hunk 明顯框出邊界、hover 顯示對應的舊
    版/新版片段

## Migration Plan

1. Alembic upgrade：加三個 nullable column，沒有 backfill（舊 row 自然
   `previous_* = NULL`，等同「沒有上一版」）
2. Backend deploy 後，既有 regenerate 仍然行為一致（舊版邏輯走 upsert，新版
   會 snapshot）。No downtime
3. Frontend deploy 後，diff mode 按鈕只在 `has_previous_version === true` 時
   出現。舊資料一律沒有上一版 → 看不到 diff mode → 使用者首次 regenerate
   後才看得到 diff

Downgrade：alembic downgrade 把三 column drop。資料遺失但功能 backward-compatible
（playbook row 主體不動）。

## Open Questions

(none — D5 的 user-save 路徑 + 顯式 discard 是 commit 階段做的決定，已寫在
 上面)

## Implementation Contract

- `playbook` table 在 alembic head 必須含 `previous_free_form_markdown`、
  `previous_updated_at`、`previous_attachment_hash_snapshot` 三 nullable
  column
- `PlaybookRepository.snapshot_then_upsert(meeting_id, payload)` 必須 atomic
  地把當下 `free_form_markdown` 寫進 `previous_free_form_markdown`、把當下
  `updated_at` 寫進 `previous_updated_at`、把當下 `attachment_hash_snapshot`
  寫進 `previous_attachment_hash_snapshot`，然後 upsert 新 payload
- `POST /api/meetings/{meeting_id}/playbook/regenerate` 必須走
  `snapshot_then_upsert`，不再走原本的 `upsert_for_meeting`
- `POST /api/meetings/{meeting_id}/playbook/discard_previous` 回應 200 +
  `PlaybookRead`；`previous_*` 三欄全部 NULL；`free_form_markdown` 不變
- `POST /api/meetings/{meeting_id}/playbook/restore_previous` 回應 200 +
  `PlaybookRead`；`free_form_markdown` ← `previous_free_form_markdown`；
  `attachment_hash_snapshot` ← `previous_attachment_hash_snapshot`；
  `previous_*` 三欄全部 NULL
- 兩個新端點當 `previous_free_form_markdown IS NULL` 時回 404
  `playbook.no_previous_version`
- `PlaybookRead` 含 `previous_free_form_markdown`、`previous_updated_at`、
  `has_previous_version`
- 前端 `<PlaybookDiffViewer>` props: `{ previous: string, current: string,
  onAccept: (mode: "all-new" | "all-previous", merged?: string) => void }`，
  line-level diff 用 `diff.diffLines`
- Playbook pane 新增第 3 個 mode `diff`，按鈕只在
  `has_previous_version === true` 時顯示
- Regenerate `onSuccess` 自動切 mode 到 `diff` 當
  `current.free_form_markdown !== previous_free_form_markdown`

## Scope Boundaries

**In scope**
- Backend playbook 模組（models / repository / router / schemas）
- Backend playbook alembic migration
- Frontend playbook-pane + 新 diff viewer 元件
- Frontend playbook-api client
- i18n keys for diff mode + restore/discard/cherry-pick UI
- 既有 confirm dialog 文案修訂

**Out of scope**
- Summary regenerate（仍維持覆蓋語意）
- 結構化 6 欄位 diff
- Multi-version history（>1 版）
- Per-character / word-level diff
- Tactical advisor / transcript / chat_message 任何邏輯
