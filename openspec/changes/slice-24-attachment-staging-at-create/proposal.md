## Why

Slice-20a 落地了「對既有 meeting 上傳附件」的能力，slice-20b 加了 calendar
preview-and-confirm 流程並擴 `POST /api/meetings` 接受 `attachments[]` —— **但
S20a 沒做 orphan attachment**，所以使用者根本沒辦法在「建立 meeting 之前」上
傳檔案、S20b 的 attachment picker 永遠是 invisible empty state。

實際情境：使用者從 Calendar 預覽預填表單時，最自然的 UX 是「在 /meetings/new
表單裡直接拖檔上傳」—— 因為這時候才知道附件要掛到哪場會議。先去別處上傳再
回來挑、或先建空會議再去 detail 頁上傳，都比直接拖在表單上多兩步。

S24 補上 staging 層 ——「先上傳到暫存、建立會議時一併綁定」—— 把 S20b 已經
預留的 `attachments[]` 通道實際接通，並把 `/meetings/new` 的 picker 升級為
真的可用的 dropzone。

## What Changes

- **Schema：`meeting_attachment` 表開放暫存態**
  - Alembic migration：`meeting_attachment.meeting_id` 改 NULLABLE（既有 FK
    CASCADE 保留 —— meeting 被刪、attachment row CASCADE 走）
  - 新增 `user_id TEXT NOT NULL` column（FK to `user.id`，無 ON DELETE rule
    因為 user 刪除走 better-auth 自家邏輯）；backfill 既有 row 透過 JOIN
    meeting 取 user_id
  - Index：`(user_id, meeting_id NULLS FIRST, uploaded_at DESC)` 加速「列
    staged for user」查詢
- **Backend：staging endpoints**
  - `POST /api/attachments/staging`：multipart upload，把檔案寫到
    `ATTACHMENT_DIR/_staging/{user_id}/{att_id}{ext}`，建立
    `meeting_attachment` row（`meeting_id=NULL`、`user_id=current`）。
    回 201 + `Attachment` shape。
  - `GET /api/attachments?status=pending`：列當前 user 的
    `meeting_id IS NULL AND deleted_at IS NULL` rows。
  - `DELETE /api/attachments/{id}`：unlink 暫存檔 + 刪 row。只接受
    `meeting_id IS NULL` 的；已綁 meeting 的走既有
    `DELETE /api/meetings/{id}/attachments/{att_id}` 路徑。
- **Backend：`POST /api/meetings` attach 邏輯擴充**
  - S20b 已落地的 `attachments[]` 驗證從「row exists + meeting_id IS NULL +
    user owns it」沿用；新增「實體搬檔」步驟 —— 把每個 attachment 從
    `ATTACHMENT_DIR/_staging/{user_id}/{att_id}{ext}` move 到
    `ATTACHMENT_DIR/{new_meeting_id}/{att_id}{ext}`，row 的 `file_path`
    更新、`meeting_id` 設成新 meeting id
  - Move 走 `os.rename`（同檔案系統 atomic）；fallback 不同 fs 時走
    `shutil.move` + delete source
  - Meeting 建立失敗 / generator 失敗導致 rollback 時，已 move 的檔案要
    move 回 staging（讓使用者不丟資料）
- **Backend：Staging quota + cleanup**
  - 每個 user 同時可有的 staged attachment 上限：**10 files / 60 MiB**（兩倍
    per-meeting 上限，因為使用者可能同時準備多場會議的素材）
  - 既有 retention cleanup job 擴：staged row 沒在 24h 內 attach 視為孤兒，
    sweep（unlink 檔 + 刪 row）。`STAGED_ATTACHMENT_TTL_HOURS` 新 env
    （default 24）
- **Frontend：新 `<StagedAttachmentDropzone>` 元件**
  - 跟既有 `<AttachmentDropzone>`（meeting-detail）分開，因為這個是 user-
    scoped、不是 meeting-scoped
  - 拖檔 → POST staging → 加進 staged list；list 上每筆有「移除」按鈕呼叫
    DELETE
  - 上傳進度顯示、whitelist + quota 錯誤訊息透過 `localizedErrorMessage`
    本地化
- **Frontend：`/meetings/new` 換掉 invisible picker**
  - 移除既有 `AttachmentPicker` empty-state-only 元件
  - 改 mount `<StagedAttachmentDropzone>` —— 一律 render（不論有沒有 staged）
  - 表單提交時把 `selectedAttachments` 改成「全部 staged 的 ids」（使用者沒
    勾選就是不附加 → 改成全部都會 attach；要排除某個就在 dropzone 上「移除」）
