## Context

PRD slice 22 要求「每場 meeting 一鍵下載 ZIP bundle」，把該會議所有 artefact 帶離 app。痛點：

- **Recording window 跑掉就回不來**：WAV 30 天自動清，使用者必須在過期前主動匯出。
- **跨 schema 拼裝**：Playbook（playbooks table, 7 個結構化欄位 + free_form_markdown）、transcript（transcript_chunk N rows）、summary（summary table, 0 or 1 row）、recording（recording table，每個 stream 一個 WAV file_path）四份資料各住不同表，需要在 export 時 cohesively 組裝。
- **記憶體炸鍋風險**：dual-channel 30 分鐘會議的雙 WAV 約 50–100MB，串成 ZIP 不能 `f.read()` 整檔，必須走 chunked streaming，否則一個 GET 就把 FastAPI worker 撐爆。
- **30 天 retention 對 export 路徑必須一致**：`recording.deleted_at IS NOT NULL` 的 row 對應的 WAV 檔已不在磁碟（slice-11 cleanup 已 unlink），就算誤 reference 也只會 IOError；ZIP bundler 必須在 SQL 查詢階段就排除，才能保證 happy path 無 exception。

技術選型上，Python stdlib `zipfile.ZipFile` 接 `io.BufferedIOBase`，搭配 FastAPI `StreamingResponse(generator)` 已是業界 Python streaming ZIP 範式，無需引入 `aiozipstream` 或 `stream-zip` 等第三方套件。Bundler 的 deep module 規模剛好：對外 `MeetingExportBundler.iter_zip_chunks(meeting_id, user_id) -> AsyncIterator[bytes]` 一個方法收乾，內部組裝邏輯隱在實作層。

## Goals / Non-Goals

**Goals:**

- 使用者在 meeting detail 點「匯出」→ browser 在數秒內開始下載 `<title>__<YYYY-MM-DD>.zip`。
- ZIP 內含：`playbook.md`、`transcript.md`、（有則 `summary.md`）、`recordings/counterparty.wav`、`recordings/me.wav`（僅未過期、`deleted_at IS NULL` 者）。
- WAV 以 1 MiB chunk 寫入 ZIP；整個 endpoint 在 30 分鐘 dual-channel 會議上常駐記憶體 < 50 MiB。
- 過期 Recording（`deleted_at IS NOT NULL`）一律排除；其他 artefact（playbook / transcript / summary）即使對應 recording 已過期仍存在於 ZIP。
- 既有 Recording window 30 天 retention 規範對 export 路徑強制（spec recording-retention 新增 requirement）。
- 跨用戶不可越權：與 meeting list/get 一樣用 `X-User-Id` 比對 ownership，他人 meeting 回 404。
- 前端 i18n「匯出 / Export」雙 locale；ZIP filename 包含中文標題時走 RFC 5987 `filename*=UTF-8''` 編碼，相容主流瀏覽器。

**Non-Goals:**

- 批次匯出多場 meeting（v1 只支援 per-meeting）。
- ZIP 加密 / 簽章。
- Import / 回放（無 `POST /api/meetings/import`）。
- 自訂匯出選項（不選欄位、不選 recordings、不選 transcript 切片）；ZIP 結構固定。
- Cloud upload / share link。
- 修改 Recording window 30 天規範或新增「export 時延長 retention」機制。
- 動 free_form_markdown / 7 個結構化欄位的渲染樣式（沿用 slice-04）。

## Decisions

### Python stdlib zipfile + FastAPI StreamingResponse，不引第三方 streaming ZIP

走 `zipfile.ZipFile(SpooledTemporaryFile(max_size=4 MiB), mode='w', allowZip64=True)`：用 spool 暫存中央目錄（central directory）+ in-flight ZIP frame，待 stdlib 把 entry 寫進 spool 後，generator 從 spool tell/read/seek 推 chunk 出去，最後 `close()` 寫尾端中央目錄再 drain。**Alternative considered**：`aiozipstream` 第三方套件——被否決，它支援 async 但 stdlib + spool 足以滿足 50 MiB 記憶體上限，且少一個 dependency；ADR-0023 對「先用 stdlib、必要時才引第三方」立場一致。**Alternative considered**：純 generator + 自己手刻 ZIP local header / central directory bytes——被否決，ZIP spec 處理 CRC32 / ZIP64 / Unicode filename 太繁，stdlib 已正確處理。

### 串流推送策略：write_iter pattern with chunked WAV stdin

