## 1. Backend：schema 開放暫存態（TDD red → green）

> 涵蓋 spec requirement「meeting_attachment row supports staged (orphan) state」（meeting-attachment）。
> 對應 design 決策 D1（沿用 `meeting_attachment` + nullable meeting_id）與
> D2（加 `user_id` column）。

- [x] 1.1 新增 Alembic migration `packages/backend/alembic/versions/0019_attachment_nullable_meeting.py`：
      ALTER `meeting_attachment.meeting_id` DROP NOT NULL；
      ADD `user_id TEXT NOT NULL DEFAULT ''`；
      UPDATE backfill `SET user_id = m.user_id FROM meeting m WHERE ma.meeting_id = m.id`；
      ALTER `user_id` DROP DEFAULT + ADD FK to `user.id`；
      CREATE INDEX `meeting_attachment_user_meeting_uploaded_idx ON (user_id, meeting_id, uploaded_at DESC)`。
      Downgrade：DELETE WHERE meeting_id IS NULL → DROP user_id → ALTER meeting_id SET NOT NULL。
      **驗證**：新測 `packages/backend/tests/test_alembic_attachment_nullable.py`
      跑 upgrade + downgrade，
      assert head 後 `meeting_id` is_nullable + `user_id` NOT NULL + index 存在，downgrade 後 row null meeting_id 都被清掉。

- [x] 1.2 `packages/backend/meeting_playbook/attachments/models.py` 的 `MeetingAttachment` SQLAlchemy model：
      `meeting_id` 改成 `str | None`、加 `user_id: str` field、加對應 FK relationship。
      **驗證**：`tests/test_alembic_attachment_nullable.py` 補一個 case
      用 ORM 直接 insert `MeetingAttachment(meeting_id=None, user_id="u_x", ...)`
      不噴 type / DB error。

## 2. Backend：repository + validation 加 staging 支援

> 涵蓋 spec requirement「POST /api/attachments/staging uploads to user-scoped staging path」
> 與 design 決策 D3（staging 路徑 `_staging/{user_id}/`）跟 D6（per-user staging quota 10/60 MiB）。

- [x] 2.1 `packages/backend/meeting_playbook/attachments/repository.py`：
      `AttachmentRepository.create` 簽名擴 `meeting_id: str | None = None` + 新增 `user_id: str` 必選參數；
      新增 `list_staged_for_user(user_id)` 方法（`SELECT WHERE user_id = ? AND meeting_id IS NULL AND deleted_at IS NULL ORDER BY uploaded_at ASC`）；
      新增 `delete_staged(attachment_id, user_id)` 方法（unlink-and-soft-delete，scope `meeting_id IS NULL AND user_id = ?`，回 None 若不符合）；
      新增 `count_staged_for_user(user_id) -> (file_count, total_bytes)` 給 quota check 用。
      既有 `list_for_meeting`、`soft_delete`、`get_for_download` 行為**不變**。
      **驗證**：擴充 `packages/backend/tests/attachments/test_repository.py`
      新增四個 case：`test_create_with_null_meeting_id_persists_staged`、
      `test_list_staged_for_user_excludes_attached_and_other_user`、
      `test_delete_staged_returns_none_for_attached_row`、
      `test_count_staged_returns_sum_for_active_only`。

- [x] 2.2 `packages/backend/meeting_playbook/attachments/validation.py`：
      新增 `validate_staging_upload(content_type, filename, declared_bytes, *, staged_count, staged_bytes)` 函式。
      行為跟既有 `validate_upload` 一樣（whitelist、MIME → kind 對應、≤ 30 MiB single-file size），
      **但 quota check 換成 per-user staging：staged_count < 10、staged_bytes + declared_bytes ≤ 60 MiB**。
      Quota 失敗拋 `AttachmentValidationError("attachment.staging_quota_exceeded", ...)`。
      **驗證**：擴充 `packages/backend/tests/attachments/test_validation.py`
      新增 `test_validate_staging_upload_rejects_eleventh_file`、
      `test_validate_staging_upload_rejects_over_60mib_total`、
      `test_validate_staging_upload_accepts_within_quota`。

## 3. Backend：staging endpoints

> 涵蓋 spec requirement「POST /api/attachments/staging」、
> 「GET /api/attachments?status=pending」、
> 「DELETE /api/attachments/{id}」（meeting-attachment）。

