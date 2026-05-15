> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/18
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16

## Why

目前 `PATCH /api/meetings/{id}` 只支援 `asr_provider`（slice-11 落地），其他欄位（title、scheduled times、display names）一旦建立就無法修改，使用者必須刪重建。同時 `meeting.scheduled_start_at` 是 nullable，導致 meeting-card / kanban / calendar 全都要寫「缺值就 fallback `created_at`」的補丁邏輯，無法把 scheduled time 當第一公民排序與顯示。S15 把 PATCH 擴成完整 inline edit endpoint，並把 `scheduled_start_at` 改必填，掃除 fallback 分支。

## What Changes

- 擴 `PATCH /api/meetings/{id}` 接受 `{title?, scheduled_start_at?, scheduled_end_at?, counterparty_display_name?, me_display_name?, asr_provider?}`；既有 `asr_provider` 行為保留
- `MeetingPatch` Pydantic schema 改成多欄位、各自驗證（非空、非空白、ISO 8601、`scheduled_end_at` 若有需 ≥ `scheduled_start_at`）
- `MeetingRepository` 新 `update_for_user(...)` 取代/包住既有 `update_asr_provider_for_user`，用單一 UPDATE 寫入所有可變欄位
- Alembic migration `0009_meeting_scheduled_start_at_not_null`：先以 `UPDATE meeting SET scheduled_start_at = created_at WHERE scheduled_start_at IS NULL` backfill，再 `ALTER COLUMN ... SET NOT NULL`；downgrade 是 `DROP NOT NULL`
- `MeetingCreate` schema 把 `scheduled_start_at` 改必填（移除 `= None` default）
- 新建會議表單 `packages/web/src/routes/meetings/new.tsx` 把 scheduled time 欄位改必填 + react-hook-form + zod 驗證
- meeting detail 頁加 inline edit form（react-hook-form + zod，submit 呼叫 PATCH，成功後 invalidate cache）
- 移除三處 `?? created_at` fallback：`meeting-card.tsx`、`meetings-kanban.tsx`、`meetings-calendar-utils.ts`
- 重新設計 Kanban 三欄分桶規則：把原本「即將到來（7 天內）/ 未來（>= 7 天）/ 已結束（completed 或 overdue）」改成「**待補錄**（`status === "scheduled" AND scheduled_start_at < now` — 應該要記錄但沒記錄）/ **未來**（`status === "scheduled" AND scheduled_start_at >= now`）/ **已結束**（`status in ("completed", "in_progress")` — 有實際會議記錄就放這）」。`meetings-bucket.ts` helper 改寫；i18n key 從 `bucketUpcoming/Future/Past` 改成 `bucketNeedsRecording/Upcoming/Completed`（雙 locale 同步）。
- **Edit form 改成 shadcn Dialog（中央彈窗）**：`MeetingEditForm` 從 detail 頁 inline conditional render 改用 `<Dialog>` 包覆，點 toolbar「編輯」按鈕開啟、ESC / 點背景 / 取消 / 儲存成功 皆關閉。`<DialogHeader>` 顯示「編輯會議」標題，`<DialogContent>` 內含原 form。
- **Detail 頁 actions bar 內「開始會議 / 上傳音檔」雙按鈕常駐**：移除既有 `UploadBanner` 的條件顯示（`shouldShowOfflineIngestBanner` 邏輯），改成在 `MetadataCard` 的 button row 內加 `uploadSlot` 並由 detail 頁傳入一個常駐「上傳音檔」按鈕。`status` 不影響可見性，只影響 button variant 與 disabled state：scheduled/needs_recording → 上傳 `outline`；in_progress → 上傳 disabled（錄音中不允許）；completed → 上傳 `secondary`（用於重跑 ASR）。同 row 既有的 start / end 按鈕保留不動。`UploadBanner.tsx` + 對應測試移除。
- **Kanban 「待補錄」欄 card 上 hover-only 上傳 shortcut**：`MeetingCard` 接受 `showUploadShortcut?: boolean` prop，當 true 時 card hover 顯示「上傳音檔」mini button；點下後 `navigate` 到 `/meetings/$id?action=upload`，detail 頁 mount 時讀 `action` query param 自動開啟 upload dialog。`MeetingsKanban` 在 render `needs_recording` 欄 card 時傳 `showUploadShortcut={true}`。
- **Kanban 「待補錄」欄空欄專屬 CTA**：當 `needs_recording` 欄為空時，把預設 `bucketEmpty` hint 換成自訂訊息 `bucketNeedsRecordingEmpty`（zh-TW「目前沒有待補錄的會議」/ en「No meetings to follow up on」），其它兩欄維持原 `bucketEmpty`。
- 新 i18n 字串雙 locale（`zh-TW.json` + `en.json`）：edit form labels、驗證錯誤、儲存成功訊息、Kanban 新 bucket 標籤、edit dialog title、actions bar 上傳按鈕、card hover shortcut label、needs_recording 空欄 CTA

