## Context

S20a 是 S20 系列（multimodal playbook input）的第一片：先把「附件」這個 first-class 物件做出來。目前 Playbook 只有純文字欄位，會前準備的 PDF 提案書、報價單截圖、合約 docx 沒地方掛。S20a 純做基礎建設 — schema、4 個 endpoint、dropzone UI、retention 整合；不動 Playbook generator（屬 S20c）、不動 Calendar preview（屬 S20b）。

附件儲存採「meeting metadata」模型：每場 meeting 自己一組附件，FK CASCADE 到 `meeting.id`。Retention 沿用既有 30 天 recording cleanup job — 多掃一張表，不另開設定。

格式 whitelist 與大小上限：`image/jpeg|png|webp`、`application/pdf`、`docx`、`text/plain`、`text/markdown`；每場 meeting 最多 5 個檔案、總量 ≤ 30MB（per meeting，非 per file）。Whitelist 鎖死是為了不放任意 binary blob 進來 — S20c multimodal generator 才需要知道附件型別來決定如何處理。

`AttachmentProcessor`（per-type 解析器，例：PDF → 文字、docx → 段落、image → vision input）屬 S20c 範圍；S20a 純儲存，不解析。但本 slice 在 schema 上預留 `kind` 欄位（enum: `image / pdf / docx / text / markdown`）讓 S20c 直接 dispatch，不用回頭改 schema。

## Goals / Non-Goals

**Goals:**

- Meeting attachment schema 落地 + Alembic migration（up/down 可逆）
- 4 個 CRUD endpoints（list / upload / delete / download）+ 整合測試含 quota / whitelist reject
- Meeting detail 新增 `<AttachmentDropzone>`，UI 包含已掛附件列表 + drag-drop 區 + 上傳進度 + 下載 / 刪除
- 附件 retention 沿用既有 30 天 cleanup job
- `ATTACHMENT_DIR` env var 文件化 + glossary + i18n 雙 locale
- 為 S20b / S20c 預留 extension point — 不在本 slice 動 LLM / Calendar 流程

**Non-Goals:**

- 把附件內容餵進 Gemini（屬 S20c — `AttachmentProcessor` + multimodal prompt 組裝）
- 從 Calendar event 自動帶附件（屬 S20b — Calendar API 抓附件 → presigned URL → 本機暫存）
- 跨 meeting 附件搜尋 / 全文索引（v1 純儲存）
- 附件版本管理 / 附件分享連結（公開 URL）
- 附件內容結構化解析 — 留 S20c
- 改用 tus chunked upload（S14 引入 tus 後 S20 / S14 可再共用上傳基礎建設）
- 直接 inline preview 附件（純連結 + 下載；preview 由瀏覽器原生處理）

## Decisions

### Schema：`meeting_attachment` 獨立表 + `kind` enum

新表 `meeting_attachment(id UUID PK, meeting_id UUID FK CASCADE, file_path TEXT NOT NULL, kind TEXT NOT NULL CHECK IN ('image','pdf','docx','text','markdown'), original_name TEXT NOT NULL, bytes INTEGER NOT NULL CHECK > 0, uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(), deleted_at TIMESTAMPTZ NULL)`。`kind` 用 CHECK constraint 而非 pg enum type — enum type 加減值要寫 migration，CHECK constraint 改動成本低且 S20c 可能要加 `xlsx / pptx` 之類新型別。**Alternative considered**：把附件存進 `meeting.metadata` JSONB 欄位 — 否決，附件是 list-of-records 性質，獨立表方便加 index、軟刪 retention、未來 CASCADE rules；JSONB 嵌入也讓 retention job 改動成本變高。

### Storage：本機檔案系統 `~/MeetingPlaybook/attachments/{meeting_id}/{attachment_id}.<ext>`

附件儲存路徑與 recordings 同邏輯 — 一個本機目錄、檔名走 UUID（避免名稱衝突）、副檔名沿用 `kind` 對應的 canonical extension（`image → 原 mime subtype`、`pdf → .pdf`、`docx → .docx`、`text → .txt`、`markdown → .md`）。`original_name` 欄位另存使用者原始檔名供下載時還原。`ATTACHMENT_DIR` 走 `Settings` + `.env.example`。**Alternative considered**：把附件存進 DB BYTEA — 否決，30MB / meeting × N meeting 進 DB 會拖慢 backup / restore；recordings 已建立「raw 檔案系統 + DB metadata」pattern，附件沿用更一致。

### Validation：whitelist mime + per-meeting quota（5 檔 / 30MB）