- [x] 3.1 新檔 `packages/backend/meeting_playbook/attachments/staging_router.py`：
      `APIRouter(prefix="/api/attachments")` mount 三個 handler。
      `POST /staging`：multipart `file` → call `validate_staging_upload` → 寫檔到 staging path
      （`ATTACHMENT_DIR/_staging/{user_id}/{att_id}{ext}`）→ `repo.create(meeting_id=None, user_id=...)` → 回 201 + serialized row。
      `GET ""`：query `?status=pending` → call `list_staged_for_user` → 回 `{"attachments": [...]}`。
      任何其他 `status` 值 → 422 `attachment.invalid_status_filter`。
      `DELETE /{attachment_id}`：call `delete_staged` → None → 404 `attachment.not_found`；否則 unlink 檔 + 回 204。
      **驗證**：新測 `packages/backend/tests/attachments/test_staging_endpoints.py`
      8 個 case：upload 成功 + per-MIME 拒收 + quota 滿拒收 + list 排序 + list 排除 attached/other_user/soft-deleted + DELETE staged 成功 + DELETE attached 回 404 + DELETE 跨 user 回 404。

- [x] 3.2 `packages/backend/meeting_playbook/server.py`：
      `app.include_router(staging_router)` 加在既有 attachment router 之後。
      **驗證**：3.1 的測試本身會 fail 如果 router 沒掛上 (collection error)。

## 4. Backend：`POST /api/meetings` 加 file move + rollback

> 涵蓋 spec requirement modified「POST /api/meetings accepts an attachments list...」
> （meeting-management，已加 file move + rollback 語意）。
> 對應 design 決策 D4（os.rename → shutil.move fallback）跟 D5（attach 失敗 move 回 staging）。

- [x] 4.1 `packages/backend/meeting_playbook/meetings/router.py` 的 `create_meeting` handler：
      attach 步驟從「只 UPDATE meeting_id」擴成「UPDATE meeting_id + 搬檔」。
      新增 helper `_move_staged_to_meeting(att, meeting_id) -> new_path`：
      try `os.rename`、抓 `OSError EXDEV` fallback `shutil.move`、回新 path。
      Attach 每筆後同步 set `att.file_path = new_path`。
      **驗證**：擴充 `packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py`
      新增 `test_create_with_attachments_moves_files_to_meeting_dir`：建 staged → POST /api/meetings 帶 attachments[] → assert response 201 + 檔案在 `ATTACHMENT_DIR/{new_meeting_id}/` 底下、staging path 已消失、row 的 file_path 已更新。

- [x] 4.2 Attach 失敗 rollback：把已 move 的檔案 move 回 staging、`meeting_id` reset NULL、`file_path` 改回 staging 路徑、meeting row DELETE。
      實作為 try/except wrap 整個 attach + Playbook generation 區段；
      `RollbackContext` 在記憶體裡記錄「哪些 att 從哪 staging path 搬到哪 meeting path」，
      exception handler iterate 反向 move。
      **驗證**：新測 `packages/backend/tests/attachments/test_staging_attach_flow.py`
      三個 case：
      `test_generator_timeout_rolls_back_attach_step`（mock PlaybookGenerationTimeout → assert 檔案 in staging、row meeting_id NULL、meeting row 不存在）、
      `test_file_move_failure_aborts_meeting_create`（mock os.rename 拋 OSError、shutil.move 也炸 → 同樣 rollback）、
      `test_db_error_after_move_rolls_back_files`（mock db commit 失敗 → assert 檔案 move 回 staging）。

## 5. Backend：retention sweep + config

> 涵蓋 spec requirement「Retention job sweeps staged attachments older than the TTL」
> 與 design 決策 D7（沿用既有 job、TTL 24h）。

- [x] 5.1 `packages/backend/meeting_playbook/config.py`：
      加 `staged_attachment_ttl_hours: int = 24`。
      `.env.example` 加對應 `STAGED_ATTACHMENT_TTL_HOURS=24` 註解區段。
      **驗證**：擴充 `packages/backend/tests/test_config.py` 新增 `test_staged_attachment_ttl_default_24` 跟 `test_staged_attachment_ttl_env_override`。

