## Context

S20a 落了「會議掛附件」的能力，S20b 為了 calendar preview 在 `POST /api/meetings`
接了 `attachments[]` —— 但 S20a 沒做出 orphan attachment（`meeting_id` 在 schema
是 NOT NULL），所以 S20b 的 attach 路徑沒有任何 candidate row 可以引用、
`/meetings/new` 的 picker 永遠空。S24 把這個 gap 接通：使用者在 `/meetings/new`
拖檔 → 後端存暫存 → 建會議時 atomically 把暫存檔 move 進 meeting dir。

當下 schema（post-S20a）：
- `meeting_attachment(id PK, meeting_id NOT NULL FK CASCADE, file_path,
  kind, original_name, bytes, uploaded_at, deleted_at)`
- Per-meeting quota：5 files / 30 MiB
- Per-meeting whitelist：image (jpeg|png|webp) / pdf / docx / text / markdown
- 既有 retention job（30-day）sweep `deleted_at` 過期或 `uploaded_at` 過期
  的 row

Single-user app（per CONTEXT.md），但 staging 仍然需要 user_id scoping —
否則 row 的「歸誰」資訊從 `meeting.user_id` 來，meeting_id 是 NULL 時就斷
鏈。

## Goals / Non-Goals

**Goals**
- 使用者可以在「沒先建會議」的前提下上傳附件、之後 attach 到新會議
- Attach 是 atomic：staging dir 的檔案搬進 meeting dir、row 的 `meeting_id`
  set；任一步失敗都不留半成品
- Staging 過期自動清掉（24h 沒用就 sweep），不讓使用者的 home 目錄無限長大
- 既有 meeting-scoped upload / download / delete 行為**完全不變**
- 既有 S20c multimodal generator 不變（attach 後才會被讀進來，跟現在一致）

**Non-Goals**
- tus / chunked upload
- 跨 meeting 共用附件
- staged 編輯 / rename
- staged 下載
- 改 per-meeting quota
- 改既有 retention 30-day window

## Decisions

### D1. Staging 不開新表，沿用 `meeting_attachment` 表 + nullable meeting_id

選擇：把 `meeting_attachment.meeting_id` 改 NULLABLE，NULL = staged。不另
開 `attachment_staging` 表。

**理由**
- 同一個 lifecycle、同一份 validation（whitelist、size、MIME）、同一個
  retention job sweep 邏輯都能複用
- S20b 已經假設「staged attachment 是 row 在 meeting_attachment 表裡、
  meeting_id IS NULL」—— attach endpoint 邏輯已 set `meeting_id`，跟這個
  model 完全 match
- 跨表 JOIN 變單表 query，列「user 的 staged 跟已 attach」一次撈

**Trade-off**：未來若 staging 邏輯複雜化（例如多階段 staging、版本控制），
單表會擠。當下 scope 看不到那個需求。

### D2. 加 `user_id` column 上 `meeting_attachment`，而非僅靠 meeting.user_id

選擇：`meeting_attachment` 新增 `user_id TEXT NOT NULL` FK to `user.id`。

**理由**
- `meeting_id IS NULL` 時無法走 `JOIN meeting ON ... WHERE user_id = ?`
  做 ownership scoping
- 直接帶 `user_id` 讓 staging 的 list / delete query 簡單（單表 WHERE）
- Backfill 安全：existing rows 有 `meeting_id` → migration 透過 JOIN 寫
  進 `user_id`，再 SET NOT NULL

**Trade-off**：兩處持有 user_id（attachment 跟 meeting）有冗餘風險 —— 
attach 流程要 verify `attachment.user_id == meeting.user_id`，否則可能
跨 user attach。

### D3. Staging 檔案路徑：`ATTACHMENT_DIR/_staging/{user_id}/{att_id}{ext}`

選擇：staging 跟 attached 分目錄。`_staging` 開頭表示「不是 meeting id」。