WAV 太大不能 `archive.write(path)`（一次 read 整檔到記憶體），改用 `with archive.open(name, 'w') as entry: for chunk in chunked_wav_reader(path, 1 MiB): entry.write(chunk)`。`chunked_wav_reader` 是 `def chunked_wav_reader(path: Path, chunk_bytes: int) -> Iterator[bytes]:` 用 `with path.open('rb') as f: while chunk := f.read(chunk_bytes): yield chunk`，搭配 stdlib `ZipFile.open(..., 'w')` API（Python 3.6+ 支援）。**Alternative considered**：直接 `archive.write(path, arcname)`——被否決，那是 stdlib helper 但內部一次性 read，無法滿足 streaming。**Alternative considered**：把 WAV 寫到 tmpfile 再 `archive.write`——被否決，多一次磁碟 round-trip，且沒有解決記憶體問題（stdlib 仍會整檔讀）。

### Recording 過期判斷下推到 SQL，不做 file-exists 二次驗證

bundler 內部 SQL select `... WHERE meeting_id = ? AND deleted_at IS NULL`，純資料層判定。**Alternative considered**：先 SELECT 全部 recording 再 `Path(rec.file_path).exists()` 判斷——被否決，會把「row 存在但檔案被外力刪掉」的不一致狀態帶進 export，導致 ZIP 行為不可預測；既有 slice-11 cleanup job 已保證 `deleted_at IS NULL ⇒ 檔案在磁碟上`（idempotent + 自我修復），bundler 信任此 invariant。若磁碟 race 真的發生（極罕見），讓 `open(file_path)` 拋 `FileNotFoundError`、endpoint 回 500（不靜默吞），這是可接受的失敗模式。

### Markdown 序列化規則

三份 markdown 各有獨立純函式（in `export/markdown.py`）：

- `playbook_to_markdown(playbook) -> str`：H1 = meeting title；接 free_form_markdown（若有）；接 6 個 H2 對應 6 個結構化 Playbook field（objective / counterparty profile / anticipated topics / anticipated objections / talking points / red lines）；空欄位輸出 `_（未填寫 / not filled）_`，雙語版本由 spec 內 ASCII 註記固定使用 `_(empty)_` 統一英文佔位避免 i18n 漂移。
- `transcript_to_markdown(chunks) -> str`：H1 = `# Transcript`；每個 chunk 一段，format `**[HH:MM:SS] {speaker_label}**: {text}`；speaker_label 轉換規則：`me` → `Me (我方)`、`counterparty` → `Counterparty (對方)`、`speaker_cluster_<N>` → `與會者 N`。
- `summary_to_markdown(summary) -> str`：H1 = `# Summary`；直接 dump `summary.markdown` 內容（slice-10 已是 markdown）。Summary 不存在時，bundler 跳過該檔案（不寫空檔）。

**Alternative considered**：把 playbook / transcript / summary 序列化邏輯掛在各自 module（playbooks/export.py、sessions/export.py、summarization/export.py）——被否決，export 是 cross-cutting concern，分散反而讓「ZIP 結構」失去單一 source of truth；集中在 `export/markdown.py` 一檔最清楚。

### ZIP filename 規則 + Content-Disposition

ZIP 檔名 = `{ascii_slug(title)}__{scheduled_at.date().isoformat()}.zip`。`ascii_slug` 規則：保留 `[A-Za-z0-9._-]`，其他字符替換為 `_`；連續 `_` 折疊；首尾 trim `_`；最大 80 字元（避免某些檔案系統路徑上限）。空 title 退回 `meeting`。

Content-Disposition 走 RFC 5987 雙值：`attachment; filename="<ascii_slug>__<date>.zip"; filename*=UTF-8''<percent_encoded(title)>__<date>.zip`，主流瀏覽器（Chrome、Safari、Firefox）優先讀 `filename*` 顯示完整 unicode 中文。**Alternative considered**：只給 unicode filename——被否決，舊瀏覽器或 curl 看到亂碼。

### 跨用戶授權與既有 Meeting ownership 一致

`GET /api/meetings/{id}/export` reuse `meetings/router.py` 已驗證的 ownership 模式：`MeetingRepository.get_for_user(meeting_id, user_id)` 回 None 時直接回 404，與既有 read / delete 端點一致，避免 export 路徑變成 ownership leak。**Alternative considered**：在 bundler 內部驗 user_id——被否決，bundler 應該專心做 ZIP 組裝，授權判定留在 router 層更清楚。

### 1 MiB chunk 寫死成常數，不暴露成 env var