- [x] 5.2 `packages/backend/meeting_playbook/retention/job.py` 的 `RecordingRetentionJob.cleanup`：
      在既有 30-day attached sweep 之後，再 sweep `meeting_id IS NULL AND deleted_at IS NULL AND uploaded_at < now() - STAGED_ATTACHMENT_TTL_HOURS hours` 的 row。
      Per row：try `Path(file_path).unlink(missing_ok=True)` 抓 OSError log + 繼續 → 然後 hard DELETE row（不是 soft delete）。
      **驗證**：擴充 `packages/backend/tests/retention/test_job.py`
      `test_cleanup_removes_staged_older_than_ttl` 跟 `test_cleanup_keeps_staged_younger_than_ttl`。

## 6. Frontend：staging API client

> 對應 design 決策 D8（新元件、不 reuse meeting-detail dropzone）的 client 端。

- [x] 6.1 `packages/web/src/lib/attachments-api.ts`：
      新增 `uploadStagedAttachment(file, onProgress) -> Promise<Attachment>`（XHR 跟既有 uploadAttachment 同結構，POST 到 `/api/attachments/staging`）；
      新增 `deleteStagedAttachment(id) -> Promise<void>`（DELETE 到 `/api/attachments/{id}`）。
      `listPendingAttachments` 函式本身不動（既有 graceful-fallback 邏輯保留，但現在 endpoint 真存在了所以正常情況回真資料）。
      `pendingAttachmentsQueryOptions` 同樣不動。
      新型別 `interface StagedAttachment` 或沿用 `PendingAttachment` —— 評估後沿用 `PendingAttachment` 但擴增 `bytes` `original_name` `kind` 欄位（跟 backend `Attachment` shape 對齊）。
      **驗證**：擴充 `packages/web/src/lib/attachments-api.test.ts`
      新增三個 case：`uploadStagedAttachment_posts_to_staging_endpoint`、
      `deleteStagedAttachment_calls_delete`、
      `uploadStagedAttachment_throws_AttachmentApiError_on_422`。

## 7. Frontend：StagedAttachmentDropzone 元件

> 涵蓋 spec requirement「Frontend StagedAttachmentDropzone uploads to staging and lists current staged」。

- [x] 7.1 新檔 `packages/web/src/components/staged-attachment-dropzone.tsx`。
      Props：`{ selectedIds: string[], onChange: (ids: string[]) => void }`（受控元件，父 form 持有 selected ids state）。
      內部 state：`uploads: { localId: string, file: File, progress: number, error?: string }[]` for in-flight UI；
      `staged: PendingAttachment[]` 來自 useQuery(pendingAttachmentsQueryOptions())。
      Render：上方 list 顯示 staged + uploading；每個 staged 有 remove 按鈕（call `deleteStagedAttachment` → invalidate query）；下方 dropzone（drag-drop + click-to-select）。
      Drop file → `uploadStagedAttachment(f, setProgress)` → 成功後 invalidate `["attachments", "pending"]` query + 把新 id push 進 `selectedIds`；失敗 → 顯示 localized error inline。
      `onChange` 在 staged 列表變動 (upload 完 / delete 完) 時 sync `selectedIds` 為 staged 全部 ids。
      **驗證**：新測 `packages/web/src/components/staged-attachment-dropzone.test.tsx`
      四個 case：render 空狀態（只有 dropzone）、render 帶 staged（list + remove 按鈕）、drop file 觸發 upload mutation、click remove 觸發 delete mutation。

## 8. Frontend：`/meetings/new` 換掉 invisible picker

- [x] 8.1 `packages/web/src/routes/meetings/new.tsx`：
      移除既有 `AttachmentPicker`（line ~443-485 那個 component 跟 line ~397 那個 mount）。
      改 mount `<StagedAttachmentDropzone selectedIds={selectedAttachments} onChange={setSelectedAttachments} />`。
      Submit handler 不變（`payload.attachments = selectedAttachments`）。
      **驗證**：擴充 `packages/web/src/routes/meetings/new.test.tsx`
      `test_attachments_dropzone_renders_unconditionally` (mock 空 pending → 仍渲染 dropzone，跟 invisible-empty-state 行為對立)、
      `test_form_submit_includes_staged_attachment_ids`（mock staged 兩個 → submit → assert POST body `attachments: [id1, id2]`）。

## 9. Frontend：i18n + CONTEXT.md

