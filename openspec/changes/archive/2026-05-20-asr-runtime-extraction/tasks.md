## 1. ASR runtime package scaffold

- [x] [P] 1.1 (Decision 1 — Runtime 拆分方式：獨立 FastAPI micro-service；Requirement: Runtime configured via env vars only) 在 `packages/asr-runtime/` 建立 Python package：`pyproject.toml`（uv-managed，dependencies = fastapi + uvicorn + qwen-asr + torch + structlog）、`meeting_playbook_asr_runtime/__init__.py`、空的 `server.py` / `schemas.py` / `qwen3_runner.py` / `routes/transcribe.py`。完成行為：`uv sync` 在 `packages/asr-runtime/` 下不報錯且能 import package；驗證：在該目錄 `uv run python -c "import meeting_playbook_asr_runtime"` 退出碼 0。

- [x] [P] 1.2 (Requirement: Runtime configured via env vars only；Scope boundaries 中的 `.env.example`) 在 `.env.example` 新增 5 個 env var (`ASR_RUNTIME_URL`、`ASR_RUNTIME_PORT`、`ASR_RUNTIME_DEVICE`、`ASR_RUNTIME_MODEL_REPO`、`ASR_RUNTIME_WARMUP_ON_BOOT`) 並都帶 default。完成行為：dev 環境 unset 任何一個都會走 design 列出的 default value；驗證：`grep ASR_RUNTIME .env.example | wc -l` ≥ 5。

## 2. Qwen3 runner core (TDD) — Decision 6 — 模型 `meta tensor` bug：runtime 內部直接固定為 CPU-then-MPS + Requirement: Model loading sidesteps accelerate meta-tensor dispatch

- [x] 2.1 (Requirement: Runtime concurrency serialised via asyncio Lock) 紅燈：先寫 `packages/asr-runtime/tests/test_qwen3_runner.py`，用一個 10 秒 silent int16 PCM bytes 呼叫 `Qwen3Runner.transcribe(...)`，斷言回傳 `TranscriptChunk` 帶非 None 的 `started_at` / `ended_at`、`text == ""`（silent ⇒ empty text）。驗證：`uv run pytest tests/test_qwen3_runner.py::test_silent_returns_empty_text -x` fail（NotImplemented）。

- [x] 2.2 (Decision 6 — 模型 `meta tensor` bug：runtime 內部直接固定為 CPU-then-MPS；Requirement: Model loading sidesteps accelerate meta-tensor dispatch + Requirement: Runtime concurrency serialised via asyncio Lock) 綠燈：寫 `qwen3_runner.py` 的 `Qwen3Runner` class：建構 lazy load 模型；`load()` 採 CPU-then-`.to(device)` 策略繞過 accelerate meta-tensor bug；`transcribe(audio_bytes, sample_rate_hz, language_hint=None) → TranscriptChunk`；內部 `asyncio.Lock` 序列化 inference。完成行為：silent input 回空 text 不丟錯；驗證：上面的 test_silent_returns_empty_text 通過 + 新加一條 test `test_concurrent_calls_serialized` 用 `asyncio.gather` 同時打兩個 chunk，斷言兩次都成功且 lock 確實序列化（用 monkeypatch 計數同時進入 lock 區間的人數 ≤ 1）。

- [x] 2.3 (Decision 2 — Wire protocol：WebSocket 主、HTTP 輔；Interfaces / data shapes — base64 PCM helpers) 重構：把 base64 ↔ int16 PCM 的轉換抽到 `schemas.py` 的 helper（重用於 HTTP / WebSocket 路由）。驗證：runner test 仍通過，新 `tests/test_schemas.py` 對 helper 做 round-trip 測試（encode → decode 等於原 bytes）。

## 3. HTTP transcribe endpoint (TDD) — Decision 2 wire protocol；Requirement: HTTP chunk transcription endpoint

- [x] 3.1 (Requirement: HTTP chunk transcription endpoint — successful path scenario) 紅燈：新 `tests/test_transcribe_http.py`，用 FastAPI TestClient 對 `POST /v1/transcribe/chunk` 送一個 base64 silent chunk，斷言 200 回 JSON 帶 `text`、`started_at`、`ended_at`。驗證：`uv run pytest tests/test_transcribe_http.py -x` fail（route 未實作）。

- [x] 3.2 (Decision 7 — Error contract：`error_code: asr.runtime_unavailable` + retry on backend；Requirement: HTTP chunk transcription endpoint — failed chunk returns structured error；Failure modes) 綠燈：在 `routes/transcribe.py` 實作 `POST /v1/transcribe/chunk`，接 `ChunkRequest` schema → 呼叫 `Qwen3Runner.transcribe` → 回 `ChunkResponse`。runtime 失敗一律包成 `error_code: asr.runtime_unavailable, retriable: false` JSON + HTTP 503。驗證：上面測試通過 + 新測 `test_transcribe_http_runtime_error_shape`，monkeypatch runner raise → 斷言 503 + `error_code` 欄位。