**理由**
- 視覺上一眼分得出來
- 清理 staging 不會誤觸 attached（path-level 隔離）
- Per-user 子資料夾避免單一目錄超過幾千個檔（filesystem 效率）

**Alternative considered**：把 staged 跟 attached 都丟 `ATTACHMENT_DIR/_pool/`，
用 row 的 file_path 維持唯一性 —— 但 meeting-scoped retention sweep 變難。
否決。

### D4. Attach 用 `os.rename` 首選、`shutil.move` fallback

選擇：attach 流程的「搬檔」優先用 `os.rename`（同 fs atomic），抓到
`OSError [Errno 18] EXDEV`（跨 fs）fallback 到 `shutil.move`。

**理由**
- Atomicity：`os.rename` 是 POSIX atomic，要嘛搬成功要嘛沒事
- 同 fs 是常態（attachment 都在 `ATTACHMENT_DIR` 底下），fast path 拿到
- 跨 fs 情境（不太可能但可能）至少有 fallback

### D5. Attach 失敗的 rollback：move 回 staging

選擇：`POST /api/meetings` 在「建立 meeting row → attach 附件 → 跑 Playbook
生成」這串失敗時（例如 generator timeout），已 attach 的附件**檔案 move 回
staging**、row 的 `meeting_id` 重設回 NULL。

**理由**
- 使用者預期是「整個流程 atomic」—— 半成功會讓他困惑
- 使用者預期是「我的附件沒丟」—— 真實情境下他剛拖完幾個檔，不該因為
  Playbook timeout 就要重傳

**Trade-off**：rollback 邏輯有 bug 的話可能 leak 檔案。新增測試覆蓋。

### D6. Per-user staging quota：10 files / 60 MiB

選擇：每個 user 同時可有 10 files / 60 MiB staged。**D12（後續決策）把
per-meeting quota 也對齊到 10 / 60，所以 staging 跟 per-meeting 是同一組數字、
維度不交叉**（staging = 「user 此刻的暫存區大小」、per-meeting = 「單場
meeting 累計附件量」）。
超過則 422 `attachment.staging_quota_exceeded`。

**理由**
- 使用者可能同時準備多場會議的素材（calendar 預覽好幾場一次處理）
- 60 MiB / 10 files 對 reference 文件（PDF、screenshot）是寬鬆的上限
- single-user app，沒有 multi-tenant 公平性顧慮

**Alternative considered**：staging 無上限，靠 24h cleanup 控量 —— 否決，
惡意操作或 bug 可能在 24h 內塞滿 disk。

### D7. Staging 過期 cleanup：沿用既有 retention job，TTL 24h

選擇：`RecordingRetentionJob.cleanup` 已經跑每 24h，sweep
`meeting_id IS NULL AND uploaded_at < now() - 24h` 的 row（unlink 檔 + 刪
row）。新 env `STAGED_ATTACHMENT_TTL_HOURS` default 24。

**理由**
- 不另開 job，operational simplicity
- 24h 對「我今晚弄好明早建會議」場景足夠寬鬆
- env 可調，使用者要短一點 (12h) / 長一點 (72h) 都能

### D8. Frontend：新 `<StagedAttachmentDropzone>` 元件，不重用 meeting-detail 的

選擇：`/meetings/new` 用新 component；既有 `<AttachmentDropzone>`（meeting-
detail）不動。

**理由**
- API 不同：staging 走 `/api/attachments/staging`，meeting-scoped 走
  `/api/meetings/{id}/attachments`
- mutation 後的 cache invalidation 不同（staging invalidate 'attachments
  pending'、meeting-scoped invalidate `['meeting-attachments', meetingId]`）
- 加 prop 切兩種模式會讓元件分支複雜化、單一責任更清楚

**Trade-off**：兩個元件 95% 視覺相似，未來要改樣式要動兩處。可以抽共用
presentational sub-component（後續優化）。

