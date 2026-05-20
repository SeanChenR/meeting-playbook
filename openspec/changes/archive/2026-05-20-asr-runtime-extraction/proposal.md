## Why

Backend ASR 載入跟主 FastAPI 共享 process，撞到三個實務問題：
（1）Qwen3-ASR-1.7B 約 5 GB 的權重塞進 FastAPI worker，記憶體跟 Mac M3 Pro 18 GB 的其他服務（auth gateway + Vite + backend）搶資源，模型載完很容易把整台機器拖慢；
（2）模型 load 失敗（例如近期撞到的 `Cannot copy out of meta tensor` 跟 Hugging Face 下載中斷）會直接讓 backend worker 重啟，把 session WebSocket 整條斷掉；
（3）我（Sean）的機器跑 Whisper Large v3 太吃 CPU，但目前仍是雙引擎並存的維護成本（兩份 provider、兩份 test fixture、兩個 settings logo），想趁這次拆 runtime 一併收掉。

把 ASR 拉到獨立 micro-service 後，模型只 load 一次、自己擁有記憶體預算；backend 透過 HTTP/WebSocket 跟它對話，失敗時退化成 `error_code: asr.runtime_unavailable` 而不是整個 session 倒下。

## What Changes

- 新增 packages/asr-runtime/：獨立的 FastAPI / uvicorn 服務，跑在 127.0.0.1:8100（可由 `ASR_RUNTIME_PORT` override），唯一暴露的能力是 Qwen3-ASR transcription 端點。
- 通訊協定：**WebSocket** 為主（/v1/transcribe/stream，跟 backend meeting-session 串接）+ HTTP POST /v1/transcribe/chunk 為輔（離線 ingest 用），訊息格式跟現有 `ASRProvider.transcribe_chunk` 對齊（`audio_bytes`、`sample_rate_hz`、optional `language_hint` → `TranscriptChunk`）。
- packages/backend 端：
  - 新增 RemoteAsrRuntimeClient，實作 `ASRProvider` interface，把每個 chunk forward 到 asr-runtime。
  - ASRProviderFactory 在 `ASR_RUNTIME_URL` 有設定時改用 remote client；env 缺值時 fail-fast 並回 `asr.runtime_unavailable`。
  - **BREAKING** 移除 whisper provider、相關 test、`WhisperConfig` env vars (`WHISPER_*`)、`ASRProvider` enum 的 `whisper` 值；任何持久化資料裡 `asr_provider = "whisper"` 的會議在讀取時 fallback 成 `"qwen3"` 並寫 lint warning，不阻斷讀取。
  - meeting-session WebSocket router 跟 offline-ingest job runner 不再直接持有 ASR 模型，只透過 factory 拿到 `ASRProvider`。
- packages/web 端：
  - Settings preferences card 移除 Whisper 選項，只剩 Qwen3-ASR。
  - 會議 detail 的 ASR engine dropdown 同步只剩 Qwen3-ASR。
  - 對應 i18n key 刪除 (`asrProvider.whisper*`)。
- 新增 root-level 啟動腳本：root devserver script 用 concurrently 多加一條 asr-runtime；`.env.example` 補上 `ASR_RUNTIME_URL`、`ASR_RUNTIME_PORT`、`ASR_RUNTIME_DEVICE`、`ASR_RUNTIME_MODEL_REPO`、`ASR_RUNTIME_WARMUP_ON_BOOT`。
- ADR-0027（new）紀錄 ASR runtime 拆分的決策。

## Non-Goals

- 不切換 ASR 模型（保留 Qwen3-ASR-1.7B，不評估 v3、不評估 Vertex AI 雲端 ASR）。
- 不拆分 LLM 呼叫（Gemini Flash / 2.5 Pro 仍在 backend，advisor 跟 summary 不動）。
- 不做多用戶並發（runtime 仍假設單一使用者；佇列管控留給未來）。
- 不引入 gRPC / Protocol Buffers — 保留 JSON over WebSocket，跟 session 協定一致。
- 不做 GPU 雲端部署 — runtime 仍跑在本機 macOS MPS 上。

## Capabilities

### New Capabilities

- `asr-runtime`: 獨立的 ASR transcription micro-service，定義它對外的 WebSocket / HTTP 端點、輸入輸出 schema、健康檢查、錯誤回應、startup warmup、跟 backend 的 contract。

### Modified Capabilities

- `asr-provider-selection`: enum / dropdown / persistence 只剩 `qwen3` 值；`whisper` 從可選清單移除（讀取舊資料時 fallback）。
- `meeting-session`: realtime ASR 改走 remote runtime；新增 `asr.runtime_unavailable` 錯誤碼跟 session 行為（degrade vs hard-fail）。
- `offline-ingest`: 離線轉錄 job 改走 remote runtime；失敗的 retry / backoff 行為需要重定義。

## Impact

- Affected specs:
  - 新：openspec/specs/asr-runtime/spec.md
  - 改：openspec/specs/asr-provider-selection/spec.md、openspec/specs/meeting-session/spec.md、openspec/specs/offline-ingest/spec.md
- Affected code:
  - 新：
    - packages/asr-runtime/pyproject.toml
    - packages/asr-runtime/meeting_playbook_asr_runtime/__init__.py
    - packages/asr-runtime/meeting_playbook_asr_runtime/server.py
    - packages/asr-runtime/meeting_playbook_asr_runtime/routes/transcribe.py
    - packages/asr-runtime/meeting_playbook_asr_runtime/schemas.py
    - packages/asr-runtime/meeting_playbook_asr_runtime/qwen3_runner.py
    - packages/asr-runtime/tests/test_transcribe_ws.py
    - packages/asr-runtime/tests/test_transcribe_http.py
    - packages/asr-runtime/tests/test_health.py
    - packages/backend/meeting_playbook/asr/remote_runtime_client.py
    - packages/backend/tests/asr/test_remote_runtime_client.py
    - docs/adr/0027-asr-runtime-extraction.md
  - 改：
    - packages/backend/meeting_playbook/asr/factory.py
    - packages/backend/meeting_playbook/asr/types.py（移除 whisper enum）
    - packages/backend/meeting_playbook/sessions/router.py
    - packages/backend/meeting_playbook/offline_ingest/runner.py
    - packages/backend/meeting_playbook/config.py（新 env vars）
    - packages/backend/tests/asr/test_factory.py
    - packages/web/src/components/meeting-detail-action-bar.tsx（dropdown 只剩 qwen3）
    - packages/web/src/components/asr-provider-selector.tsx
    - packages/web/src/routes/settings/preferences.tsx
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
    - .env.example
    - package.json（root，concurrently script 加 asr-runtime）
    - README.md
  - 移除：
    - packages/backend/meeting_playbook/asr/whisper_provider.py
    - packages/backend/tests/asr/test_whisper_provider.py
    - packages/backend/meeting_playbook/asr/qwen3_provider.py（邏輯搬到 asr-runtime；factory 不再直接 import qwen-asr）
    - packages/web/public/icons/whisper.png