> i18n parity test 會擋住單邊新增 key 漏 sync 的情況。

- [x] 9.1 兩份 locale 同步新 keys：
      `meetings.new.staging.dropzone_label`（拖檔到這裡上傳到暫存區）、
      `meetings.new.staging.empty_hint`（尚未暫存任何附件）、
      `meetings.new.staging.remove_button`（移除）、
      `meetings.new.staging.uploading_label`（上傳中… {{percent}}%）、
      `errors.attachment.staging_quota_exceeded`（暫存附件超過 10 個或 60 MiB 上限）、
      `errors.attachment.invalid_status_filter`（不支援的 status query）。
      移除既有 `meetings.new.attachmentsLabel`、`attachmentsHint`、`attachmentsEmpty`（被新 staging keys 取代）。
      **驗證**：跑 `bun --filter @meeting-playbook/web test src/locales/locales.test.ts`
      （deep-equal parity test）綠燈。

- [x] 9.2 `CONTEXT.md` glossary 新增「**Staged attachment (暫存附件)**」條目：
      User-uploaded attachment with `meeting_id IS NULL`，由 `POST /api/attachments/staging` 建立，
      在 `/meetings/new` 拖檔時暫存到 `ATTACHMENT_DIR/_staging/<user>/`，建立會議時搬到
      `ATTACHMENT_DIR/<meeting_id>/`；24h 沒 attach 由 retention job 清掉。
      **驗證**：手動 grep `CONTEXT.md` 含「Staged attachment (暫存附件)」字串。

## 10. 端到端驗證

- [ ] 10.1 手動 E2E：開既有 meeting list → 按「新會議」→ `/meetings/new` 出現 dropzone（即使 staged 是空）→
      拖一個 PDF + 一張圖 → 看到 list 兩筆 + 上傳進度 → 改填表單其他欄位 → 按「建立」→
      navigate 到新 meeting → meeting detail 「附件」section 應該已經有那兩個檔。
      重複一次但這次 calendar preview 路徑（從 /calendar/upcoming 點 import）→ dropzone 也應該渲染、行為一致。
      第三次測 quota：連拖 11 個檔 → 第 11 個應該看到 localized error「暫存附件超過 10 個或 60 MiB 上限」。
      **驗證**：本 task 是手動 checklist，commit message 寫明三條 flow 都過。

- [x] 10.2 跑 full backend + web test：
      `psql postgresql://localhost:5432/meeting_playbook_test -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"` →
      backend pytest → web bun test。
      **驗證**：backend pass count 比 main 多至少 12 個（new staging + attach flow + retention + validation + config tests）、
      web pass count 比 main 多至少 7 個（new dropzone + api client tests + new.tsx）、0 fail。

## 11. Frontend：Dropzone batch upload + quota counter (pre-merge UX expansion)

> 涵蓋 spec requirement「Frontend StagedAttachmentDropzone uploads to staging and lists current staged」新加的 multi-file / truncation / counter / at-limit 行為（meeting-attachment）。
> 對應 design 決策「D10. Dropzone batch upload 採前端 truncation + sequential POST」與「D11. Quota counter 直接從 staged list 計算、達上限即 disable dropzone」。
> **Backend 不動** —— per-file `validate_staging_upload` 已在 task 2.2 落地、繼續是 quota 真相來源；truncation 純前端 UX 優化。

- [x] 11.1 `packages/web/src/components/staged-attachment-dropzone.tsx` —— 批次上傳：
      `<input type="file">` 加 `multiple` attribute；
      `_handleFiles(files: FileList)` 從只取 `files[0]` 改成 `Array.from(files)` 處理整批；
      新加純函式 `_truncateToQuota(files, currentCount, currentBytes, maxCount=10, maxBytes=60*1024*1024) -> { accepted: File[], dropped: number }`：
      **skip-and-continue 演算法** —— iterate files in drop order，維護 running `count` 跟 `bytes`；
      每個 file 試算「`count + 1 <= maxCount` 且 `bytes + file.size <= maxBytes`」，
      若兩條件都滿足則 push 進 accepted 並更新 running；否則跳過該檔（記入 dropped）、繼續看下一個；
      回 `{ accepted, dropped: files.length - accepted.length }`；
      上傳改 sequential `for...of` 配 `uploadMutation.mutateAsync(file)`（一個 await 完才下一個），共用同一個 progress UI；
      `dropped > 0` 時 `setErrorMessage` 為 `localizedErrorMessage("attachment.staging_batch_truncated", t, { dropped, accepted: accepted.length })`。
      **驗證**：擴 `packages/web/src/components/staged-attachment-dropzone.test.tsx` 三個 case —
      `test_drop_three_files_uploads_all_sequentially_within_quota`（assert 3 個 mutationFn call 依序、list 3 筆、單一 progress bar）、
      `test_drop_exceeds_count_quota_truncates_to_remainder`（mock 8 staged + drop 5 → assert 只 mutate 2 次 + warning render dropped=5 accepted=2）、
      `test_drop_exceeds_byte_quota_truncates_by_byte_prefix`（mock 已 58 MiB + drop [3 MiB, 1 MiB] → assert 只 mutate 1 MiB 那個）。