### D9. `/meetings/new` submit：所有 staged 都 attach，不選 → 移除

選擇：表單沒「checkbox 挑 attach 哪些」UI；submit 時把當前 dropzone 列表
的所有 staged ids 全部送進 `attachments[]`。要排除某個就在 dropzone 上點
「移除」（會 DELETE staging row）。

**理由**
- 已 staged = user 已表達意圖
- 少一層 mental overhead
- 跟「拖檔就是要附加」的直覺一致

### D10. Dropzone batch upload 採前端 truncation + sequential POST

選擇：拖入 / 多選的 N 個 file 由前端先做 quota truncation。
**演算法是 skip-and-continue（accept-what-fits）：iterate files in drop order，
逐個試算「加上去後 count 是否 > 10、bytes 是否 > 60 MiB」；不合就跳過該檔、
繼續看下一個；合就收進 accepted 並累加 running count / bytes**。
任何被 skip 的檔都計入 `dropped` 計數，最後 `dropped > 0` 就 inline 顯示
「拖入 N 個檔，配額只上傳前 K 個」warning（N = files.length, K = accepted.length）。
送出去的 K 個檔走 sequential `POST /api/attachments/staging`
（一個跑完才下一個），共用同一個 upload-progress UI。

**例子**：已 staged 1 個 58 MiB 檔，拖入 `[3 MiB, 1 MiB]`（drop-action total = 2）：
- iter 0：3 MiB → `58 + 3 = 61 > 60` → skip
- iter 1：1 MiB → `58 + 1 = 59 ≤ 60` 且 count 2 ≤ 10 → accept
- 結果：accepted = `[1 MiB 那個]`（K = 1）；warning 顯示「拖入 2 個檔，配額只上傳前 1 個」
  （`dropped` i18n param = drop-action total = 2、`accepted` = 1）

**理由**
- 跟既有 per-file backend route 完全相容，**無需新 endpoint 或 backend 改動**
- Truncation 給使用者清晰 feedback —— 比讓 backend 接收 11 個然後第 11 個
  422 失敗（前 10 個還是會佔配額）更好
- Sequential 比 parallel 易讀 progress（單一進度條照舊），且避免 server
  同時收 10 個 multipart request 的 IO 壓力
- Truncation 是**前端優化**，不取代 backend per-file enforcement —
  backend `validate_staging_upload` 仍會在每個 POST 檢查 quota（雙保險、
  跟 D6 一致）

**Alternative considered**：parallel `Promise.allSettled` — 否決，
progress bar UI 需要重設計成 per-file rows，scope 大；批次 3-5 個檔
sequential 用時 ≈ 2-5s，可接受。

### D11. Quota counter 直接從 staged list 計算、達上限即 disable dropzone

選擇：dropzone 內嵌 `<used>/10 個 · <bytesUsed>/60 MiB` counter，從
`rows` 直接 derive（count + reduce bytes）。`used === 10` 或
`bytesUsed >= 60 * 1024 * 1024` 時，dropzone 的 drop-area + file-input button
都標 `disabled` + 顯示「已達暫存區上限」hint。

**理由**
- 「為什麼上傳不了」變成「dropzone 一眼就看得到」，避開使用者拖檔之後
  才看到 quota 422 的 dead-end UX
- Counter 從 client cache 算（`useQuery(pendingAttachmentsQueryOptions)`），
  無新 API call
- Disabled state 不取代 backend 422 enforcement —— `addEventListener('drop')`
  即使被略過，backend 仍會擋

**Alternative considered**：counter 從 backend `GET /api/attachments/quota`
之類新 endpoint 拿 —— 否決，多一輪 round-trip 沒價值；client 已有 list
就夠算。

### D12. Per-meeting attachment quota 對齊 staging quota（10 個 / 60 MiB）

