## 1. Backend：schema + repository（TDD red → green）

> 涵蓋 spec requirement「`playbook` row SHALL carry the immediately preceding generated version」（playbook-versioning）
> 與 spec requirement「User-save upsert preserves the previous-version snapshot」（playbook-management）。
> 對應 design 決策 D1（snapshot 存在 row column 不另開表）與 D2（snapshot 只在 regenerate 路徑做，user-save 不做）。

- [x] 1.1 新增 Alembic migration `packages/backend/alembic/versions/0018_playbook_previous_snapshot.py`
      增加 `playbook` 表三個 nullable column：
      `previous_free_form_markdown TEXT`、
      `previous_updated_at TIMESTAMPTZ`、
      `previous_attachment_hash_snapshot TEXT`。
      此為 design D1 的實作落點。
      **驗證**：新測 `packages/backend/tests/test_alembic_playbook_previous.py` 跑 alembic upgrade + downgrade，
      assert head 後三個 column 都存在且 nullable，downgrade 後消失。

- [x] 1.2 在 `packages/backend/meeting_playbook/playbooks/models.py` 的 `Playbook` SQLAlchemy model 加三個欄位
      （type 對應 1.1，預設 None）。
      **驗證**：`packages/backend/tests/test_alembic_playbook_previous.py` 的同一份測試額外 `Playbook(...).previous_free_form_markdown` 可讀寫不噴 type error。

- [x] 1.3 新增 `PlaybookRepository.snapshot_then_upsert(meeting_id, payload)` 方法
      在 `packages/backend/meeting_playbook/playbooks/repository.py`。
      行為（per design D2 — snapshot 只在 regenerate 路徑做）：
      單一 transaction 內，先把當下 row 的 `free_form_markdown` / `updated_at` / `attachment_hash_snapshot`
      寫進三個 `previous_*` 欄位，然後跑等同既有 `upsert_for_meeting` 的 upsert 邏輯。
      Row 不存在時 snapshot 步驟 no-op、直接 insert（`previous_*` 留 NULL）。
      **驗證**：新測 `packages/backend/tests/playbooks/test_versioning_repository.py::test_snapshot_then_upsert_existing_row`
      跑 v1 → snapshot_then_upsert(v2) → assert `free_form_markdown == "v2"` 且 `previous_free_form_markdown == "v1"`。
      第二個 case `test_snapshot_then_upsert_first_insert` 跑空 row → upsert → assert `previous_*` 仍為 None。
      第三個 case `test_user_save_upsert_preserves_snapshot` 驗證 user-save 路徑（既有 `upsert_for_meeting`）
      不會碰 `previous_*` 欄位（涵蓋「User-save upsert preserves the previous-version snapshot」requirement）。

- [x] 1.4 新增 `PlaybookRepository.discard_previous(meeting_id)` 方法。
      把三個 `previous_*` 欄位都改 None；其他欄位不動；回傳更新後的 row（或 None 若 row 不存在或本來就沒 snapshot）。
      涵蓋 spec requirement「`POST .../playbook/discard_previous` SHALL clear the snapshot without changing the current draft」repository 層。
      **驗證**：新測 `packages/backend/tests/playbooks/test_versioning_repository.py::test_discard_previous_clears_snapshot`
      建一個有 snapshot 的 row → discard → assert 三 `previous_*` 為 None，`free_form_markdown` 不變。
      第二個 case `test_discard_previous_returns_none_when_no_snapshot` 對無 snapshot row 呼叫 → 回 None。

- [x] 1.5 新增 `PlaybookRepository.restore_previous(meeting_id)` 方法。
      把 `previous_free_form_markdown` 寫進 `free_form_markdown`、
      `previous_attachment_hash_snapshot` 寫進 `attachment_hash_snapshot`、
      `updated_at` 設為 `datetime.now(UTC)`、三個 `previous_*` 設 None；
      6 個結構化欄位不動；回傳更新後的 row（或 None 若無 snapshot）。
      涵蓋 spec requirement「`POST .../playbook/restore_previous` SHALL swap the snapshot back into the current draft」repository 層。
      **驗證**：新測 `packages/backend/tests/playbooks/test_versioning_repository.py::test_restore_previous_swaps_snapshot_in`
      跑 setup row (current v2, previous v1) → restore → assert current 為 v1、`previous_*` 為 None、`updated_at` 已更新。

## 2. Backend：API surface

> 涵蓋 spec requirement「GET / `PlaybookRead` response SHALL expose the previous-version columns」（playbook-versioning）
> 與「`PlaybookRead` schema exposes the previous-version snapshot」（playbook-management）。
> 對應 design 決策 D3（discard / restore 用兩個 POST 端點，不用一個帶 verb 的 PATCH）與 D7
> （PlaybookRead 加 `has_previous_version: bool` derived flag）。