## 4. WebSocket transcribe endpoint (TDD) — Decision 2 wire protocol；Requirement: WebSocket realtime transcription endpoint

- [x] 4.1 (Requirement: WebSocket realtime transcription endpoint — Client opens stream and receives ready signal + Audio chunk produces transcript chunk) 紅燈：新 `tests/test_transcribe_ws.py`，連上 `/v1/transcribe/stream`，送 `{"type":"config", "sample_rate_hz":16000}`、然後一個 `audio_chunk` frame，斷言收到 `ready` + `transcript_chunk` frame（含 `sequence` 跟 input 相同）。驗證：`uv run pytest tests/test_transcribe_ws.py -x` fail。

- [x] 4.2 (Decision 7 — Error contract：`error_code: asr.runtime_unavailable` + retry on backend；Requirement: WebSocket realtime transcription endpoint — Server closes connection on error；Failure modes — chunk-level failures) 綠燈：實作 WebSocket route — handshake 等 `config`、之後 loop 收 `audio_chunk` / 回 `transcript_chunk`、`sequence` 透傳；任何錯誤回 `{"type":"error","error_code":"asr.runtime_unavailable","retriable":bool}` 後 close。驗證：上面測試通過 + 新測 `test_ws_error_closes_connection`：monkeypatch runner raise → 斷言收到 error frame 後 socket 立即關閉。

## 5. Health + warmup lifespan (TDD) — Decision 5 startup warmup；Requirements: Health check + Optional startup warmup

- [x] [P] 5.1 (Requirement: Health check endpoint reports model load state — three scenarios) 紅燈：新 `tests/test_health.py`，三條：`status: loading` 在 lifespan startup 完前、`status: ready` 在 warmup 後、`status: error` 在 monkeypatch 讓 warmup raise 時。驗證：`uv run pytest tests/test_health.py -x` fail。

- [x] 5.2 (Decision 5 — startup warmup：opt-in via env；Requirement: Optional startup warmup — Warmup enabled by default + can be disabled) 綠燈：實作 uvicorn lifespan：startup 階段建 `Qwen3Runner` 單例 + 視 `ASR_RUNTIME_WARMUP_ON_BOOT` 決定是否跑 0.5 秒 silent warmup；`/healthz` 路由用 module-level state 報 status。完成行為：runtime 啟動後 `curl /healthz` 反映三種狀態之一；驗證：health tests 全綠 + 手動 `curl 127.0.0.1:8100/healthz` 在 `WARMUP_ON_BOOT=0` 跟 `=1` 兩個路徑下都能正確分辨。

## 6. Backend remote client (TDD) — Decision 3；Requirement: Qwen3ASRProvider implements ASRProvider Protocol via MLX 8-bit model (MODIFIED)

- [x] 6.1 (Requirement: Qwen3ASRProvider implements ASRProvider Protocol via MLX 8-bit model — Scenarios: First transcribe_chunk opens runtime connection + warmup() pings the runtime healthz endpoint + Runtime unavailable surfaces a structured error) 紅燈：新 `packages/backend/tests/asr/test_remote_runtime_client.py`，用 `pytest-httpx` mock HTTP `/v1/transcribe/chunk`：成功路徑回 `TranscriptChunk`、5xx 路徑 raise `AsrRuntimeUnavailableError`、`warmup()` 對 `/healthz` poll 直到 `ready`。驗證：`uv run pytest tests/asr/test_remote_runtime_client.py -x` fail。

- [x] 6.2 (Decision 3 — Backend 接 runtime 的方式：`RemoteAsrRuntimeClient` 實作 `ASRProvider`；Requirement: Qwen3ASRProvider implements ASRProvider Protocol via MLX 8-bit model — RemoteAsrRuntimeClient satisfies the ASRProvider Protocol) 綠燈：在 `packages/backend/meeting_playbook/asr/remote_runtime_client.py` 實作 `RemoteAsrRuntimeClient(ASRProvider)`：建構接 `stream` + `runtime_url`，long-lived `aiohttp.ClientSession`，`transcribe_chunk` 走 HTTP POST、`warmup` 對 `/healthz` poll、所有非 2xx / WS error frame 都包成 `AsrRuntimeUnavailableError`。完成行為：實作後 isinstance(provider, ASRProvider) True；驗證：上面測試全綠。

## 7. Factory + Whisper removal (TDD) — Decision 4 移除 Whisper；Requirements: ASR factory selects provider per meeting at WebSocket connect time (MODIFIED) + WhisperProvider is offered alongside Qwen3 (REMOVED)

