- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/13 (Slice 12 — Qwen3-ASR)
- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/14 (Slice 13 — Recording retention)
- ADR-0028: https://github.com/SeanChenR/meeting-playbook/blob/main/docs/adr/0028-qwen3-asr-replaces-vibevoice.md

## Why

兩件 infra 工作合一個 slice，因為都在 detail page 上半 metadata 卡片同個區塊出現（ASR selector + Re-run button + Recording 狀態 badge），且都不動 user-facing UX 太多 — 拆兩個 change 的 propose / apply / archive 儀式成本不值得。

(a) **ASR 升級** — Slice 6 到 Slice 10 都是 Whisper Large v3，Mandarin WenetSpeech meeting WER 19.11；Qwen3-ASR-1.7B-MLX-8bit 同 benchmark 5.88（3.2× 好），對 Sean 主要中文 B2B 會議是決定性差距。Sean 主要做中文，**Qwen3 設為新會議預設**；保留 Whisper 為選項，因為英文 / 多語混雜場景仍由 Whisper 廣為驗證。

(b) **Recording retention** — 每場會議 2 條 wav 檔（30 fps 16kHz × 2 stream ≈ 30MB / 小時），會議數量累積 → 磁碟膨脹。ADR-0020 + PRD 訂的 30 天保留期一直沒實作。本 slice 補上 + 加 `deleted_at` 欄位保留「曾經錄過音」歷史事實。

## What Changes

- 新後端模組 `packages/backend/meeting_playbook/asr/qwen3_provider.py`（MLX 包裝 `doggy8088/Qwen3-ASR-1.7B-MLX-8bit`，實作既有 `ASRProvider` Protocol）+ `factory.py`（依 provider name + stream 拿 process-scoped 單例）
- 替換 `sessions/dependencies.py` 的 `_whisper_singleton_me/counterparty` `lru_cache` pattern；新加 `get_asr_providers_for_meeting(meeting_id)` 在 WS 連線時依 `meeting.asr_provider` 動態選 provider
- `Meeting.asr_provider` **預設值改 `qwen3`**（既有資料不 back-fill — 老會議是用 Whisper 錄的，保留 `whisper` 字面為歷史事實）
- 新模組 `packages/backend/meeting_playbook/retention/{job,runtime}.py`：
  - `RecordingRetentionJob.cleanup(now)` — 找 `created_at < now() - {RECORDING_RETENTION_DAYS} days AND deleted_at IS NULL` 的 row → 刪 wav 檔 + 設 `deleted_at = now()`
  - `runtime.run_forever()` — `asyncio.sleep(24h)` 迴圈
  - 透過 FastAPI `lifespan` async context manager 在 server.py 啟動時 spawn，shutdown 時 cancel
- Alembic migration `0007_add_recording_deleted_at` — `recording.deleted_at TIMESTAMPTZ NULL`
- Config 加 `recording_retention_days: int = 30` 設定欄位
- 新 HTTP endpoint `POST /api/meetings/{id}/rerun_asr`：
  - Validate ownership / status=completed / `recordings.deleted_at IS NULL` / 兩個 wav 檔在磁碟上（paranoia 雙 check）
  - 透過新 `rerun/runtime.py` 的 in-flight registry（同 slice-10 summary pattern）spawn 背景 task
  - 202 `{status: "pending"}` / 409 `rerun.busy` / 410 `rerun.recording_expired` / 404 meeting.not_found
- 新 HTTP endpoint `GET /api/meetings/{id}/rerun_asr_status` — `{status: "idle"|"pending"|"failed", chunks_processed, chunks_total}`，前端 1 秒 polling
- 背景 re-run task：開新 AsyncSession → `SELECT * FROM recording` 拿兩個 wav 路徑 → 用 `meeting.asr_provider` 對應的 provider，每個 wav chunk 成 10 秒 window → 蒐集所有 transcript_chunk → **單一 transaction** 內 `DELETE FROM transcript_chunk WHERE meeting_id = ?` + `INSERT ... RETURNING`（原子替換）→ in-flight registry pop
- 失敗（任何 chunk inference 出錯）→ 不動既有 transcript_chunk row + log + pop registry
- Re-run 期間 `MeetingSummarizer` 拒絕 trigger（避免拿到舊 transcript 生 summary 然後新 transcript 寫進去之後 stale）— 透過 stale flag 既有機制體現，summary 變 stale 就行
- 新 `meeting-management` 端點回 `recordings_available: bool`（false 當且僅當 *所有* recording 的 `deleted_at IS NOT NULL`）+ `rerun_asr_pending: bool`（從 in-flight registry 算）
- 前端：detail 頁面 metadata 卡片上半部新增三個元素：
  - ASR provider dropdown（取代既有唯讀「ASR 引擎」label）— 選項：Whisper / Qwen3，切換立刻 PUT 到 `/api/meetings/{id}`，下次 session 才生效（hover hint「切換下一場會議生效」）
  - Recording 狀態文字 badge — 「錄音可用」/「錄音已過期」（不用 emoji 照 Sean UI 規矩，用 dot 顏色 + 文字）
  - 「重新轉錄」按鈕 — 只在 `status === "completed"` AND `recordings_available === true` AND `rerun_asr_pending === false` 才出現；點擊 → POST /rerun_asr → 進 pending 狀態 → 1 秒 polling 直到完成 → invalidate transcript_chunks query → workspace transcript pane 自動 refetch 拿到新版
  - Re-run 進行中：transcript pane 顯示 skeleton + 「重新轉錄中... ({n}/{總} chunks)」
