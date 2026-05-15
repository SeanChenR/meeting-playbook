## Context

S12 完成了 single-channel diarization + finalize 路徑（`speaker-attribution-strategy` capability），但 production runtime 入口只有 dual-channel live capture。S14 補上**第一個** single-channel 入口：使用者手上預錄的音檔（手機錄音、Zoom 匯出、Voice Memo），透過上傳 → 轉碼 → ASR → finalize 全 pipeline 變成 transcript。

現有 `rerun/runtime.py`（slice-11 task 5.1）已實作完備的「background ASR task + in-flight registry + chunk progress」pattern — S14 重用該抽象避免重新發明。

依賴 / 限制：
- `meeting.status` enum 不擴增，sticking to `scheduled / in_progress / completed`（per issue #25）— 用 `Recording.source` 區分顯示
- 加 `Recording.started_at` 一同處理（slice-16 chunk inline edit 也需要）
- BlackHole 仍是 live capture 前提；live 路徑的 single-channel UI 入口 gap 不在本 slice scope

## Goals / Non-Goals

**Goals:**

- 對 `scheduled_end_at` 已過、無 recording 的 meeting，使用者可上傳一個音檔到後端，後端跑 ASR + finalize 後產出 `transcript_chunk` 列
- Resumable upload — 同 browser session 內網路斷可從中斷處續傳
- ffmpeg 轉碼支援 wav / mp3 / m4a / aac / flac / ogg → 16kHz mono 16-bit PCM WAV
- 上傳對話框讓使用者指定「實際開始時間」（預設 `scheduled_start_at`），寫進新 `Recording.started_at`
- ASR 走背景任務 + polling progress（端到端可支援 3 小時音檔不爆 timeout）
- 接通 S12 `SingleChannelStrategy` 在 production runtime 第一次跑

**Non-Goals:**

- 不支援多檔合併、多軌音檔分軌 — 單檔 → 單 recording row
- 不支援跨 device / 跨 browser session resume — 不存 tus session token cross-session（per discuss decision，個人單機）
- 不觸發 playbook 重生 — playbook 沿用 pre-meeting 既存產物
- 不動 live capture 路徑或 `meeting.status` enum
- 不對既有 dual-channel 流程做任何 regression-risk 改動

## Decisions

### Decision 1: Background task 重用 `rerun/runtime.py` 模式

新增 `offline_ingest/runtime.py` 鏡像 `rerun/runtime.py` 的 in-flight registry + `ChunksProgress` + `spawn_*_task` 結構，**不抽共用 base class**（兩者差異足夠：rerun 既有 recording、重算 transcript；offline 從零建 recording → 轉碼 → 跑 ASR）。共用 module 在後續 slice 出現 4+ instance 才考慮。

### Decision 2: Tus 1.0 protocol — 後端自寫 200 行 protocol handler

實作 4 個 HTTP methods 構成 tus 1.0 core：
- `OPTIONS /api/meetings/{id}/recordings/offline_upload` — 回 `Tus-Resumable: 1.0.0` + `Tus-Version` + `Tus-Max-Size` + `Tus-Extension: creation,termination`
- `POST /api/meetings/{id}/recordings/offline_upload` — creation，body 空，header 帶 `Upload-Length` + `Upload-Metadata`（含 `filename`, `mimetype`, `actual_started_at`），回 201 + `Location: /api/meetings/{id}/recordings/offline_upload/{upload_id}`
- `HEAD /api/meetings/{id}/recordings/offline_upload/{upload_id}` — 查詢 `Upload-Offset`
- `PATCH /api/meetings/{id}/recordings/offline_upload/{upload_id}` — append chunk，body 是 bytes，header `Upload-Offset` + `Content-Type: application/offset+octet-stream`

不引 `tuspyserver` 第三方依賴，因為自寫 200 行 FastAPI handler 涵蓋我們需要的全部功能，且能直接走既有 `X-User-Id` gateway 鑑權；引入第三方反而要處理 middleware 不相容。

前端：引入 `tus-js-client@4.x`（~80KB gzip），是官方 reference 實作。

### Decision 3: 轉碼 — ffmpeg subprocess via `asyncio.create_subprocess_exec`

不引 in-process audio decode lib（pyav / librosa）。轉碼指令：

```
ffmpeg -i {input} -ac 1 -ar 16000 -sample_fmt s16 -f wav {output}
```

涵蓋 6 種輸入格式。失敗（returncode != 0）→ raise `OfflineIngestTranscodeError`，pipeline 把上傳 staging file unlink + 設 ASR task 為 failed 狀態。

不用 `subprocess.run` 是因為 ffmpeg 可能跑數十秒（3hr 音檔轉碼），要 yield event loop。

### Decision 4: Recording schema — `source` + `started_at` 雙欄位 migration

