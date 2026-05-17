> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/23
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16

## Why

目前 meeting 內容（Playbook、transcript、summary、recordings）散落在 DB row 與本機 WAV 檔，使用者無法一次把一場會議的 artefact 全帶走（備份、外部分享、跨機歸檔皆無路徑）。Recording 又受 30 天 Recording window 自動清掉，使用者必須在過期前主動匯出才能保留語音 evidence；transcript / playbook / summary 即使對應 recording 已過期仍應可匯出。本 slice 補上「每場 meeting 一鍵下載 ZIP bundle」的能力，並嚴格遵守 Recording window：deleted_at 已標記的 Recording 一律不進 ZIP。

## What Changes

- 新增 deep module `MeetingExportBundler`：把單一 meeting 的 Playbook / transcript / summary 轉成 markdown，並把 `deleted_at IS NULL` 的 Recording WAV 依檔名規則寫入 ZIP。
- 新 endpoint `GET /api/meetings/{meeting_id}/export`：以串流方式回 `application/zip`，使用 `zipfile.ZipFile(stream, mode='w', allowZip64=True)` 寫入 `StreamingResponse`，過程中 WAV 以 chunked read 寫入（不 `f.read()` 整檔），確保 30 分鐘以上的 dual-channel 會議不撐爆 Python heap。
- ZIP 內容固定為：`playbook.md`、`transcript.md`、（若 summary 存在）`summary.md`、`recordings/counterparty.wav`、`recordings/me.wav`（僅未過期者）。
- Response 帶 `Content-Disposition: attachment; filename="<title>__<YYYY-MM-DD>.zip"`，標題經 ASCII-safe slug 後保留 unicode 版本於 `filename*=UTF-8''`。
- 前端 meeting detail 加「匯出」按鈕，點下去觸發 browser download；i18n 「匯出 / Export」字串雙 locale 加入。
- 新增 Recording window 對 export 的契約：spec `recording-retention` 加 requirement「Export bundle MUST exclude WAVs whose Recording row has `deleted_at IS NOT NULL`」，與既有 cleanup job 並列。
- 無新環境變數；ZIP 串流 chunk size 直接寫成常數 `EXPORT_WAV_CHUNK_BYTES = 1024 * 1024`（1 MiB），不暴露到設定。

## Non-Goals

- 跨多場 meeting 的批次匯出（v1 只支援 per-meeting export）。
- 加密 / 簽章 ZIP（無 password、無 signature）。
- 匯入回放 — 本 slice 只做 export，沒有對應 `POST /api/meetings/import`。
- 自訂匯出選項（不選欄位、不選 recordings、不選 transcript 切片）；ZIP 結構固定。
- Cloud upload / share link — bundle 就是 browser download，不寫 S3 / Drive。
- 修改 30 天 Recording window 或新增延長機制 — 過期 Recording 一律排除而非延展存活。
- Free-form playbook markdown 與 7 個結構化欄位的渲染樣式調整（沿用 slice-04 已落地的 markdown 渲染規則，僅組合輸出文字）。

## Capabilities

### New Capabilities

- `meeting-export`: 提供 `MeetingExportBundler` deep module、`GET /api/meetings/{id}/export` 串流端點、ZIP 檔案命名規則、Playbook / transcript / summary markdown 序列化規則，以及前端匯出按鈕的互動契約。

### Modified Capabilities

- `recording-retention`: 新增「Export bundle MUST exclude expired recordings」requirement，補上 30 天 Recording window 對 export 路徑的強制保證。

## Impact

- Affected specs:
  - New: `openspec/specs/meeting-export/spec.md`
  - Modified: `openspec/specs/recording-retention/spec.md`
- Affected code:
  - New:
    - `packages/backend/meeting_playbook/export/__init__.py`
    - `packages/backend/meeting_playbook/export/bundler.py`
    - `packages/backend/meeting_playbook/export/markdown.py`
    - `packages/backend/meeting_playbook/export/router.py`
    - `packages/backend/tests/export/__init__.py`
    - `packages/backend/tests/export/test_bundler.py`
    - `packages/backend/tests/export/test_markdown.py`
    - `packages/backend/tests/export/test_router.py`
    - `packages/web/src/components/export-meeting-button.tsx`
    - `packages/web/src/components/export-meeting-button.test.tsx`
    - `packages/web/src/lib/export-api.ts`
  - Modified:
    - `packages/backend/meeting_playbook/server.py`
    - `packages/web/src/routes/meetings/detail.tsx`
    - `packages/web/src/locales/zh-TW.json`
    - `packages/web/src/locales/en.json`
  - Removed: (none)
- No new environment variables.