`EXPORT_WAV_CHUNK_BYTES = 1 << 20` 直接寫在 `export/bundler.py`。**Alternative considered**：暴露成 `EXPORT_WAV_CHUNK_BYTES` env var——被否決，這個值有「太小拖慢、太大吃記憶體」的甜蜜點，但對使用者沒實際意義；保留為內部常數，未來真的需要調整再 promote 成 settings 欄位。

## Implementation Contract

**Observable behavior**

- `GET /api/meetings/{id}/export`（with `X-User-Id` header）對 own meeting 回 HTTP 200 + `Content-Type: application/zip` + RFC 5987 Content-Disposition；body 為串流 ZIP bytes。
- ZIP 一定包含 `playbook.md`、`transcript.md`，必要時包含 `summary.md`；對每個 `deleted_at IS NULL` 的 Recording row 各包一個 `recordings/{stream}.wav`（stream 值來自 `Recording.stream`：`counterparty` / `me`）。
- 過期 Recording（`deleted_at IS NOT NULL`）不出現在 ZIP，但 playbook / transcript / summary 三份 markdown 仍在。
- 越權匯出（meeting 屬於別人）回 HTTP 404 + `error_code: meeting.not_found`（沿用 meeting-management spec）。
- 前端 meeting detail 「匯出」按鈕點下後，呼叫 `fetch('/api/meetings/{id}/export')` 取 blob、用 `URL.createObjectURL` + 隱藏 `<a download>` 觸發 browser download；按鈕在 fetch 期間 disabled + 顯示 spinner，完成後恢復。

**Interface / data shape**

- `MeetingExportBundler.iter_zip_chunks(meeting_id: str, user_id: str) -> AsyncIterator[bytes]`：一個 async generator，每次 yield 一段 ZIP frame bytes。Meeting 不存在或不屬於該 user 時 raise `MeetingNotFound`（router 攔到後回 404）。
- `playbook_to_markdown(playbook: Playbook) -> str`、`transcript_to_markdown(chunks: list[TranscriptChunk]) -> str`、`summary_to_markdown(summary: Summary) -> str`：純函式，無 I/O，無 side effect。
- `chunked_wav_reader(path: Path, chunk_bytes: int) -> Iterator[bytes]`：sync generator；可被 async generator 透過 `asyncio.to_thread` 或直接同步 read 取出（WAV 是 local FS，stat / read 不阻塞 event loop 明顯）。
- 前端 `exportMeeting(meetingId: string, expectedFilename: string): Promise<void>`（住 `packages/web/src/lib/export-api.ts`）：包裝 fetch + blob handling + 觸發下載；失敗時 throw `MeetingApiError`（沿用 meetings-api 既有錯誤型別）讓 component 顯示 toast。

**Failure modes**

- Meeting 不存在 / 不屬於 user → 404 `{"error_code": "meeting.not_found", "message": "..."}`（沿用既有 meeting-management 行為）。
- Recording row `deleted_at IS NULL` 但 WAV 檔意外消失（race 或外力刪除）→ bundler open 時 raise `FileNotFoundError`，未捕獲 → 500 `{"error_code": "common.internal_error"}`（沿用 server.py 既有 handler）。這是可接受的「不應該發生」失敗，slice-11 cleanup 已保證此 invariant。
- 寫 ZIP 過程中 WAV 讀到一半 client 斷線 → FastAPI 自動 cancel async generator；spool tmpfile 由 `with` block 自動清；無 file handle leak。

**Acceptance criteria**

- `tests/export/test_bundler.py`：
  - `test_bundler_includes_playbook_transcript_summary_when_summary_exists`：完整 happy path，校驗 ZIP namelist 含 4 + N WAV 條目，4 種 markdown 內容字面比對 fixture。
  - `test_bundler_skips_summary_when_no_summary_row`：summary 缺席時 ZIP namelist 不含 `summary.md`，其他完整。
  - `test_bundler_excludes_recording_when_deleted_at_set`：兩個 Recording row，一個 `deleted_at IS NULL` 一個 NOT NULL，ZIP 只含未過期那一個 WAV；playbook / transcript / summary 不受影響。
  - `test_bundler_streams_wav_without_loading_full_file`：建一個 200 MB 假 WAV，跑 bundler，用 `tracemalloc` 或 `resource.getrusage` 驗 peak RSS 增量 < 20 MiB；不可整檔載入。
  - `test_bundler_raises_meeting_not_found_for_cross_user`：user A 跑 export 對 user B 的 meeting → raise `MeetingNotFound`。