POST 路徑做三道驗證 — (1) `Content-Type` 在 whitelist；(2) 該 meeting 既有 active（`deleted_at IS NULL`）附件數 < 5；(3) 該 meeting 既有 active 附件 `SUM(bytes) + 新檔 bytes ≤ 30 * 1024 * 1024`。違規回 HTTP 422 + 對應 error_code（`attachment.unsupported_format` / `attachment.too_many` / `attachment.quota_exceeded`）。Per-meeting quota 而非 per-user quota — 跟 ADR-0020 retention 同樣 per-meeting scoped；避免一場 meeting 吃掉整個 user 配額。**Alternative considered**：放寬到 10 檔 / 50MB — 否決，S20c multimodal generator 餵進 Gemini 的 input token 量會線性放大，5 檔已是 LLM context 合理上限。**Alternative considered**：sniff magic bytes 驗證真實 mime（避免改副檔名假裝 PDF）— 否決 v1 範圍，單一使用者本機環境信任邊界內；S20c 真要把檔案餵 LLM 時再加 magic bytes 驗證。

### Retention：擴 `RecordingRetentionJob.cleanup` 多掃一張表

不開新 job、不開新 env var。`packages/backend/meeting_playbook/retention/job.py` 的 `cleanup` 函數內加第二段查詢：`SELECT meeting_attachment WHERE uploaded_at < (now - retention_days days) AND deleted_at IS NULL`，逐筆 `Path(att.file_path).unlink()` + 設 `deleted_at = now`。Idempotency 規則沿用：第二次跑同 `now` 應零 unlink、零 row update。**Alternative considered**：開新 `AttachmentRetentionJob` 與獨立 env var `ATTACHMENT_RETENTION_DAYS` — 否決，使用者心智模型「附件跟 recording 一樣 30 天會清」單一變數最簡；獨立 job 增加維運面積無對應收益。

### API contract：4 個 endpoints under `/api/meetings/{id}/attachments`

- `GET /api/meetings/{id}/attachments` → 200 + `{attachments: [{id, kind, original_name, bytes, uploaded_at}, ...]}`，只回該 meeting 該 user owned 且 `deleted_at IS NULL` 的 row。
- `POST /api/meetings/{id}/attachments` → multipart `file` field，驗證通過 → 200 + `{id, kind, original_name, bytes, uploaded_at}`；驗證失敗 → 422 + `{error_code, message}`。
- `DELETE /api/meetings/{id}/attachments/{attachment_id}` → 設 `deleted_at = now()` + `Path(file_path).unlink(missing_ok=True)`；回 204。**軟刪 + 硬刪檔案**：DB row 留下做 audit；磁碟 WAV 立即清掉省空間，沿用 recording 既有 pattern。
- `GET /api/meetings/{id}/attachments/{attachment_id}/download` → `FileResponse` 串流檔案 + `Content-Disposition: attachment; filename="<original_name>"`。

Auth：所有 endpoint 走 `X-User-Id` header（per gateway invariant），repository 層驗該 `meeting_id` 屬於該 user。**Alternative considered**：用 `/api/attachments/{id}` flat namespace — 否決，巢狀路徑讓「該 meeting 的所有附件」這個查詢語意明確；前端 cache invalidation 也好寫（按 meeting_id key 起來）。

### Frontend：`<AttachmentDropzone>` 元件 + 上傳進度（XMLHttpRequest）

新 `packages/web/src/components/attachment-dropzone.tsx`，用 `react-dropzone`（已在 web package 內，slice-14 引入）+ `XMLHttpRequest.upload.onprogress` 顯示百分比。元件包含：
- 既有附件列表（kind icon + 原檔名 + 大小 + 上傳時間 + 下載 / 刪除按鈕）
- Drag-drop 區（accept whitelist mime + 顯示「最多 5 檔 / 30MB」提示）
- 上傳進度條（per-file，每檔 X% 顯示在該檔卡片上）
- 錯誤訊息（驗證失敗 → 透過 `localizedErrorMessage` 顯示對應 i18n）

掛載點：`packages/web/src/routes/meetings/detail.tsx` 在 playbook pane 下方加一個 collapsible section「附件 / Attachments」，default expanded；不動既有 layout switcher / 三欄結構。**Alternative considered**：把 dropzone 變成獨立 pane 進三欄 — 否決，附件是 metadata 級別資訊（重要但不是主要工作區），跟著 playbook 同邊欄較自然；S20c 把附件吃進 generator 時 UI 動線也順。

### `kind` 推斷邏輯

POST 接到檔案後，後端透過 `Content-Type` header + 副檔名雙保險推斷 `kind`：先看 `Content-Type` 是否在 whitelist 對應表內 → 不在再看副檔名是否在 known extension 對應表內 → 都不在 reject。對應表：