- 新後端依賴：`mlx`、`mlx-lm`（apply 階段先花 5 分鐘 spike 確認 `doggy8088/Qwen3-ASR-1.7B-MLX-8bit` 用哪個 loader API；可能改成 `mlx-whisper`）；`huggingface_hub` 應已透過 faster-whisper 帶入，先驗證再決定要不要明列
- 新 i18n keys: `meetings.detail.asrProvider.{label, whisper, qwen3, switchHint}`、`meetings.detail.recording.{available, expired}`、`meetings.detail.rerun.{button, inProgress, completed, failed}`、`errors.rerun.{busy, recording_expired, not_completed}`

## Non-Goals

- 第三個 ASR provider（Deepgram / AssemblyAI / etc.）— 純 MLX 單機 + faster-whisper 兩家
- 即時切換 provider — 切了下一場才生效（per Issue #13 acceptance criteria）
- Re-run progress 透過 WebSocket push — 用 HTTP polling（per Sean 拍板）
- Multi-region recording / S3 / cloud sync — 純本機 wav 檔
- 不同 retention 期間 per meeting — 全域 `RECORDING_RETENTION_DAYS`，無 per-meeting 覆寫
- 軟刪除 row recovery — `deleted_at` 是單向，不提供 undelete
- ASR provider 自動偵測語言 — 維持手動選（避免 cold start 載兩個 model ≈ 4GB+）
- Re-run cancel 功能 — 跑了就跑完，無中途停止 button（YAGNI；2-5 分鐘的 task）
- Re-run 跨多個 meeting 批次 — 一次一場
- Re-run 寫進新 row 保留歷史版本 — 直接覆寫，無轉錄版本控
- APScheduler — 用 `asyncio.sleep(24h)` 純迴圈，省一個依賴
- 同步刪除舊 wav 檔（meeting delete CASCADE 觸發） — 維持現狀（目前 meeting delete 不刪實體 wav 檔，是 known limitation；本 slice 不處理）
- Backfill 既有 row 的 `deleted_at`（如果 wav 檔已不在磁碟上）— 不檢查既有 row 磁碟狀態；只有 cleanup 跑到才開始填
- VibeVoice provider — ADR-0028 已 deprecate；本 slice 不實作（任何提到 VibeVoice 的舊 issue / 註解都該清）
- ASR provider 影響 advisor / summary 的 prompt — Whisper 跟 Qwen3 都產出同樣 transcript_chunk 結構，下游 LLM 不知道也不用知道是哪家轉的

## Capabilities

### New Capabilities

- `asr-provider-selection`: Whisper / Qwen3 並存的 ASR 引擎選擇 + per-meeting selector + 重新轉錄完整契約 — Qwen3ASRProvider 實作、ASR factory、`Meeting.asr_provider` 預設改 qwen3、re-run POST + GET status endpoints、in-flight registry、原子 transcript 替換邏輯、預設 Qwen3 / 保留 Whisper 為 fallback 的決策
- `recording-retention`: 30 天 wav 檔自動清理 — `recording.deleted_at` 欄位、`RecordingRetentionJob.cleanup` 邏輯、`asyncio.sleep(24h)` 迴圈、FastAPI lifespan 整合、`RECORDING_RETENTION_DAYS` 設定欄位、cleanup 不刪 row 只設 timestamp 的「歷史保留」設計

### Modified Capabilities

- `meeting-detail-layout`: detail 頁面上半 metadata 卡片新增 3 個 UI 元素 — ASR provider dropdown（取代既有唯讀 label）、Recording 狀態 badge（available / expired）、「重新轉錄」按鈕（gating: completed + recordings_available + 非 pending）；re-run 進行中時 workspace transcript pane 顯示 skeleton + 進度文字
- `meeting-management`: `Meeting.asr_provider` 預設值從 `whisper` 改 `qwen3`；GET `/api/meetings/{id}` 回應加 `recordings_available: bool` + `rerun_asr_pending: bool` 兩個 derived 欄位
- `meeting-session`: WS connect 時不再用全域 `_whisper_singleton_me/counterparty`，改用 `get_asr_providers_for_meeting(meeting_id)` 依 `meeting.asr_provider` 動態選 provider；warmup 維持 lazy

## Impact