- [x] 7.1 (Requirement: ASR factory selects provider per meeting at WebSocket connect time — Factory returns RemoteAsrRuntimeClient + Legacy provider names coerce to qwen3 + Runtime URL missing raises an explicit error) 紅燈：更新 `packages/backend/tests/asr/test_factory.py` — 改測「factory 只回 `RemoteAsrRuntimeClient`」「`provider_name='whisper'` 被 coerce 成 `qwen3` 並 emit structlog warning」「`ASR_RUNTIME_URL` 未設時 raise `AsrRuntimeUnavailableError`」；刪掉舊的 Whisper 相關 test case。驗證：`uv run pytest tests/asr/test_factory.py -x` 紅燈。

- [x] 7.2 (Decision 4 — 移除 Whisper：硬性 breaking change + 讀取時 fallback；Requirement: WhisperProvider is offered alongside Qwen3 — REMOVED) 綠燈：改寫 `packages/backend/meeting_playbook/asr/factory.py`：移除 Whisper import / case、coerce 未知值 + warning log、缺 env var raise。刪除 `whisper_provider.py`、`test_whisper_provider.py`、`qwen3_provider.py`（model load 邏輯已搬到 asr-runtime）、`WhisperConfig` 在 `config.py` 內的相關欄位、`.env.example` 內 `WHISPER_*` 行。完成行為：grep `whisper` packages/backend 排除註解後 0 hit（保留 `_coerced from="whisper"` log 字串）；驗證：factory test 全綠 + `git grep -i whisper packages/backend | grep -v 'coerced' | grep -v test_factory.py` 期望空輸出。

## 8. Session router runtime-unavailable handling (TDD) — Decision 7 error contract；Requirement: ASR runs through one ASRProvider instance per stream with parallel warmup (MODIFIED)