| Content-Type / extension | kind |
|--------------------------|------|
| `image/jpeg`, `.jpg / .jpeg` | `image` |
| `image/png`, `.png` | `image` |
| `image/webp`, `.webp` | `image` |
| `application/pdf`, `.pdf` | `pdf` |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `.docx` | `docx` |
| `text/plain`, `.txt` | `text` |
| `text/markdown`, `.md`, `.markdown` | `markdown` |

**Alternative considered**：強制只看 mime — 否決，瀏覽器對 `.md` 常給 `application/octet-stream`，雙保險避免使用者體驗壞掉。

## Implementation Contract

- **Behavior**: 使用者在 meeting detail 頁可拖檔（或點按鈕選檔）上傳附件；上傳成功後立即顯示在已掛附件列表內，可下載 / 刪除；每場 meeting 最多 5 檔、總量 30MB；超量或非 whitelist 格式上傳時 UI 顯示本地化錯誤；附件超過 30 天會被 retention job 自動清掉（檔案從磁碟移除，DB row 標 `deleted_at`）。
- **Data shape (schema)**:
  ```
  meeting_attachment(
    id           UUID PK,
    meeting_id   UUID NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    file_path    TEXT NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('image','pdf','docx','text','markdown')),
    original_name TEXT NOT NULL,
    bytes        INTEGER NOT NULL CHECK (bytes > 0),
    uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ NULL
  )
  ```
- **Interface (Python)**:
  - `AttachmentRepository.list_for_meeting(meeting_id, user_id) -> list[Attachment]`（僅 active，`deleted_at IS NULL`）
  - `AttachmentRepository.create(meeting_id, kind, original_name, file_path, bytes) -> Attachment`
  - `AttachmentRepository.soft_delete(attachment_id, user_id) -> Attachment`
  - `AttachmentRepository.get_for_download(attachment_id, user_id) -> Attachment | None`
  - `validate_upload(content_type, declared_name, declared_bytes, existing_attachments) -> tuple[kind, error_code | None]`（raise 設計 — 違規 raise `AttachmentValidationError(error_code)`）
- **HTTP endpoints**: `GET / POST / DELETE / GET .../download` 對 `/api/meetings/{id}/attachments` — 詳見 Decisions 「API contract」。
- **Failure modes**:
  - 上傳格式不在 whitelist → 422 `attachment.unsupported_format`
  - 附件數 >= 5 → 422 `attachment.too_many`
  - 累計 bytes > 30MB → 422 `attachment.quota_exceeded`
  - 該 meeting 不存在或不屬於該 user → 404（不揭露存在性）
  - 該 attachment 不存在或不屬於該 user → 404
  - 下載時磁碟檔已被 retention 清掉 → 410 `attachment.expired`
- **Retention integration**: `RecordingRetentionJob.cleanup` 同一個 transaction 內處理 recording 與 attachment，兩段查詢；`AttachmentRow.deleted_at` 設定後不再被掃到（idempotency）。
- **Acceptance criteria**:
  1. `uv run pytest packages/backend/tests/attachments/` 全綠（含 quota / whitelist reject 整合測試 + retention 整合測試）
  2. `uv run pytest packages/backend/tests/test_alembic_meeting_attachment.py` 跑 up → down → up 三輪可逆
  3. `bun --filter @meeting-playbook/web test attachment-dropzone` 全綠（含 drag-drop、上傳進度、刪除、錯誤訊息渲染）
  4. `bun --filter @meeting-playbook/web test src/locales/locales.test.ts` 仍綠（i18n 雙 locale 同步）
  5. `grep ATTACHMENT_DIR .env.example` 命中、`grep -F 'Meeting attachment' CONTEXT.md` 命中
  6. 手動 e2e：上傳 PDF → 列表顯示 → 下載成功還原檔名 → 刪除消失；再上傳 6 個檔案第 6 個被 reject；上傳 docx 35MB（單檔超 30MB）被 reject。
- **Scope boundary** — In scope：meeting-attachment 模組、4 endpoints、Alembic migration、retention job 擴充、`<AttachmentDropzone>` 元件、meeting detail 整合、`ATTACHMENT_DIR` config、glossary、i18n 字串。Out of scope：附件內容解析（S20c）、Calendar 自動帶附件（S20b）、tus 上傳（S14 抽象後再切）、附件版本管理、附件搜尋、附件分享連結、附件 inline preview。

### Per-file-type 行為表（給 AttachmentProcessor TDD 用 — 本 slice 只驗 storage，本表為 S20c 預備）

S20a 只驗證 storage 行為（accept / reject / persist / serve），不解析內容。下表列出每種 `kind` 在 S20a 必須滿足的「存得進 / 拿得出」契約：

