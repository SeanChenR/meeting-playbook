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