- [x] 2.1 修改 `packages/backend/meeting_playbook/playbooks/schemas.py` 的 `PlaybookRead`，
      加 `previous_free_form_markdown: str | None`、`previous_updated_at: datetime | None`、
      `has_previous_version: bool`（用 `@computed_field` 或 `model_validator` 從 `previous_free_form_markdown` 推算，per design D7）。
      **驗證**：既有 `packages/backend/tests/playbooks/test_router.py` 補一個 assert
      無 snapshot 時 response 含 `"has_previous_version": false`、`"previous_free_form_markdown": null`。

- [x] 2.2 修改 `POST /api/meetings/{meeting_id}/playbook/regenerate` handler（playbooks/router.py）
      改呼叫 `snapshot_then_upsert` 而非既有 `upsert_for_meeting`。Generator 部份不動。
      涵蓋 spec requirement「Regenerate endpoint persists via snapshot-then-upsert」（playbook-generation）。
      **驗證**：既有 `packages/backend/tests/playbooks/test_router.py::test_regenerate_playbook_*` 系列
      新增一個 assert：regenerate 完後 response 的 `previous_free_form_markdown` 等於 regen 前的 `free_form_markdown`。

- [x] 2.3 新增 `POST /api/meetings/{meeting_id}/playbook/discard_previous` handler（per design D3 兩個 POST 端點而非單一 PATCH）。
      呼叫 `MeetingRepository.get_for_user` 做 ownership check（404 `meeting.not_found` 若失敗），
      然後呼叫 `PlaybookRepository.discard_previous`，None 回傳 → 404 `playbook.no_previous_version`，
      否則 200 + `PlaybookRead`。
      涵蓋 spec requirement「`POST .../playbook/discard_previous` SHALL clear the snapshot without changing the current draft」endpoint 層。
      **驗證**：新測 `packages/backend/tests/playbooks/test_discard_endpoint.py` 三個 case：
      `test_discard_with_snapshot_returns_200`、`test_discard_without_snapshot_returns_404`、
      `test_discard_cross_user_returns_404`。

- [x] 2.4 新增 `POST /api/meetings/{meeting_id}/playbook/restore_previous` handler，
      結構同 2.3 但呼 `restore_previous`。
      涵蓋 spec requirement「`POST .../playbook/restore_previous` SHALL swap the snapshot back into the current draft」endpoint 層。
      **驗證**：新測 `packages/backend/tests/playbooks/test_restore_endpoint.py` 三個 case：
      `test_restore_with_snapshot_swaps_in_previous`、`test_restore_without_snapshot_returns_404`、
      `test_restore_cross_user_returns_404`。

## 3. Frontend：API client

> 對應 design 決策 D4（diff 計算放前端、用 jsdiff line-level）的 client 端介面。

- [x] 3.1 修改 `packages/web/src/lib/playbook-api.ts` 的 `interface Playbook`，
      加三個欄位：`previous_free_form_markdown?: string | null`、
      `previous_updated_at?: string | null`、`has_previous_version?: boolean`。
      **驗證**：跑 `bun --filter @meeting-playbook/web test`，既有 `playbook-pane.test.tsx` 跟 `playbook-api.test.ts`
      都不能因 type 變更而紅。

- [x] 3.2 在 `packages/web/src/lib/playbook-api.ts` 新增三個函式 + mutation hook：
      `discardPreviousPlaybook(meetingId)` POST 到 `/playbook/discard_previous`、
      `restorePreviousPlaybook(meetingId)` POST 到 `/playbook/restore_previous`、
      `useDiscardPreviousPlaybookMutation(meetingId)` 跟 `useRestorePreviousPlaybookMutation(meetingId)`
      onSuccess 走 `queryClient.setQueryData(["playbook", meetingId], data)`。
      **驗證**：新測 `packages/web/src/lib/playbook-api.test.ts` 加兩個 case，
      mock fetch 回 200 + body → assert 函式回傳 parsed Playbook，回 404 → throw PlaybookApiError。

## 4. Frontend：Diff viewer 元件

> 落實 design 決策 D4（diff 計算放前端、用 jsdiff line-level）
> 與 D5（per-hunk cherry-pick 用 local state 累積、最後一次 POST）。

- [x] 4.1 加 `diff` npm dep + types：
      在 `packages/web/` 工作區跑 `bun add diff` 跟 `bun add -d @types/diff`，
      lock file commit 進 PR。
      **驗證**：`packages/web/package.json` 有 `"diff"` 在 dependencies、`"@types/diff"` 在 devDependencies；
      `bun install` 跑成功；`bun --filter @meeting-playbook/web typecheck` 不噴 module-not-found。