Alembic `0011_recording_source_and_started_at.py`：

```python
def upgrade():
    op.add_column("recording", sa.Column("source", sa.Text(), nullable=False, server_default="live"))
    op.create_check_constraint("recording_source_check", "recording", "source IN ('live','offline')")
    op.add_column("recording", sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True))

def downgrade():
    op.drop_constraint("recording_source_check", "recording")
    op.drop_column("recording", "source")
    op.drop_column("recording", "started_at")
```

`source` server_default 確保既有 row backfill 為 `'live'`；`started_at` nullable 因為 live capture 還沒寫這欄（下個 slice 補）。Offline upload 寫入時兩欄都填。Stream 欄位**不變動** — offline upload 一律 `stream = "me"`，select_strategy 看到 1 筆 recording 自動走 single-channel。

### Decision 5: 上限驗證 — 兩層 + 第三層

- **Frontend pre-check**：file picker `accept` 限副檔名；`onchange` 看 `file.size` 拒絕 > 500MB 不送 POST，避免無謂的 tus 創建
- **Backend creation check**：POST 收到 `Upload-Length > OFFLINE_UPLOAD_MAX_BYTES` 拒絕 413
- **Backend post-transcode check**：ffprobe 確認 duration ≤ `OFFLINE_UPLOAD_MAX_DURATION_SECONDS`；超出 → unlink staging WAV + raise `OfflineIngestTooLong`

三層因為 file size 跟 duration 是兩件事（高 bitrate flac 可能 600MB 但只 1hr，低 bitrate ogg 可能 200MB 但 4hr）。

### Decision 6: 上傳 UI — meeting detail 上方 conditional banner

`packages/web/src/routes/meetings/detail.tsx` 在 header 下方插入 `<OfflineIngestBanner>`，顯示條件：

```
meeting.status === "scheduled"
  && new Date() > new Date(meeting.scheduled_end_at)
  && meeting.recordings.length === 0
```

Banner 元素：
- Icon + 標題（"這場會議已結束 — 上傳音檔取得逐字稿"）
- 「上傳音檔」按鈕 → 開 `<OfflineIngestUploadDialog>`
- Dialog 內含 dropzone（drag-drop 或 file picker）+ 「實際開始時間」`<DateTimePicker>` (default = `scheduled_start_at`) + 「開始上傳」按鈕

上傳期間 dialog 內：tus-js-client progress callback → progress bar + 估算剩餘秒數。上傳完成 → 切換到「ASR 進行中」狀態，每 3s `GET /api/meetings/{id}/offline_ingest_progress` 拉 `(chunks_processed, chunks_total)`，完成 → close dialog + invalidate meeting query + 顯示 toast。

### Decision 7: 錯誤碼 + i18n key 表

| Error code | HTTP | 觸發 |
| --- | --- | --- |
| `offline_ingest.unsupported_format` | 422 | mimetype / 副檔名不在白名單 |
| `offline_ingest.too_large` | 413 | `Upload-Length` 超 `OFFLINE_UPLOAD_MAX_BYTES` |
| `offline_ingest.too_long` | 422 | 轉碼後 ffprobe 偵測 duration > `OFFLINE_UPLOAD_MAX_DURATION_SECONDS` |
| `offline_ingest.invalid_started_at` | 422 | `actual_started_at` 不是有效 ISO 8601 或晚於 now |
| `offline_ingest.transcode_failed` | 500 | ffmpeg returncode != 0 |
| `offline_ingest.busy` | 409 | 該 meeting 已有 ASR task in-flight |
| `offline_ingest.conditions_not_met` | 409 | 開 dialog 後狀態變了（now < scheduled_end_at 或 recording 已存在） |

i18n key prefix `errors.offline_ingest.*` 與 `offline_ingest.banner.*` / `offline_ingest.dialog.*`；雙 locale 鏡像（per CLAUDE.md i18n convention）。

## Implementation Contract

**Behavior**

- 對符合 banner 顯示條件的 meeting，使用者按「上傳音檔」→ 選檔 + 填實際開始時間 → 上傳開始
- 大檔走 tus chunked PATCH，網路斷後同 dialog 重新點上傳會從 `Upload-Offset` 中斷處繼續（test scenario: 60MB 檔上傳到 30% disconnect，重新打開 dialog 重連同一 `upload_id` 從 30% 繼續到完成）
- 上傳完 → 後端轉碼 → ASR background task 跑 → transcript_chunk 寫入 → meeting status 變 `completed`
- 結束後 banner 消失，detail page 顯示 transcript chunks，speaker 值為 `speaker_cluster_*`（per S12 single-channel）

**Interface / data shape**

- DB `recording` row（offline）：
  - `source = "offline"`
  - `stream = "me"`
  - `started_at = <use's actual_started_at>` (ISO 8601)
  - `file_path = <OFFLINE_UPLOAD_DIR>/{meeting_id}/source.wav`（轉碼後）
