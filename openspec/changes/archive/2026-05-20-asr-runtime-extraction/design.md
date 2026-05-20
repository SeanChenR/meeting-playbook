## Context

目前 backend (`packages/backend`) 把 Qwen3-ASR 跟 Whisper 都當成 in-process provider — 模型直接 load 進 FastAPI worker 的記憶體空間。實際運作有幾個痛點：

1. **記憶體佔用**：Qwen3-ASR-1.7B 載完約 5 GB，跟 backend 的 SQLAlchemy connection pool、async tasks、Gemini SDK 全擠在一個 process。Mac M3 Pro 18 GB 跑 vite + auth + backend + ASR + 其他 dev 工具會明顯卡。
2. **失敗連坐**：模型 load 拋 exception（最近撞到的 `Cannot copy out of meta tensor`、HuggingFace 下載中斷、MPS unavailable）會讓 backend session WebSocket 整條斷掉。session_id 跟未 flush 的 audio chunk 都丟。
3. **冷啟動雙倍成本**：backend 重啟（reload 是常態 dev workflow）= 重新 load 模型 30 秒。改一行 backend code 就要等。
4. **Whisper 維護負擔**：Sean 在這台機器跑不動 Whisper Large v3，但 codebase 仍有 `whisper_provider.py`、test fixture、settings logo、provider enum、i18n key 一整套，純粹累積死碼。

把 ASR 抽到 `packages/asr-runtime/`（獨立 FastAPI / uvicorn 服務）後：
- 模型 load 一次、long-running，backend reload 不影響。
- ASR 失敗 → runtime client 拋 `RemoteAsrRuntimeError` → backend 把它包成 `error_code: asr.runtime_unavailable` 給前端，session 可以 graceful pause 而不是斷線。
- Whisper 整條移除，減少維護面積。

## Goals / Non-Goals

**Goals:**

- ASR runtime 是獨立 process，跟 backend 透過 localhost network 通訊（不共享 Python interpreter / memory）。
- Qwen3-ASR 模型只 load 一次；backend reload 不會重 load 模型。
- ASR runtime 失敗回應有明確 error contract，不會以「整個 WebSocket 斷線」傳遞。
- backend 對 ASR 的依賴收斂在 `ASRProvider` interface 後面，現有 session router / offline ingest runner 不需要知道 runtime 是 in-process 還是 remote。
- 把 Whisper 整條移除（provider、test、frontend dropdown、i18n、PNG logo），不留 dead code。
- 新 env vars 全部寫進 `.env.example` 並有 default；root devserver script 跟著啟動 asr-runtime，沒有 manual 啟動步驟。

**Non-Goals:**

- 不評估新 ASR 模型（保留 Qwen3-ASR-1.7B；ADR-0026/VibeVoice 走另一條路）。
- 不拆分 Gemini LLM 呼叫（仍在 backend）。
- 不引入 gRPC / Protocol Buffers — 維持 JSON over WebSocket / HTTP。
- 不做 multi-tenant queueing — runtime 仍假設單一 session concurrent；佇列管控留給未來。
- 不做雲端 GPU 部署 — runtime 跑在本機 macOS MPS。
- 不寫 systemd / launchd 守護腳本 — dev/prod 都仰賴 root devserver script 即可。

## Decisions

### Decision 1 — Runtime 拆分方式：獨立 FastAPI micro-service

選擇：新 package `packages/asr-runtime/`，跑 uvicorn 在 `127.0.0.1:8100`。

理由：
- 跟現有 `packages/backend` 的 Python 技術棧一致（uv + FastAPI + structlog）→ tooling、test runner、deps 管理都複用。
- 獨立 port 讓 backend reload / restart 不影響 runtime；runtime crash 也只影響 ASR 路徑。
- 比子程序 sidecar 更乾淨：lifecycle 透過 uvicorn 自身的 reload + graceful shutdown 處理，不需要 backend 自己管 PID。
- root devserver script 已經透過 concurrently 跑多 process，加一條跟現有模式一致。

**Alternatives considered:**
- *子程序 sidecar*（backend spawn child + stdin/stdout JSON-RPC）：少一個 port 但 lifecycle 管理麻煩，healthcheck 跟 crash recovery 要自己刻。
- *Unix socket RPC*：本機快但 cross-platform 麻煩，沒有實質 throughput 差異（每 10 秒一個 chunk）。

### Decision 2 — Wire protocol：WebSocket 主、HTTP 輔