- 後端新檔：
  - `packages/backend/alembic/versions/0007_add_recording_deleted_at.py` — Alembic migration 加 `recording.deleted_at` 欄位
  - `packages/backend/meeting_playbook/asr/qwen3_provider.py` — Qwen3ASRProvider impl
  - `packages/backend/meeting_playbook/asr/factory.py` — `get_provider_singleton(name, stream)` lru_cache factory
  - `packages/backend/meeting_playbook/retention/__init__.py`
  - `packages/backend/meeting_playbook/retention/job.py` — `RecordingRetentionJob.cleanup`
  - `packages/backend/meeting_playbook/retention/runtime.py` — `run_forever()` + lifespan helpers
  - `packages/backend/meeting_playbook/rerun/__init__.py`
  - `packages/backend/meeting_playbook/rerun/runtime.py` — in-flight registry + spawn helper（同 slice-10 模式）
  - `packages/backend/meeting_playbook/rerun/router.py` — POST + GET status endpoints
  - `packages/backend/meeting_playbook/rerun/transcribe.py` — wav file → chunks → provider → atomic transcript_chunk replacement
  - `packages/backend/tests/asr/test_qwen3_provider.py`
  - `packages/backend/tests/asr/test_factory.py`
  - `packages/backend/tests/retention/__init__.py`
  - `packages/backend/tests/retention/test_job.py`
  - `packages/backend/tests/retention/test_runtime.py`
  - `packages/backend/tests/rerun/__init__.py`
  - `packages/backend/tests/rerun/test_runtime.py`
  - `packages/backend/tests/rerun/test_router.py`
  - `packages/backend/tests/rerun/test_transcribe.py`
  - `packages/backend/tests/test_alembic_recording_deleted_at.py`
- 後端修改：
  - `packages/backend/meeting_playbook/asr/__init__.py` — re-export Qwen3ASRProvider
  - `packages/backend/meeting_playbook/sessions/dependencies.py` — 移除舊 singleton；改用 `get_asr_providers_for_meeting(meeting_id)`
  - `packages/backend/meeting_playbook/sessions/router.py` — WS connect 時 call `get_asr_providers_for_meeting(meeting_id)`，不再用 dependency injection 拿 providers（meeting_id 在 path 已知）
  - `packages/backend/meeting_playbook/meetings/models.py` — `asr_provider` default 改 qwen3
  - `packages/backend/meeting_playbook/meetings/repository.py` — `create` 的 `asr_provider` default 改 qwen3
  - `packages/backend/meeting_playbook/meetings/router.py` — GET `/api/meetings/{id}` response 加 `recordings_available` + `rerun_asr_pending` 欄位
  - `packages/backend/meeting_playbook/server.py` — 加 FastAPI `lifespan`，spawn retention job
  - `packages/backend/meeting_playbook/config.py` — 加 `recording_retention_days: int = 30`
  - `packages/backend/pyproject.toml` — 新增 `mlx`、`mlx-lm`（或 `mlx-whisper`，視 spike 結果）
  - `packages/backend/tests/conftest.py` — 既有 truncate cascade 不變（`recording` 已在列）
  - `packages/backend/tests/sessions/test_router.py` — 既有 dual-stream 測試 update 用新 factory
  - `packages/backend/tests/meetings/test_endpoints.py` — GET 回應 schema 新欄位
  - `.env.example` — 新增 `RECORDING_RETENTION_DAYS=30` 註解區塊
- 前端新檔：
  - `packages/web/src/lib/rerun-api.ts` — POST + GET status 包裝 + `RerunApiError`
  - `packages/web/src/lib/rerun-api.test.ts`
  - `packages/web/src/components/asr-provider-selector.tsx` — Whisper / Qwen3 dropdown
  - `packages/web/src/components/asr-provider-selector.test.tsx`
  - `packages/web/src/components/recording-badge.tsx` — available / expired 狀態
  - `packages/web/src/components/recording-badge.test.tsx`
  - `packages/web/src/components/rerun-button.tsx` — gating + pending overlay
  - `packages/web/src/components/rerun-button.test.tsx`
  - `packages/web/src/hooks/use-rerun-status.ts` — React Query polling hook
  - `packages/web/src/hooks/use-rerun-status.test.tsx`
- 前端修改：
  - `packages/web/src/lib/meetings-api.ts` — Meeting type 加 `recordings_available` + `rerun_asr_pending` + asr_provider mutation helper
  - `packages/web/src/lib/meetings-api.mutations.test.tsx` — 新 PUT asr_provider mutation 測試
  - `packages/web/src/components/transcript-pane.tsx` — re-run pending overlay（skeleton + 進度文字）
  - `packages/web/src/components/transcript-pane.test.tsx` — pending overlay test
  - `packages/web/src/routes/meetings/detail.tsx` — metadata 卡片整合三個新元件 + invalidation 對應
  - `packages/web/src/routes/meetings/detail.test.tsx` — 三組新整合測試
  - `packages/web/src/locales/zh-TW.json` + `packages/web/src/locales/en.json` — 新 i18n keys
- 文件：
  - `docs/agents/asr-providers.md` — 更新或新增：Whisper / Qwen3 並存架構、factory pattern、re-run 流程、provider 選擇 timing（WS connect 時）
  - `docs/agents/recording-retention.md` — 新增：cleanup job 流程、deleted_at 語意、lifespan 整合
