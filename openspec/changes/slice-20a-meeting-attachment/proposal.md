> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/21
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16
> Unlocks: slice-20b-calendar-attachment-preview, slice-20c-multimodal-playbook-input

## Why

目前 Playbook 只能吃文字欄位，但實際會前準備常有 PDF 提案書、報價單截圖、合約 docx 等資料。沒地方掛這些檔案，使用者只能複製貼上摘要進 Playbook 欄位，失去原始格式與細節。S20a 引入 **Meeting attachment (會議附件)** 基礎建設：schema、CRUD endpoints、dropzone UI。這是 S20b（calendar event 自動帶附件預覽）與 S20c（multimodal playbook generator 把附件吃進 Gemini）的前置 slice。

## What Changes

- 新增 schema `meeting_attachment(id, meeting_id, file_path, kind, original_name, bytes, uploaded_at, deleted_at)`；FK `meeting_id` → `meeting.id` ON DELETE CASCADE
- 4 個新 endpoints：`GET / POST / DELETE / GET .../download` 對 `/api/meetings/{id}/attachments`
- 格式 whitelist：`image/jpeg|png|webp`、`application/pdf`、`application/vnd.openxmlformats-officedocument.wordprocessingml.document` (docx)、`text/plain`、`text/markdown`
- 上限：每場 meeting 最多 5 個檔案、總量 ≤ 30MB（per meeting，非 per file）
- 新 `<AttachmentDropzone>` 元件掛在 meeting detail：列已掛附件 + drag-drop 區 + 上傳進度 + 下載 / 刪除按鈕
- Retention 沿用既有 30 天 recording cleanup job（讀 `meeting_attachment.deleted_at`），不另開 job
- 新環境變數 `ATTACHMENT_DIR`（default `~/MeetingPlaybook/attachments`）寫入 `.env.example`
- `CONTEXT.md` glossary 加「Meeting attachment (會議附件)」

## Non-Goals

- Calendar event 自動帶附件預覽（屬 S20b）
- Playbook generator 把附件內容吃進 LLM prompt（屬 S20c — multimodal input）
- 跨 meeting 附件搜尋 / 全文索引（v1 不做；附件純儲存 + 下載）
- 附件版本管理（同名上傳直接覆蓋為「新附件 row」，舊 row 標 deleted_at；不留 version chain）
- 附件分享連結 / 公開 URL（沿用 auth，下載需登入 + 該 meeting 擁有者）
- 結構化解析（從 PDF 抽文字、從 docx 抽段落）— 屬 S20c 的 `AttachmentProcessor`，本 slice 純儲存
- tus chunked upload — S14 offline ingest 才導入 tus；本 slice 先用單一 POST + multipart，等 tus 抽象成共用模組再切換
- 附件直接黏進 transcript / summary 區段（v1 附件純掛 meeting metadata）

## Capabilities

### New Capabilities

- `meeting-attachment`: meeting-level 附件的儲存、CRUD endpoints、whitelist + quota 驗證、dropzone UI、與 retention cleanup 整合。

### Modified Capabilities

- `recording-retention`: 既有 `cleanup` job 擴大掃除範圍至 `meeting_attachment` row（讀 `uploaded_at` + `deleted_at`），不另開 retention 設定；30 天門檻沿用 `RECORDING_RETENTION_DAYS`。
- `meeting-detail-layout`: meeting detail 新增「附件區」(`<AttachmentDropzone>`)，位置與其他三欄共存；layout switcher（stack / columns）行為不變。

## Impact

- New env vars: `ATTACHMENT_DIR` (default `~/MeetingPlaybook/attachments`)
- Affected specs:
  - New: `openspec/specs/meeting-attachment/spec.md`
  - Modified: `openspec/specs/recording-retention/spec.md`, `openspec/specs/meeting-detail-layout/spec.md`
- Affected code:
  - New: `packages/backend/meeting_playbook/attachments/__init__.py`, `packages/backend/meeting_playbook/attachments/models.py`, `packages/backend/meeting_playbook/attachments/repository.py`, `packages/backend/meeting_playbook/attachments/router.py`, `packages/backend/meeting_playbook/attachments/validation.py`, `packages/backend/alembic/versions/XXXX_meeting_attachment.py`, `packages/web/src/components/attachment-dropzone.tsx`, `packages/web/src/components/attachment-dropzone.test.tsx`, `packages/web/src/lib/attachments-api.ts`
  - Modified: `packages/backend/meeting_playbook/retention/job.py`, `packages/backend/meeting_playbook/server.py`, `packages/backend/meeting_playbook/config.py`, `packages/web/src/routes/meetings/detail.tsx`, `packages/web/src/locales/zh-TW.json`, `packages/web/src/locales/en.json`, `packages/web/src/lib/i18n-errors.ts`, `CONTEXT.md`, `.env.example`, `README.md`
  - Removed: (none)