選擇：
- **realtime session**（meeting in progress） → WebSocket `/v1/transcribe/stream`，handshake 後可以連續送 audio chunk frame、收 transcript chunk frame。
- **offline ingest job** → HTTP `POST /v1/transcribe/chunk`，一個 chunk 一個 request。

理由：
- WebSocket 跟現有 `meeting-session` ws router 模式一致；frame schema 直接複用 `audio_chunk` / `transcript_chunk` JSON shape。
- HTTP 給 offline ingest，因為 ingest job 本來就是 batch、不需要 long-lived connection；一個 chunk 一個 request 失敗 retry 也乾淨。
- 兩條路在 runtime 內部走同一個 `Qwen3Runner.transcribe(audio_bytes, sample_rate_hz)` async 函式，差異只在 transport adapter。

**Alternatives considered:**
- *純 HTTP for everything*：實作簡單，但每個 chunk 一次 connection handshake 在 dual-channel 每 10 秒 ×2 stream 累積 latency 不必要。
- *gRPC bidirectional streaming*：throughput 跟 type safety 都好，但 dev/test infra 成本太高（要 generate Python + TS stubs，沒在用 protobuf）。

### Decision 3 — Backend 接 runtime 的方式：`RemoteAsrRuntimeClient` 實作 `ASRProvider`

選擇：新 class `RemoteAsrRuntimeClient(ASRProvider)`，建構時收 `runtime_url`，內部維持 long-lived `aiohttp.ClientSession` 跟可選的 WebSocket 連線。`ASRProviderFactory.create(name)` 在環境變數 `ASR_RUNTIME_URL` 有值時統一回 `RemoteAsrRuntimeClient`（name 仍是 `qwen3`，傳給 runtime 當 model selector）。

理由：
- session router / offline ingest 不需要知道 runtime 是 in-process 還是 remote — 只看 `ASRProvider` interface。
- factory 是現有 keystone（per architectural invariant），不破壞既有 plug-in 模式。
- env vars 缺值 → factory raise `AsrRuntimeUnavailableError`，session 收到後直接送 `error_code: asr.runtime_unavailable` 給前端，不嘗試 fallback to local（因為我們已經拿掉 local provider）。

**Alternatives considered:**
- *在 factory 之外 inject HTTP client*：彈性更高但繞過 ASR provider 抽象，違反 invariant「new engines plug in as new implementations」。

### Decision 4 — 移除 Whisper：硬性 breaking change + 讀取時 fallback

選擇：
- code 刪：`whisper_provider.py`、`test_whisper_provider.py`、`WhisperConfig` env vars、`ASRProvider` enum 的 `whisper` 值、`whisper.png` logo、前端 dropdown / settings card 的 Whisper 選項、i18n key `asrProvider.whisper*`。
- 資料相容：DB 裡 `meetings.asr_provider = "whisper"` 的舊資料**讀取時 fallback 成 `"qwen3"`**（在 ORM model 的 validator hook 處理），不寫 migration 強制改值（避免破壞歷史紀錄）。
- 不做 deprecation period — 個人單用戶專案，沒有外部消費者。

理由：
- Sean 機器跑 Whisper 太吃 CPU，實際幾乎不用 → 留著只是維護負擔。
- 雙引擎 dropdown 在前端佔位、tests 在 backend 拖時間。
- 讀取 fallback 比強制 migration 安全：歷史會議仍 `asr_provider = "whisper"` 在 DB 裡是事實，沒必要改寫。

**Alternatives considered:**
- *deprecation 兩個 release 再刪*：個人專案不需要這個 ceremony。
- *寫 Alembic migration 改舊資料 `whisper → qwen3`*：破壞歷史真實性；fallback 已經夠安全。

### Decision 5 — Startup warmup：opt-in via env

選擇：runtime 啟動時若 `ASR_RUNTIME_WARMUP_ON_BOOT=1`（default `1`，dev 可關），會在 uvicorn `lifespan` startup hook 跑一次 `Qwen3Runner.warmup()`（dummy 0.5 秒 silent audio 跑 inference）。runtime 處於 `loading` 狀態時 `GET /healthz` 回 `200 {"status":"loading"}`；session router 看到 `loading` 會把前端的 ASR loading dialog 維持顯示直到 `ready`。

理由：
- warm 後第一次真實 chunk 不會吃 cold-start 的 7~12 秒，session 體感平順。
- env 可關方便 unit test 跟 quick reload 場景。