- [x] 4.2 新增 `packages/web/src/components/playbook-diff-viewer.tsx` 元件（design D4 落點）。
      Props：`{ previous: string, current: string, onAcceptAllNew: () => void,
      onRestoreAllPrevious: () => void, onApplyMerged: (mergedMarkdown: string) => void,
      isPending?: boolean }`。
      用 `diff.diffLines(previous, current)` 算 hunks，每個 hunk 顯示為：
      - 刪除（紅底）：`<del>` semantic + bg `--color-destructive`/10
      - 新增（綠底）：`<ins>` semantic + bg `--color-accent`/10
      - 不變：`<span>` + bg `--color-card`
      Per design D5，每個變動 hunk（add 或 remove）旁邊有「保留此段」按鈕；
      點下去把該 hunk 的決定累積到 local state，
      最後「套用」按鈕呼叫 `onApplyMerged(merged)` 把累積結果送出去。
      上方三個全域按鈕：「全部採用新版」、「全部回到舊版」、「套用挑選」（後者只在有任一 hunk 被改 decision 時 enabled）。
      **驗證**：新測 `packages/web/src/components/playbook-diff-viewer.test.tsx` 渲染兩段差異 markdown，
      assert hunk 數量、顏色 class 套對、點「全部採用新版」呼叫 `onAcceptAllNew` 一次、
      點 hunk「保留舊版」按鈕後再按「套用挑選」呼叫 `onApplyMerged` 帶正確 merged 字串。

## 5. Frontend：Playbook pane 整合

> 涵蓋 spec requirement「Frontend Playbook pane SHALL expose a `diff` mode in addition to `edit` and `preview`」（playbook-versioning）
> 與 modified requirement「PlaybookPane UI exposes a free-form view, a structured view, and a save action」（playbook-management）。
> 對應 design 決策 D6（regenerate 完自動切到 diff mode）。

- [x] 5.1 修改 `packages/web/src/components/playbook-pane.tsx`，
      把既有 `freeformMode: "edit" | "preview"` state 擴成 `"edit" | "preview" | "diff"`，
      在 toggle group 增加 `<Button>` for `diff`，**只在 `query.data?.has_previous_version === true` 時 render**。
      Mode 為 `diff` 時 render `<PlaybookDiffViewer>`，三個 callback 接到既有/新 mutation：
      - `onAcceptAllNew` → `useDiscardPreviousPlaybookMutation` 跑、success 後 setMode("edit")
      - `onRestoreAllPrevious` → `useRestorePreviousPlaybookMutation` 跑、success 後 setMode("edit")
      - `onApplyMerged(merged)` → `useUpsertPlaybookMutation` 帶 `free_form_markdown: merged` + 其他欄位，
        success 後再連發 `useDiscardPreviousPlaybookMutation`、setMode("edit")
      **驗證**：擴充 `packages/web/src/components/playbook-pane.test.tsx`（或新增）
      mock playbook query `has_previous_version: true` → assert toggle 有 3 個按鈕；
      mock `has_previous_version: false` → assert 只有 2 個按鈕。

- [x] 5.2 在 playbook-pane.tsx 的 regenerate mutation `onSuccess` 加 auto-switch 邏輯（design D6）：
      regenerate 完拿到新 data → 若 `data.previous_free_form_markdown && data.previous_free_form_markdown !== data.free_form_markdown` → setMode("diff")。
      **驗證**：擴充 `packages/web/src/components/playbook-pane.test.tsx`：
      mock regenerate response (previous v1 / current v2) → assert 按重新生成完後 mode 變 diff。
      第二個 case：mock 兩版相同 → assert mode 不變。

- [x] 5.3 修訂既有 regenerate 確認 dialog 文案（playbook-pane.tsx + 兩份 locale）。
      新版文案要點出「會自動存上一版、可在 Diff 模式對照」，
      舊文案的「未儲存的修改會遺失」改成「未儲存的修改可在 Diff 模式還原」。
      新 i18n keys（兩份 locale 同步）：
      `playbook.diff.tab` / `playbook.diff.acceptAllNew` / `playbook.diff.restoreAllPrevious` /
      `playbook.diff.applyMerged` / `playbook.diff.keepThis` / `playbook.diff.emptyHint`。
      修訂 keys：`playbook.stale.confirm_description`。
      **驗證**：跑 `bun --filter @meeting-playbook/web test src/locales/locales.test.ts`
      （deep-equal parity test）不能紅。

## 6. 端到端驗證

- [x] 6.1 手動 E2E：開既有 meeting → 上傳 PDF → 等 stale banner → 按重新生成 →
      確認 dialog 看到新文案 → 按確認 → pane 自動進 diff mode → 看到舊版/新版對照 →
      按「全部採用新版」→ pane 切回 edit、textarea 顯示新版 markdown、banner 消失。
      重複一次但這次按「全部回到舊版」→ assert textarea 變回 regen 前的內容。
      第三次測 cherry-pick：按其中一個 hunk「保留舊版」→ 按「套用挑選」→ assert textarea 顯示混合結果。
      **驗證**：本 task 是手動測試 checklist，commit message 寫明三條 flow 都過。

- [x] 6.2 跑 full backend + web test：
      `psql postgresql://localhost:5432/meeting_playbook_test -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"` →
      `cd packages/backend && uv run pytest -q` →
      `bun --filter @meeting-playbook/web test`。
      **驗證**：backend pass count 比 main 多至少 6 個（new versioning tests）、web pass count 比 main 多至少 4 個
      （new diff viewer + pane diff mode tests）、0 fail。