選擇：把既有 `MAX_ATTACHMENTS_PER_MEETING = 5` 提高到 `10`、
`MAX_BYTES_PER_MEETING = 30 MiB` 提高到 `60 MiB`，跟 D6 的 staging quota
完全對齊。原本 D6 的「staging = per-meeting × 2」rationale（user 同時準備
多場 meeting）改寫成「per-meeting = staging = 10 個 / 60 MiB，user 一次
上傳的經驗值上限」。

**理由**
- UX 一致性：在 `/meetings/new` 看到「10 / 10 個 · 60 / 60 MiB」counter、
  在 `/meetings/{id}` 卻 hit「最多 5 個」的 422 → 使用者沒理由背兩組數字
- 「在哪上傳跟結果上限該一樣」是直覺的 mental model；原本 2x 設計只服務
  「同時準備多場 meeting」這個 edge case，但 UI 沒呈現這個 design intent
- Disk 影響可控：60 MiB / meeting × 平常 meeting 數 ≪ 100 GB 級的 audio
  recording disk usage（recording 才是 disk 主消費者）

**Trade-off**：對「每場 meeting 只放少量 reference 文件」場景 over-provision，
但這不傷使用者 —— 只是上限沒被打到。原 D6「staging = per-meeting × 2」
intent 被 D12 取代後，staging quota 的 rationale 改為「per-user 一次性
作業空間」，跟 per-meeting 維度互不交叉。

## Risks / Trade-offs

- **Risk**：Attach 流程的 rollback 邏輯複雜，可能漏處理某個 exception
  - **Mitigation**：D5 加專屬 test，覆蓋 generator failure / meeting create
    db error / attachment move file fail 三種情境
- **Risk**：Staging 路徑可能被誤當 meeting_id 解析（`_staging` 是合法目錄名
    但不是 UUID prefix）
  - **Mitigation**：meeting_id 是 `m_` prefix UUID，`_staging` 不衝突；同
    時 router URL 用 `/api/attachments/staging` 不接 path param
- **Risk**：使用者退出 `/meetings/new` 沒提交，staged 檔案留在 disk 24h
  - **Trade-off**：D7 接受。24h cleanup + per-user quota 雙保險

## Migration Plan

1. Alembic upgrade：
   - ALTER `meeting_attachment.meeting_id` DROP NOT NULL
   - ADD COLUMN `user_id TEXT NOT NULL DEFAULT ''`（temp default 讓 ADD COLUMN
     不卡），紀錄 FK to user.id
   - UPDATE backfill：`UPDATE meeting_attachment ma SET user_id = m.user_id
     FROM meeting m WHERE ma.meeting_id = m.id`
   - ALTER `user_id` DROP DEFAULT
   - CREATE INDEX `meeting_attachment_user_meeting_uploaded_idx`
     ON `meeting_attachment (user_id, meeting_id, uploaded_at DESC)`

2. Backend deploy：新 staging endpoints 上線、`POST /api/meetings` 的
   attach 邏輯加 move 步驟。既有 per-meeting upload / list / delete /
   download 行為不變

3. Frontend deploy：`/meetings/new` 改用 `<StagedAttachmentDropzone>`。
   無 staged 時就空列表 + dropzone

Downgrade：alembic downgrade 把 user_id column drop、meeting_id 改回
NOT NULL（這步要 DELETE WHERE meeting_id IS NULL 先清掉 staged row、否則
SET NOT NULL 會炸）

## Open Questions

(none — design 階段都決定完)

## Implementation Contract

- Alembic 0019 head 後：`meeting_attachment.meeting_id` IS NULLABLE，
  `meeting_attachment.user_id` IS NOT NULL with FK 到 user.id
- `POST /api/attachments/staging` 接受 multipart `file` field，回 201 +
  `Attachment` shape。寫入 `ATTACHMENT_DIR/_staging/{user_id}/{att_id}{ext}`
  並建立 row `meeting_id=NULL, user_id=<current>`