### Decision 6 — 模型 `meta tensor` bug：runtime 內部直接固定為 CPU-then-MPS

選擇：`Qwen3Runner` 的 model loader 寫死 `from_pretrained(...)` 不傳 `device_map`，載完 CPU 後手動 `.to(device)`。這條路徑是 round-6 hotfix 已經驗證可繞過 accelerate dispatch 的 meta-tensor 問題。

理由：之前 in-process 版本撞過這個錯，搬到 runtime 同樣需要這個保護。

### Decision 7 — Error contract：`error_code: asr.runtime_unavailable` + retry on backend

選擇：
- runtime 對外錯誤統一回 `{ "error_code": "asr.runtime_unavailable", "message": "...", "retriable": bool }`。
- backend `RemoteAsrRuntimeClient` 收到後重 raise 同樣的 `error_code` 給 session router / offline ingest。
- realtime session：connecting phase 收到 `runtime_unavailable` → session 結束 + 前端顯示 alert；in_progress 中 chunk 失敗 → 該 chunk drop + 記 log，不斷 session。
- offline ingest：retry 3 次 with exponential backoff（2s → 4s → 8s），仍失敗就把 job 標 `failed` 並寫 `error_code` 進 job row。

## Implementation Contract

### Observable behavior

1. **ASR runtime 啟動**：root devserver script 起來時，新跑一條 `packages/asr-runtime/`；終端機 log 看得到 `asr-runtime listening on http://127.0.0.1:8100`。
2. **第一次按開始會議**（dual mode）：前端顯示 ASR loading dialog → backend 對 runtime 發 WebSocket → runtime 回 `{"type":"ready"}` → dialog 自動消失 → 開始送 audio chunk → 10 秒後回第一段 transcript。
3. **Backend 重啟（reload）**：終端機只看到 backend 的 reload log，ASR runtime 維持 `listening`，模型不重 load。從前端按開始會議，dialog 在 < 1 秒消失（runtime 已 warm）。
4. **Runtime 沒起**（手動 kill）：按開始會議 → 前端立刻收到 `error_code: asr.runtime_unavailable` toast → loading dialog 不卡住、可關。
5. **Whisper provider 完全消失**：grep `whisper` 在 packages/backend, packages/web, openspec/specs 全 0 hit（除了 archive 跟 git history）；settings preferences card 只剩 Qwen3 logo + label；meeting detail dropdown 只有一個選項（仍是 dropdown shape，待未來新引擎加入）。

### Interfaces / data shapes

- **WebSocket `/v1/transcribe/stream`** —
  - Client → server: `{"type": "config", "sample_rate_hz": 16000, "language_hint": "zh"}` 一次性 handshake；後續 `{"type": "audio_chunk", "audio_bytes_b64": "...", "sequence": N}`。
  - Server → client: `{"type": "ready"}` 一次（model warm 完）；後續 `{"type": "transcript_chunk", "sequence": N, "text": "...", "started_at": "ISO8601", "ended_at": "ISO8601"}`；錯誤時 `{"type": "error", "error_code": "asr.runtime_unavailable", "message": "...", "retriable": bool}` 然後 server-side close frame。

- **HTTP `POST /v1/transcribe/chunk`** —
  - Request body: `{"audio_bytes_b64": "...", "sample_rate_hz": 16000, "language_hint": "zh" | null}`
  - Response 200: `{"text": "...", "started_at": "ISO8601", "ended_at": "ISO8601"}`
  - Response 4xx/5xx: `{"error_code": "asr.runtime_unavailable", "message": "...", "retriable": bool}`

- **HTTP `GET /healthz`** — `{"status": "loading" | "ready" | "error", "model_repo": "Qwen/Qwen3-ASR-1.7B", "device": "mps" | "cpu", "uptime_seconds": int}`

- **Backend interface（不變，但實作換）**：`ASRProvider.transcribe_chunk(audio_bytes, sample_rate_hz, language_hint) → TranscriptChunk` 仍是唯一進入點；`RemoteAsrRuntimeClient` 實作這個。

- **New env vars in `.env.example`**：
  - `ASR_RUNTIME_URL=http://127.0.0.1:8100`
  - `ASR_RUNTIME_PORT=8100`
  - `ASR_RUNTIME_DEVICE=mps`
  - `ASR_RUNTIME_MODEL_REPO=Qwen/Qwen3-ASR-1.7B`
  - `ASR_RUNTIME_WARMUP_ON_BOOT=1`

