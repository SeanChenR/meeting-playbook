> Source: GitHub Issue [#25](https://github.com/SeanChenR/meeting-playbook/issues/25)
> Discussion: 2026-05-15 grill session — see `design.md` for the 7 收斂決策

## Why

`scheduled_end_at` 已過、從未 live capture 的會議目前是死巷 — 使用者手上有的音檔（手機錄音、Zoom 匯出、Voice Memo）沒處理入口，逐字稿與 Playbook 後續產物完全產不出來。S12 的 single-channel finalize 路徑已完備，但只能跑空轉測試 fixture；S14 把這條 pipeline 接到 production 第一個現實入口。

## What Changes

- **Backend**：新增 `OfflineIngestPipeline` 走 validate → store → ffmpeg 轉碼 → 觸發 ASR；ASR background task reuse `rerun/runtime.py` 的 in-flight registry + progress 模式
- **API**：tus 1.0 protocol 端點 `POST /api/meetings/{id}/recordings/offline_upload`（resumable chunked upload，accept wav / mp3 / m4a / aac / flac / ogg；3 小時 / 500MB 上限）
- **Schema**：`recording` 表加 `source TEXT NOT NULL DEFAULT 'live' CHECK (source IN ('live','offline'))` 與 `started_at TIMESTAMPTZ NULL`（S16 chunk timestamp 也用得到）；alembic 0011 migration 可逆
- **Frontend**：meeting detail 上方 conditional banner（`status = scheduled` AND `now > scheduled_end_at` AND 無 recording），含 dropzone + 「實際開始時間」input + 上傳進度條 + ASR 進度提示
- **i18n**：雙 locale 字串 `offline_ingest.*` 與錯誤碼
- **CONTEXT.md glossary**：加入 *Live capture (即時擷取)* 與 *Offline ingest (離線匯入)*

## Non-Goals

- **不**支援多檔合併或多軌音檔分軌處理（單檔 → 單 recording）
- **不**支援上傳會議直接重新觸發 Playbook 生成（playbook 沿用 pre-meeting 既有產物）
- **不**改 live capture 的 single-channel UI 入口（BlackHole 仍是 live capture 前提；此 gap 留下個 slice）
- **不**支援匿名 / 跨 device tus session（個人單機使用足夠）

## Capabilities

### New Capabilities

- `offline-ingest`: 預錄音檔上傳 + 轉碼 + ASR 完整 vertical pipeline，含 tus resumable upload 契約與 background task progress 模式

### Modified Capabilities

- `meeting-management`: `recordings_available` derived field 涵蓋 `source = "offline"` 的 recording
- `recording-retention`: 30 天保留期明示涵蓋 `source = "offline"` 的 recording WAV

## Impact

- Affected specs: new `offline-ingest`; modified `meeting-management` / `recording-retention`
- Affected code:
  - New:
    - `packages/backend/alembic/versions/0011_recording_source_and_started_at.py`
    - `packages/backend/meeting_playbook/offline_ingest/__init__.py`
    - `packages/backend/meeting_playbook/offline_ingest/router.py`
    - `packages/backend/meeting_playbook/offline_ingest/tus_protocol.py`
    - `packages/backend/meeting_playbook/offline_ingest/pipeline.py`
    - `packages/backend/meeting_playbook/offline_ingest/runtime.py`
    - `packages/backend/meeting_playbook/offline_ingest/transcode.py`
    - `packages/backend/tests/offline_ingest/test_tus_protocol.py`
    - `packages/backend/tests/offline_ingest/test_pipeline.py`
    - `packages/backend/tests/offline_ingest/test_router.py`
    - `packages/backend/tests/offline_ingest/test_runtime.py`
    - `packages/backend/tests/integration/test_offline_ingest_e2e.py`
    - `packages/web/src/components/offline-ingest/UploadBanner.tsx`
    - `packages/web/src/components/offline-ingest/UploadDialog.tsx`
    - `packages/web/src/lib/tus-uploader.ts`
    - `packages/web/src/lib/offline-ingest-api.ts`
    - `packages/web/src/components/offline-ingest/UploadBanner.test.tsx`
    - `packages/web/src/lib/tus-uploader.test.ts`
  - Modified:
    - `packages/backend/meeting_playbook/sessions/models.py`
    - `packages/backend/meeting_playbook/server.py`
    - `packages/backend/meeting_playbook/config.py`
    - `packages/backend/pyproject.toml`
    - `packages/web/src/routes/meetings/detail.tsx`
    - `packages/web/src/locales/zh-TW.json`
    - `packages/web/src/locales/en.json`
    - `.env.example`
    - `CONTEXT.md`