- `GET /api/attachments?status=pending` 回 200 + `{"attachments":
  [Attachment, ...]}`，只列當前 user 的 `meeting_id IS NULL AND
  deleted_at IS NULL` rows
- `DELETE /api/attachments/{id}` 對 staged row（`meeting_id IS NULL`、
  owned by current user）unlink 檔 + 刪 row、回 204。對 attached row
  回 404 `attachment.not_found`（要走 meeting-scoped delete）
- `POST /api/meetings` 帶 `attachments[]` 時：每個 id 必須是 staged
  （`meeting_id IS NULL` + `user_id == current`）；不符合任一條件回 422
  `attachment.not_attachable`。Attach 步驟把檔案從
  `ATTACHMENT_DIR/_staging/{user_id}/{att_id}{ext}` move 到
  `ATTACHMENT_DIR/{meeting_id}/{att_id}{ext}`，row 的 `file_path` 更新、
  `meeting_id` 設成新 meeting id
- Meeting create + attach + Playbook generation 失敗時：已 move 的檔案
  move 回 staging、row 的 `meeting_id` reset 回 NULL、`file_path` 改回
  staging 路徑
- Staging quota：當前 user 的 `meeting_id IS NULL` row 總數 ≥ 10 或總
  bytes ≥ 60 MiB 時，新 staging 上傳回 422
  `attachment.staging_quota_exceeded`
- Retention job：每 24h 跑時，sweep `meeting_id IS NULL AND uploaded_at
  < now() - STAGED_ATTACHMENT_TTL_HOURS hours` 的 row（unlink + 刪 row）
- 新 env `STAGED_ATTACHMENT_TTL_HOURS` default `24`，寫進 `.env.example`
- Frontend `<StagedAttachmentDropzone>` 跟 `<AttachmentDropzone>` 共存；
  `/meetings/new` 只用 staging dropzone
- `attachments-api.ts` 新增 `uploadStagedAttachment`、
  `deleteStagedAttachment`，既有 `listPendingAttachments` 行為不變但現在
  接到真實 endpoint
- Dropzone 的 `<input type="file">` 標 `multiple`；drop / pick N 個 file
  時，若 `current_count + N > 10` 或 `current_bytes + Σnew_bytes > 60 * 1024 * 1024`，
  只送前 K 個（最多塞下的數量）、跳過其餘、inline 顯示 `staging.batch_truncated`
  warning（含 dropped N、accepted K 兩個變數）
- Dropzone 永遠 render 一個 counter `<used>/10 個 · <bytesUsed>/60 MiB`
  derived from `rows`；`used === 10` 或 `bytesUsed >= 60 * 1024 * 1024`
  時 drop-area + upload button `disabled` + render `staging.at_limit` hint
- Sequential upload：批次內每個 POST 都是 `await uploadStagedAttachment(file)`
  跑完才下一個；單一 progress bar 顯示「當前檔 X / 總共 N · {percent}%」

## Scope Boundaries

**In scope**
- Backend `meeting_playbook.attachments` 模組（models / repository /
  validation / router / staging_router 新檔）
- Backend Alembic 0019 migration
- Backend `meetings/router.py` 的 `POST /api/meetings` attach 步驟擴
- Backend retention job 的 staged sweep
- Backend `config.py` 新 env
- Frontend `<StagedAttachmentDropzone>` 新 component + tests
- Frontend `meetings/new.tsx` 換 picker → dropzone
- Frontend `attachments-api.ts` 新 mutation
- i18n keys for staging dropzone UI
- CONTEXT.md glossary 加「Staged attachment (暫存附件)」

**Out of scope**
- 既有 meeting-detail `<AttachmentDropzone>`
- S20c multimodal pipeline（generator 邏輯不動，attach 後才會被讀）
- S20b calendar preview 預填邏輯（calendar 帶來的附件還是走同一個
  staging dropzone）
- Playbook / Summary / Tactical advisor 任何邏輯
- Multi-user / permission 模型
- tus / chunked upload