### Failure modes

- runtime 沒起：backend factory raise `AsrRuntimeUnavailableError` → session router 把它包成 WebSocket close + `error_code: asr.runtime_unavailable`。
- chunk 中失敗（model crash）：runtime 回 `error_code: asr.runtime_unavailable, retriable: false`；backend 把該 chunk drop、寫 log、不斷 session。
- offline ingest 失敗：backend 自帶 3 次 exponential backoff，仍失敗則把 ingest job row 標 `status=failed`、`error_code=asr.runtime_unavailable`。
- model warmup 失敗：runtime `/healthz` 回 `{"status": "error"}`；backend session 嘗試開啟時收到立即 error，不會走進 in_progress phase。
- 既有資料 `asr_provider="whisper"`：ORM validator hook fallback 成 `qwen3`；前端不會看到 whisper option。

### Acceptance criteria

1. `bun run test` 全部測試通過（包含新的 `tests/asr/test_remote_runtime_client.py` 跟 `packages/asr-runtime/tests/`）。
2. `grep -r whisper packages/backend packages/web` 排除 archive / git log 後零命中。
3. `.env.example` 包含 5 個新 env var，每個都有 default value。
4. 手動驗證流程：
   a. root devserver script 啟動，三條 + 一條 asr-runtime 都 listening。
   b. 開 meeting detail，按開始會議（dual mode），ASR loading dialog 出現後 < 5 秒消失（warmup 已完成的情況）。
   c. 講話 10 秒後逐字稿欄出現第一段 transcript chunk。
   d. `kill` asr-runtime process 後再按開始會議，前端 toast 顯示「ASR 引擎未啟動」之類訊息，session 不卡住。
   e. Settings preferences card 只有一張 Qwen3 卡，無 Whisper。
5. backend reload（編輯 backend 任一檔）後第一次開始會議，dialog 出現後 < 1 秒消失。

### Scope boundaries

**In scope:**
- 新 `packages/asr-runtime/` micro-service（uvicorn + FastAPI + Qwen3Runner）。
- 新 `RemoteAsrRuntimeClient` in backend。
- 移除 Whisper 全套（provider、test、frontend dropdown 選項、i18n、PNG logo）。
- `.env.example`、root devserver script、README、ADR-0027 更新。
- `meeting-session` 跟 `offline-ingest` 路徑改走 remote client。

**Out of scope:**
- 不動 Gemini Flash advisor / Gemini 2.5 Pro summary 任何 LLM 呼叫。
- 不調整 audio capture pipeline（sounddevice + BlackHole 不變）。
- 不寫 launchd / systemd daemon — runtime 仍由 root devserver script 啟動。
- 不重構 `meeting-session` WebSocket 協定本身（只在 backend 內部換 provider）。
- 不評估 / 不整合新的 ASR 模型。

## Risks / Trade-offs

- **[Risk] Runtime 多一個 port 要管** → Mitigation: root devserver script 用 concurrently 自動拉起；`.env.example` 寫明 default port；`spectra-apply` task 包含 README 寫明 `ASR_RUNTIME_PORT` 衝突時怎麼改。
- **[Risk] WebSocket 雙重 hop 增加延遲** → Mitigation: runtime 跟 backend 跑在 localhost；asyncio 直通；實測 chunk-to-chunk 應 < 20 ms overhead，相對 model inference 的 1~3 秒幾乎不可見。
- **[Risk] Whisper 移除後若 Qwen3 出現嚴重 bug 無備援** → Mitigation: 可接受 risk（單用戶、Qwen3 已是 daily driver）；最壞情況 git revert 該 commit。
- **[Risk] runtime crash 沒有自動 restart** → Mitigation: dev 走 uvicorn `--reload`；prod 仍由 root devserver script 拉起，crash 後 concurrently 顯眼地停掉整組（Sean 會手動重起）。docs/adr/0027 註明這個限制。
- **[Risk] 多個 backend worker 同時打 runtime** → Mitigation: 目前 backend 仍是單 worker；runtime 內部 `Qwen3Runner` 用 asyncio.Lock 串行；如果未來 backend 開 multiple worker，需要排隊或 horizontal scale runtime — 暫不在 scope 內。
- **[Risk] ADR-0027 跟既有 ADR-0026 (VibeVoice) 衝突** → Mitigation: 在 ADR-0027 explicitly 寫「VibeVoice 若採用，會新增另一個 runtime instance；不取代 Qwen3 runtime」。