- [x] 11.2 `packages/web/src/components/staged-attachment-dropzone.tsx` —— quota counter + at-limit:
      新加純函式 `_computeUsage(rows) -> { count: number, bytes: number, atLimit: boolean }`（`atLimit = count >= 10 || bytes >= 60 * 1024 * 1024`）；
      dropzone CardContent 內**永遠 render** counter 一行：`<used>/10 個 · <bytesUsedFormatted>/60 MiB`（透過既有 `_formatBytes`），不論 rows 有沒有；
      `atLimit === true` 時：drop area 的 `onDragOver` handler 提早 return（不 setDragOver）、`onDrop` handler 提早 return（不 call `_handleFiles`）、`<input>` + upload button 加 `disabled` attr、
      empty-state / dropzone-label 文字換成 `t("meetings.new.staging.at_limit")`。
      **驗證**：擴同檔 test 四個 case —
      `test_counter_renders_current_count_and_bytes_formatted`（mock 3 staged 1+2+3 MiB → assert counter 文字 `3/10 個 · 6.0 MB / 60 MiB` 樣式）、
      `test_at_count_limit_disables_dropzone_and_renders_hint`（mock 10 staged → drop event 不觸發 mutate + button disabled + at-limit text render）、
      `test_at_byte_limit_disables_dropzone`（mock 1 staged @ 60 MiB → 同 disabled）、
      `test_remove_from_at_limit_state_reenables_dropzone`（mock 10 → click remove → button enabled + counter 9/10）。

- [x] 11.3 i18n: 兩份 locale 同步加 3 個 keys (parity test 會擋漏邊):
      `meetings.new.staging.counter_label` —
      zh-TW: `"{{used}} / {{max}} 個 · {{bytesUsed}} / {{bytesMax}}"`；
      en: `"{{used}} / {{max}} files · {{bytesUsed}} / {{bytesMax}}"`。
      `meetings.new.staging.at_limit` —
      zh-TW: `"已達暫存區上限（10 個 / 60 MiB）"`；
      en: `"Staging limit reached (10 files / 60 MiB)"`。
      `errors.attachment.staging_batch_truncated` —
      zh-TW: `"拖入 {{dropped}} 個檔，配額只上傳前 {{accepted}} 個"`；
      en: `"Dropped {{dropped}} files, only the first {{accepted}} fit the staging quota"`。
      `staging_batch_truncated` 是純前端 error code（backend 不會回），放 `errors.attachment.*` 維持命名 namespace 一致。
      **驗證**：`bun --filter @meeting-playbook/web test src/locales/locales.test.ts`（deep-equal parity test）綠燈；
      新測 `packages/web/src/lib/i18n-errors.test.ts` 加 `test_localized_message_for_staging_batch_truncated_interpolates_counts`（call `localizedErrorMessage("attachment.staging_batch_truncated", t, { dropped: 5, accepted: 2 })` → assert 中文回 `"拖入 5 個檔，配額只上傳前 2 個"`）。