- [x] 8.1 (Requirement: ASR runs through one ASRProvider instance per stream with parallel warmup — Runtime unavailable during connecting phase aborts session start + Runtime failure on a single chunk does not tear down the session；Observable behavior #4) 紅燈：在 `packages/backend/tests/sessions/test_router.py` 新增 case：mock `RemoteAsrRuntimeClient.warmup` raise `AsrRuntimeUnavailableError`，斷言 WebSocket 收到 `{"type":"error","error_code":"asr.runtime_unavailable",...}` 然後正常 close；另一條 case：mock `transcribe_chunk` 對單一 chunk raise，斷言 socket 不關 + 該 chunk 沒進 `transcript_chunk` 表。驗證：`uv run pytest tests/sessions/test_router.py -k runtime_unavailable -x` 紅燈。

- [x] 8.2 (Decision 7 — Error contract：`error_code: asr.runtime_unavailable` + retry on backend；Requirement: ASR runs through one ASRProvider instance per stream with parallel warmup — Warmup runs both providers in parallel) 綠燈：在 `packages/backend/meeting_playbook/sessions/router.py` connecting phase 包 `try/except AsrRuntimeUnavailableError` → 發 error frame + close；in_progress chunk 失敗只 drop + warning log，session 維持開啟。完成行為：runtime 沒起時 frontend 收到結構化錯誤而不是 connection drop；驗證：8.1 兩條 test 全綠。

## 9. Offline ingest retry + structured failure (TDD) — Requirement: Pipeline writes a single offline recording row and spawns ASR task (MODIFIED)

- [x] 9.1 (Requirement: Pipeline writes a single offline recording row and spawns ASR task — Runtime unavailable triggers bounded retry then job-level failure；Failure modes — offline ingest 失敗) 紅燈：在 `packages/backend/tests/offline_ingest/test_runtime.py` 新增 `test_runtime_unavailable_triggers_retry_then_fail`：mock client 連續 4 次 raise `AsrRuntimeUnavailableError`，斷言 task 走 3 次 exponential backoff（2s/4s/8s — 用 monkeypatch 加速器把 sleep 換成立刻完成 + 記錄等待時間）後把 progress row 標 `state="failed"` + `error_code="asr.runtime_unavailable"`；meeting status 不變成 completed。驗證：`uv run pytest tests/offline_ingest/test_runtime.py -k runtime_unavailable -x` 紅燈。

- [x] 9.2 (Requirement: Pipeline writes a single offline recording row and spawns ASR task — ASR task spawns with single-channel strategy via remote runtime) 綠燈：在 `packages/backend/meeting_playbook/offline_ingest/runtime.py` 的 chunk 轉錄循環包 `tenacity` 或手刻 retry decorator：retry 3 次 / 2-4-8 秒 backoff；最終失敗時 update `offline_ingest_progress` row 為 `failed` + 寫 error_code。驗證：9.1 通過。

## 10. Frontend: single ASR + i18n + Whisper UI removal — Decision 4；Scope boundaries — UI surface

- [x] [P] 10.1 (Observable behavior #5 — Settings preferences card 只剩 Qwen3 logo + label) 紅燈：更新 `packages/web/src/components/meeting-detail-action-bar.test.tsx` + `asr-provider-selector.test.tsx`：斷言 dropdown 只剩一個選項（Qwen3-ASR）、settings preferences card 也只剩 Qwen3、所有 `whisper` testid / 字串 0 hit。驗證：`bun --filter @meeting-playbook/web test src/components/meeting-detail-action-bar.test.tsx src/components/asr-provider-selector.test.tsx -t whisper` fail。

- [x] 10.2 (Decision 4 — 移除 Whisper：硬性 breaking change + 讀取時 fallback；Observable behavior #5) 綠燈：從 `asrOptions` array 移除 `whisper` 項目、`packages/web/src/routes/settings/preferences.tsx` 移除 Whisper provider card、刪 `packages/web/public/icons/whisper.png`、`zh-TW.json` + `en.json` 移除 `asrProvider.whisper*` keys。完成行為：UI 上只看得到 Qwen3 一個 ASR 選項；驗證：上面 tests 全綠 + `locales.test.ts` deep-equal 仍綠。

## 11. Root devserver script + README + ADR — Observable behavior #1 + Scope boundaries — packaging

- [x] 11.1 (Observable behavior #1 — Root dev script 啟動時看得到 `asr-runtime listening`) 在 root `package.json` 的 dev script 加一條 asr-runtime（用 `concurrently`，命名 `asr`，色塊 magenta，command 為 `cd packages/asr-runtime && uv run uvicorn meeting_playbook_asr_runtime.server:app --reload --host 127.0.0.1 --port $ASR_RUNTIME_PORT`）。完成行為：root dev script 啟動時終端機看到第四條 `[asr]` log 線、`asr-runtime listening on http://127.0.0.1:8100`；驗證：手動跑 root dev script 同時看到 4 條 prefix。

- [x] 11.2 (Decision 4 — 移除 Whisper：硬性 breaking change + 讀取時 fallback；Scope boundaries — README) 更新 `README.md`：新增 ASR runtime 段落（環境需求 / 啟動方式 / 健康檢查 / port 衝突 troubleshoot），移除舊的 Whisper 設定段落。完成行為：README 反映 ASR 拆 runtime 後的 onboarding 流程；驗證：人工檢視 `README.md` diff，無遺漏的 stale Whisper 字串。

- [x] 11.3 (Decision 1 — Runtime 拆分方式：獨立 FastAPI micro-service；Decision 4 — 移除 Whisper：硬性 breaking change + 讀取時 fallback；Risks / Trade-offs — runtime crash 沒有自動 restart) 新增 `docs/adr/0027-asr-runtime-extraction.md`：紀錄為何拆 runtime（記憶體 + 失敗隔離 + 移除 Whisper）、選用 FastAPI micro-service + WebSocket+HTTP 的理由、跟 ADR-0026 / 0028 (VibeVoice / Qwen3 替代) 的關係、單 process inference 假設、未來 multi-tenant / GPU 雲端的延伸方向。完成行為：ADR 文件存在且通過 `docs/adr/` README 的 frontmatter 格式檢查；驗證：人工 review + 跟 ADR-0025 / 0028 對讀無內容衝突。

## 12. Manual verification + spec archive readiness — Implementation Contract acceptance criteria

- [x] 12.1 (Implementation Contract — Acceptance criteria #1-5；Requirement: ASR runtime process isolation — Backend reload preserves model state + ASR runtime crash isolated from backend) 手動驗證設計 Implementation Contract 的 5 條 acceptance criteria（runtime 起得來 / 第一次開始會議 < 5s 出 dialog / 講話 10s 出 transcript / kill runtime 後前端收到 structured error / settings 只剩 Qwen3）。完成行為：5 條全通過、有 screenshot 或 log 證據；驗證：把 evidence 貼進 `openspec/changes/asr-runtime-extraction/notes/verification.md`（手動建立）後人工確認。

- [x] 12.2 (Implementation Contract — Acceptance criteria #1 全套 test 通過) 跑全套 test：root test 命令 + `cd packages/asr-runtime && uv run pytest` + `cd packages/backend && uv run pytest`，全綠。驗證：3 套 test 都 exit code 0、無新增 skip。

- [ ] 12.3 (Scope boundaries — archive readiness；Requirement: WhisperProvider is offered alongside Qwen3 — REMOVED migration) `spectra validate asr-runtime-extraction` 通過後執行 `spectra archive`。完成行為：change 從 `openspec/changes/` 搬到 `openspec/changes/archive/2026-MM-DD-asr-runtime-extraction/`、specs 套用；驗證：`spectra list` 不再列這條 change 為 active、`openspec/specs/asr-runtime/spec.md` 存在。