- `tests/export/test_markdown.py`：
  - `test_playbook_markdown_emits_six_field_h2`：6 個 H2、empty 欄位 placeholder、free_form_markdown 排序正確。
  - `test_transcript_markdown_speaker_label_mapping`：me / counterparty / speaker_cluster_3 三種 speaker 對應 `Me (我方)` / `Counterparty (對方)` / `與會者 3`。
  - `test_summary_markdown_passes_through`：summary.markdown 內容原樣輸出 + `# Summary` H1。
- `tests/export/test_router.py`：
  - `test_export_endpoint_returns_zip_with_correct_disposition`：HTTP 200 + Content-Type + RFC 5987 雙值 filename。
  - `test_export_endpoint_returns_404_for_other_users_meeting`：跨用戶 → 404 `meeting.not_found`。
- `packages/web/src/components/export-meeting-button.test.tsx`：
  - `renders 匯出 / Export based on locale`、`disables and shows spinner during fetch`、`triggers <a download> click on success`、`shows localized error toast on 4xx`.
- `packages/web/src/locales/locales.test.ts` deep-equal pass（兩 locale 對齊）。

**Scope boundaries**

- **In scope**：`packages/backend/meeting_playbook/export/` 模組（bundler、markdown、router）；server.py include_router 一行；前端 `export-meeting-button` 元件 + `export-api.ts` helper；meeting detail 加按鈕；雙 locale 字串；`tests/export/` 三檔；spec `meeting-export` 新增 + spec `recording-retention` 加新 requirement。
- **Out of scope**：批次匯出；ZIP 加密 / 簽章；import；自訂選項；cloud upload；修改 30 天 retention；Playbook / transcript / summary 內部 markdown 渲染樣式調整。

## Risks / Trade-offs

- **WAV chunked write 對 stdlib ZipFile.open(name, 'w') 的限制**：Python 3.6+ ZIP 支援，但若標準庫 implementation detail 改變（罕見），需要降回 spool tmpfile workaround → 寫一個 integration test 跑真實 fixture，CI 上 Python 3.12 持續驗證。
- **Spool tmpfile 在容器化部署可能洩漏到 /tmp 滿盤**：當前是 macOS local dev + 單用戶，不會發生；future deploy 上 cloud 才需要考慮 → 加 `SpooledTemporaryFile(max_size=4 MiB)` 把絕大多數小 ZIP 留在記憶體；只有大 WAV bundle 才 spill 到 disk，且 generator yield 完即刪。
- **中文 filename 與 RFC 5987 的瀏覽器相容性**：Chrome / Safari / Firefox 已支援 `filename*=UTF-8''`，Edge 舊版 (<= 18) 不支援 → 我們 dev 環境只用 Chrome，影響範圍可忽略；spec 內仍標 ASCII fallback 確保最低限度可用。
- **`recording.deleted_at IS NULL` invariant 破裂的可能**：slice-11 cleanup 是 best-effort，極端情境（cleanup 半途 process kill）可能讓 deleted_at 寫了但 WAV 還在，反之亦然 → 信任既有 idempotent 設計；bundler 走 `Path.open('rb')` 對「row 存在但檔案不在」會拋 `FileNotFoundError`，由 FastAPI exception handler 統一回 500，可被使用者重試（下次 cleanup sweep 後 row 會被 mark 為 deleted_at NOT NULL，後續 export 自動排除）。
- **記憶體 peak 測試的 flakiness**：`tracemalloc.get_traced_memory()` 對小量 allocation 敏感，CI Python warmup 可能造成 noise → 設定寬鬆 budget（< 20 MiB 增量對 200 MB WAV 已是巨大餘裕）並在 fixture 內手動跑 `gc.collect()` 隔離。

## Migration Plan

- 無 Alembic migration（不動 schema）。
- 無新 env var；`EXPORT_WAV_CHUNK_BYTES = 1 << 20` 是 module 級常數。
- Rollout：合主 branch 後直接生效；既有 meeting list / detail / session 路徑 0 影響（新 endpoint + 新前端按鈕）。
- Rollback：把 `export_router` 從 `server.py` `include_router` 拿掉、前端按鈕 commenting out 即可；無 schema 殘留。

## Open Questions

- 是否要在 ZIP 內額外加 `metadata.json`（包含 meeting id / status / created_at / scheduled_at）方便未來 import？v1 不加，等 import slice 需要時再 propose 補（避免本 slice 過寬）。
- 中文 ZIP 內部檔名 `recordings/counterparty.wav` 是否需要 i18n？目前固定 ASCII，因 ZIP 內部結構 cross-tool 必須穩定（解壓工具相容性比顯示更重要）；spec 內明確記載 ASCII filename 為契約。