| kind | accept (mime / ext) | reject 條件 | S20a 必驗 happy path | S20a 必驗 failure |
|------|---------------------|-------------|----------------------|-------------------|
| image | jpeg / png / webp | 非 whitelist mime | 上傳 200KB PNG → 200 + 下載回原 bytes | 上傳 BMP → 422 unsupported |
| pdf   | application/pdf, .pdf | 非 PDF | 上傳 1MB PDF → 200 + 下載 bytes 與原檔一致 | 上傳改副檔名 `.pdf` 的 zip → S20a 不驗 magic bytes，因此 mime 是 PDF 就 accept（S20c 再加 sniff） |
| docx  | OOXML wordprocessingml, .docx | 非 docx mime | 上傳 500KB docx → 200 + 下載還原 | 上傳 35MB docx → 422 quota_exceeded |
| text  | text/plain, .txt | 非 plain text | 上傳 5KB .txt → 200 + 下載 | (隨 quota 驗證) |
| markdown | text/markdown, .md, .markdown | 非 markdown | 上傳 12KB .md → 200 + 下載原樣 | (隨 quota 驗證) |

**重要**：本表只是 S20a 的 storage layer TDD checklist。S20c 的 `AttachmentProcessor` 會在這張表多一欄「parse output」（image → base64 vision input、pdf → 文字、docx → 段落、text/md → 字串），那是 S20c 範圍，本 slice 不實作。

## Risks / Trade-offs

- **沒做 magic-bytes sniff** → 使用者改副檔名假冒 mime 可繞過 whitelist。Mitigation: 單一使用者本機環境信任邊界內可接受；S20c 真要把檔案餵 LLM 時加 magic bytes 驗證（攻擊面是 LLM 端而非 storage 端）。
- **附件 retention 與 recording 共用 cleanup transaction** → 一個附件 unlink 失敗可能影響 recording 那段 commit。Mitigation: cleanup 內每筆 unlink 例外獨立 try/except + 該筆 row 不 set `deleted_at`（沿用既有 recording cleanup 行為），整個 transaction 仍能正常 commit 其他成功的 row。
- **`<AttachmentDropzone>` 同時上傳多檔時逐檔順序 POST** → UI 顯示進度但網路阻塞時整體變慢。Mitigation: 先 sequential（最簡實作），效能不足再改 concurrent + global cap；S14 引入 tus 後再共用 chunked upload 基礎建設。
- **30MB / meeting quota 是否合理** → 一份完整提案書 PDF 可能 8–15MB，5 檔上限剛好可上 3 份大型 PDF + 2 張截圖。若 S20c 上線後實測常碰天花板，再改 env var 化（v1 直接 hardcode 兩個常數）。
- **`kind` enum CHECK constraint vs pg enum type** → CHECK constraint 改值要 Alembic migration drop + recreate constraint，但成本低於 pg enum type；S20c 加新 `kind` 時用同樣模式。
- **附件命名衝突** → 同 meeting 兩個 `proposal.pdf`：磁碟 UUID 化避免衝突，但 UI 兩個同名 row 使用者要靠 `uploaded_at` 區分。Mitigation: UI 在重名時於 `original_name` 後面顯示 `(2)`、`(3)`（前端純展示處理，DB 不改）。

## Migration Plan

- **Alembic migration `XXXX_meeting_attachment.py`**: up — `CREATE TABLE meeting_attachment` + FK CASCADE + CHECK constraint + index on `(meeting_id, deleted_at)`（list endpoint 查詢用）；down — drop table。
- **Rollout**: 合主 branch 後跑既有 recording 與 dual-channel session 兩週確認 retention job 加 attachment 段落沒打破既有 recording cleanup。
- **Rollback**: 若 retention job 出問題，環境變數 `ATTACHMENT_RETENTION_ENABLED=false`（default true）短路 attachment 段落；緊急時 env off 即可，DB schema 不需 rollback。**註**：本 slice 預設不加這個 feature flag — 真出問題再加（避免提早 over-engineering）。

## Open Questions

- 是否要在 list endpoint 帶 `download_url` 預簽連結（避免前端組 URL）？v1 直接讓前端組 `${API_BASE}/api/meetings/{id}/attachments/{att_id}/download`，等 S20b / S20c 連動 Calendar API（真有 presigned 場景）時再做。
- 同一場 meeting 多次「上傳同一個檔」是否要 dedup？v1 不 dedup（兩個附件、兩條 row、UI 自然顯示 `(2)`）；若 S20c 餵 LLM 時重複內容是問題再加 hash 欄位 dedup。