- DB `transcript_chunk` row：speaker 依 SingleChannelStrategy 寫 `speaker_cluster_*`，asr_provider_used 沿用 meeting.asr_provider
- HTTP envelope: 成功 200 / 201 / 202 / 204；錯誤 走 `{error_code, message}` per project convention（meeting-management spec 內定義）
- Tus headers per spec 1.0.0：`Tus-Resumable`, `Upload-Length`, `Upload-Offset`, `Upload-Metadata` (base64-encoded key-value pairs)
- Progress endpoint `GET /api/meetings/{id}/offline_ingest_progress` 回 `{state: "uploading"|"transcoding"|"asr_running"|"completed"|"failed", chunks_processed?, chunks_total?, error_code?}`

**Failure modes**

- Tus PATCH 失敗 / chunk 損壞 → 對應 HTTP 4xx；前端 `tus-js-client` 自動重試 3 次後 surface 給 user
- 轉碼失敗 → `offline_ingest.transcode_failed`，staging file 清掉，meeting 維持 `scheduled` 狀態（不轉 in_progress）
- ASR 失敗 → 走既有 rerun runtime 失敗路徑（log + 不寫 chunks），progress endpoint 回 `state="failed"`，但 recording row 留住（未來可手動 rerun）
- 多 user 開兩個 tab 同時上傳同 meeting → 第二個收到 `offline_ingest.busy`
- 上限觸發各種錯誤碼 per Decision 7 表

**Acceptance criteria**

- `pytest tests/offline_ingest/` 全綠（unit）
- `pytest tests/integration/test_offline_ingest_e2e.py` 全綠（end-to-end，含 tus chunked resume + real-audio fixture）
- `bun --filter @meeting-playbook/web test` 全綠（UploadBanner / UploadDialog / tus-uploader）
- 手動驗證：在 dev 環境上傳 `tests/speaker/fixtures/multi_speakers_zh.wav` 到一個 mock scheduled-end-at-過期 meeting，看到 banner → dialog → 上傳進度 → ASR 進度 → transcript 出現 ≥2 speaker_cluster 值
- 中斷重連驗證：60MB 檔上傳到 ~30% 關閉 dialog，重開後 PATCH `Upload-Offset` 證明 server 記得進度

**Scope boundaries**

In scope:
- `recording.source` + `recording.started_at` migration
- Tus 1.0 core (`creation`, `termination` extension)
- ffmpeg subprocess 轉碼
- ASR background task reuse rerun pattern
- Meeting detail conditional banner + dialog
- 雙 locale i18n + 錯誤碼

Out of scope:
- Tus `concatenation` / `checksum` extension（個人單機不需要）
- 多檔合併、分軌
- Playbook 重生
- Live capture single-channel UI entry（已紀錄為下個 slice）
- ASR 失敗後自動重試（手動 rerun 即可）

## Risks / Trade-offs

### Risk 1: 自寫 tus protocol handler 偏離規格

200 行 FastAPI 自寫 vs 引第三方 `tuspyserver`。

Mitigation：嚴格對照 [tus.io/protocols/resumable-upload.html](https://tus.io/protocols/resumable-upload.html) 1.0.0 spec，把 `OPTIONS`/`POST`/`HEAD`/`PATCH` 四個 verb 各寫一個 happy-path + 兩個 error case 的 unit test；接受度測試用真實 `tus-js-client` 對打。如果發現需要 `concatenation` 或 `checksum` 等 extension，再評估換 lib。

### Risk 2: ffmpeg 不在使用者 PATH

dev 機已驗（前面用 ffmpeg 轉了 fixture），但若部署環境 ffmpeg 缺失會在第一次 transcode 才爆。

Mitigation：app 啟動時 `shutil.which("ffmpeg")` 檢查，缺失 → `logger.warning("ffmpeg_missing")`。upload pipeline 在轉碼前再檢查一次，缺失 → raise `OfflineIngestTranscodeError`，error_code 附「ffmpeg 未安裝」訊息給使用者明示。

### Risk 3: tus staging file 累積佔磁碟

中斷 / 取消的 upload session 留下 partial file 沒清。

Mitigation：daily cleanup job（既有 retention 模組已有 cron pattern）— 24 小時前的 `OFFLINE_UPLOAD_DIR/*.partial` unlink；完成上傳 OR 主動 DELETE 走 tus `termination` extension 即時清。

### Trade-off: Background task in-process vs queue

選 in-process（沿用 rerun pattern），不引 Celery / RQ。

理由：個人單機 + 並發 ≤ 2 task；queue 過度設計。代價：backend 重啟會中斷 in-flight task，progress endpoint 回 `state="failed"`，使用者需手動重新上傳。可接受。