## Non-Goals

- Soft-delete / undo / 版本歷史 — meeting 更新採直接覆寫，不留歷史 row
- 修改 meeting status (`scheduled` / `in_progress` / `completed`) — status 仍由 session 生命週期驅動，不開放 PATCH
- 修改 `calendar_event_id` — 由 calendar sync 自行管理，不開放 inline edit
- WebSocket 即時通知其他開啟同會議的 client — 本 slice 仍 client-side invalidate-on-success，跨 tab 同步留未來 slice
- 修改 `started_at` / `ended_at` — 由 session router 寫入，不開放 PATCH
- Bulk PATCH 多筆 meeting — 仍維持 per-id endpoint

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `meeting-management`: PATCH endpoint 從只支援 `asr_provider` 擴成支援 title / scheduled times / display names / asr_provider 全欄位 partial update；`scheduled_start_at` schema 約束從 nullable 改 NOT NULL（backfill from `created_at`）；`MeetingCreate` schema 必填 `scheduled_start_at`；list / detail / kanban / calendar 不再有 `created_at` fallback 邏輯；Kanban 三欄分桶規則從「時間窗口（7 天）」改成「狀態 + 是否過期」（待補錄 / 未來 / 已結束），i18n key 同步改名；Detail 頁 inline edit form 改 Dialog 彈窗；Detail 頁 actions bar 內「上傳音檔」常駐顯示（取代既有 `UploadBanner` 條件顯示）；Kanban「待補錄」欄 card 加 hover-only 上傳 shortcut 與專屬空欄 CTA。

## Impact

- Affected specs:
  - Modified: `openspec/specs/meeting-management/spec.md`
- Affected code:
  - New: `packages/backend/alembic/versions/0009_meeting_scheduled_start_at_not_null.py`, `packages/web/src/components/meeting-edit-form.tsx`, `packages/web/src/components/meeting-edit-form.test.tsx`
  - Modified: `packages/backend/meeting_playbook/meetings/schemas.py`, `packages/backend/meeting_playbook/meetings/repository.py`, `packages/backend/meeting_playbook/meetings/router.py`, `packages/backend/meeting_playbook/meetings/models.py`, `packages/backend/tests/meetings/test_endpoints.py`, `packages/backend/tests/meetings/test_repository.py`, `packages/web/src/routes/meetings/new.tsx`, `packages/web/src/routes/meetings/detail.tsx`, `packages/web/src/components/meeting-card.tsx`, `packages/web/src/components/meetings-kanban.tsx`, `packages/web/src/components/meetings-kanban.test.tsx`, `packages/web/src/components/meeting-edit-form.tsx`, `packages/web/src/components/meeting-edit-form.test.tsx`, `packages/web/src/components/metadata-card.tsx`, `packages/web/src/lib/meetings-bucket.ts`, `packages/web/src/lib/meetings-bucket.test.ts`, `packages/web/src/lib/meetings-calendar-utils.ts`, `packages/web/src/lib/meetings-api.ts`, `packages/web/src/locales/zh-TW.json`, `packages/web/src/locales/en.json`
  - Removed: `packages/web/src/components/offline-ingest/UploadBanner.tsx`, `packages/web/src/components/offline-ingest/UploadBanner.test.tsx`
  - Removed: (none)