- [ ] 11.4 手動 E2E (補充 task 10.1 的 four-flow checklist):
      A) `/meetings/new` 拖 3 個檔（PDF + PNG + DOCX、合計 < 60 MiB）→ counter 從 `0/10 · 0 B/60 MiB` 走到 `3/10 · X MB/60 MiB`、list 3 筆、單一 progress bar 順序遞進。
      B) 接著拖 5 個（共 8 個尚未達上限）→ counter 變 `8/10`；再拖 5 個 → 看 truncation warning「拖入 5 個檔，配額只上傳前 2 個」、counter 變 `10/10`、dropzone 變 disabled（drag-over 不亮、button 不可按）、empty-state 變「已達暫存區上限（10 個 / 60 MiB）」。
      C) 點任一筆 remove 按鈕 → counter 變 `9/10`、dropzone 重新 enabled、可繼續拖。
      D) 按「建立」送 form → 新 meeting detail 「附件」section 顯示 9 個檔；回 `/meetings/new` → dropzone 變回 `0/10` 空 state（pendingAttachments query 重 fetch）。
      **驗證**：本 task 是手動 checklist；PR 描述 / commit 訊息要寫明 A/B/C/D 四條 flow 都過。

## 12. Backend + i18n：per-meeting quota 對齊 staging quota (UX consistency follow-up)

> Sean 在 task 11.4 手測時發現 `/meetings/new` 顯示「10 / 10」counter、但
> `/meetings/{id}` 既有 dropzone 仍 hit「最多 5 個」422 — 兩個 dropzone 數字
> 不一致的 UX 訊號讓使用者困惑。對應 design 決策「D12. Per-meeting attachment
> quota 對齊 staging quota（10 個 / 60 MiB）」，spec 用 MODIFIED 改 main
> capability `meeting-attachment` 的 "Upload validation enforces..." 跟
> "AttachmentDropzone component renders list..." 兩個 requirement。
> Frontend `<AttachmentDropzone>` 元件依賴 i18n key 顯示 hint、沒 hardcode
> 數字，所以這 group 沒 frontend code 改動，只改 backend constants + i18n。

- [x] 12.1 `packages/backend/meeting_playbook/attachments/validation.py`：
      `MAX_ATTACHMENTS_PER_MEETING: Final[int] = 5` → `10`；
      `MAX_BYTES_PER_MEETING: Final[int] = 30 * 1024 * 1024` → `60 * 1024 * 1024  # 60 MiB`。
      File 頂部 docstring 第 (2) / (3) 點數字同步 (5 → 10、30 MiB → 60 MiB)。
      `validate_upload` 函式內的 docstring 提到 `30 MiB` 處同步。
      **驗證**：擴 `packages/backend/tests/attachments/test_validation.py` —
      把 `test_rejects_sixth_attachment` rename 成
      `test_rejects_eleventh_attachment` + assert per-meeting 10 個 row 後第 11 個拋
      `attachment.too_many`；把 `test_rejects_when_total_exceeds_30mib` rename 成
      `test_rejects_when_total_exceeds_60mib` + assert 58 MiB 既有 + 3 MiB 新檔
      拋 `attachment.quota_exceeded`；既有「接受 5 個內」test rename 成
      「接受 10 個內」。

- [x] 12.2 i18n: 兩份 locale 同步改 3 個 keys（parity test 會擋漏邊）:
      `errors.attachment.too_many` —
      zh-TW: `"每場會議最多可上傳 5 個附件"` → `"每場會議最多可上傳 10 個附件"`；
      en: `"Each meeting allows at most 5 attachments"` → `"Each meeting allows at most 10 attachments"`。
      `errors.attachment.quota_exceeded` —
      zh-TW: `"已超過每場會議 30MB 上限"` → `"已超過每場會議 60 MiB 上限"`；
      en: `"Per-meeting 30MB quota exceeded"` → `"Per-meeting 60 MiB quota exceeded"`。
      `meetings.detail.attachments.hintLimit` —
      zh-TW: `"最多 5 個檔案，30MB 上限"` → `"最多 10 個檔案，60 MiB 上限"`；
      en: `"Max 5 files, 30MB total"` → `"Max 10 files, 60 MiB total"`。
      **驗證**：`bun --filter @meeting-playbook/web test src/locales/locales.test.ts`（deep-equal parity）綠燈。

- [ ] 12.3 手動 E2E：開既有 meeting detail 頁、在 attachment section 拖 10 個檔
      → 都成功上傳；拖第 11 個 → backend 回 422 `attachment.too_many` + 前端
      顯示「每場會議最多可上傳 10 個附件」。Dropzone hint 文字應顯示
      「最多 10 個檔案，60 MiB 上限」。
      **驗證**：本 task 是手動 checklist；PR 描述記錄 OK。