- **Frontend：`listPendingAttachments` 變成真實 query**
  - 既有 `attachments-api.ts` 的 graceful-fallback 邏輯（404 → []）保留，但
    現在 endpoint 真的存在了，正常情況回真的 list

## Non-Goals

- **不改 meeting-detail 的 `<AttachmentDropzone>`**：那個還是 meeting-scoped、
  上傳直接到 `POST /api/meetings/{id}/attachments`、行為一字不變
- **不做 tus / chunked upload**：staging 跟既有 meeting-scoped upload 都是
  single POST multipart；30 MiB 上限下，slow network 也能在 reasonable 時間
  完成。tus 留給 `slice-14-offline-ingest` 既有的 audio ingest 場景用
- **不做 staged attachment 編輯 / 重新命名**：上傳後就只能刪除重傳
- **不做跨 meeting 共用附件**：staging 的目的是「未來綁某 meeting」，attach
  後就鎖住、不能 detach 再 attach 到另一場
- **不做 staging 的 download endpoint**：staged 不是分享給人的，是準備中
  狀態；要看內容就先 attach 再用 meeting-scoped download
- **不調 retention 30-day window**：staged sweep 是另一條軌（24h），跟
  recording retention 不互相干擾
- **不擴 Playbook / Summary multimodal**：staged 不被當作 context；只有
  attach 後變成 `meeting_id` 非 null 才會進 S20c multimodal pipeline
- **不改 slice-20b 的 calendar preview 預填邏輯**：calendar preview 帶來的
  附件還是走 staging dropzone 上傳，跟手動 create 沒分別
- **不引入 staging UI 的拖檔 reorder / 排序**：list 維持上傳順序

## Capabilities

### New Capabilities

(none — 本 slice 不引入新 capability，所有變動 fold 進兩個既有的)

### Modified Capabilities

- `meeting-attachment`：開放 `meeting_id` 暫存態（NULL = staged）、新 user_id
  column、staging endpoints (POST / GET / DELETE)、user-scoped staging
  quota、retention cleanup 擴。S20a 的 per-meeting upload / list / delete /
  download 行為不變
- `meeting-management`：clarify「`POST /api/meetings` 的 `attachments[]` 必
  須是 staged（`meeting_id IS NULL` + 屬於 current user）」—— 從 S20b 寫的
  通用「pre-uploaded attachments」收緊成「staged attachments only」。Attach
  時除了 set `meeting_id` 還會做檔案 move

## Impact

- Affected specs: meeting-attachment, meeting-management
- Affected code:
  - New:
    - packages/backend/alembic/versions/0019_attachment_nullable_meeting.py
    - packages/backend/meeting_playbook/attachments/staging_router.py
    - packages/backend/tests/attachments/test_staging_endpoints.py
    - packages/backend/tests/attachments/test_staging_attach_flow.py
    - packages/backend/tests/attachments/test_staging_cleanup.py
    - packages/web/src/components/staged-attachment-dropzone.tsx
    - packages/web/src/components/staged-attachment-dropzone.test.tsx
  - Modified:
    - packages/backend/meeting_playbook/attachments/models.py
    - packages/backend/meeting_playbook/attachments/repository.py
    - packages/backend/meeting_playbook/attachments/router.py
    - packages/backend/meeting_playbook/attachments/validation.py
    - packages/backend/meeting_playbook/config.py
    - packages/backend/meeting_playbook/meetings/router.py
    - packages/backend/meeting_playbook/retention/job.py
    - packages/backend/meeting_playbook/server.py
    - packages/backend/tests/conftest.py
    - packages/backend/tests/attachments/test_repository.py
    - packages/backend/tests/attachments/test_endpoints.py
    - packages/backend/tests/attachments/test_validation.py
    - packages/backend/tests/retention/test_job.py
    - packages/backend/tests/test_config.py
    - packages/backend/tests/meetings/test_create_with_calendar_and_attachments.py
    - packages/web/src/lib/attachments-api.ts
    - packages/web/src/lib/attachments-api.test.ts
    - packages/web/src/routes/meetings/new.tsx
    - packages/web/src/routes/meetings/new.test.tsx
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
    - .env.example
    - CONTEXT.md
  - Removed: (none)
