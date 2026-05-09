- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/8
- Agent Brief：https://github.com/SeanChenR/meeting-playbook/issues/8#issuecomment-4386426530

## Why

Slice 5 把「會前」全部串完（Calendar 一鍵 → LLM 生 playbook 草稿 → 編輯器）。下一塊價值是「**會中**」：使用者按下「開始會議」，就能在 detail 頁右側看到自己講話被即時轉錄（10 秒一個 chunk，逐段出現）。這也把整條 `audio → ASR → WebSocket → React reducer → UI` 的管線立起來，後續 Slice 7（BlackHole 第二聲道）+ Slice 8（tactical advisor 吃 transcript stream）+ Slice 12（VibeVoice 替換 ASR provider）全都掛在這個基礎上。

本 slice 故意只做麥克風單聲道，不碰 BlackHole — 先把整條 pipe 跑通，BlackHole 再加。

## What Changes

- Alembic 兩張新表：
  - `transcript_chunk`（id, meeting_id, speaker, text, started_at, ended_at, asr_provider_used, confidence nullable）— `speaker` 本 slice 全部 `"me"`，欄位形狀已支援 `"counterparty"` 給 Slice 7
  - `recording`（id, meeting_id, stream, file_path, bytes, created_at）— `stream` 本 slice 全部 `"me"`
- 後端新增 `ASRProvider` 介面（per ADR-0005）— 抽象契約：`transcribe_chunk(audio_bytes, language_hint?) -> TranscriptChunk`、`name` 識別字串
- `WhisperProvider`（first impl）— 用 `faster-whisper` `large-v3-turbo`，lazy-load（首次呼叫才載入模型，~1.5GB）
- `AudioCaptureService` deep module — 用 `sounddevice` 從預設系統麥克風抓音訊；負責 device discovery、chunk buffering（~10 秒）、WAV 寫檔到 `{RECORDINGS_DIR}/{meeting_id}/me.wav`；30 秒 silence 偵測（RMS 低於門檻 → 觸發 warning event）
- FastAPI WebSocket endpoint `GET /api/meetings/{id}/session`：透過 Bun gateway proxy 升級（保留 `X-User-Id` header），ownership gate 透過 `MeetingRepository.get_for_user`
- WebSocket 訊息契約（JSON, type-tagged）：
  - client → server：`start_meeting {meeting_id}`、`end_meeting {meeting_id}`
  - server → client：`meeting_started {meeting_id}`、`transcript_chunk {meeting_id, speaker, text, started_at, ended_at, asr_provider_used, confidence?}`、`silence_warning {meeting_id, since}`、`meeting_ended {meeting_id}`、`error {error_code, message}`
- meeting status 真正開始用：`scheduled → in_progress`（按下 Start）→ `completed`（按下 End），由 `MeetingRepository.transition_status` 統一寫入
- React 新增 `useMeetingSession(meetingId)` deep hook — 內含 useReducer 管 WS lifecycle + transcript chunks + silence warning state + connection retry（單次 backoff，超過放棄）
- React 新增 `TranscriptPane` 元件 — 按時間排序顯示 chunk，每段標 `me_display_name`（從 meeting 資料拿，slice-05 已正確填入）；視覺上預留 counterparty 樣式（slice-07 會用到）
- Detail 頁加 **「開始會議」/「結束會議」** 按鈕、capture indicator（脈動的小點）、silence warning UI
- Bun gateway 處理 WebSocket upgrade：偵測 `Upgrade: websocket`、驗證 session、proxy 到 FastAPI 並保留 `X-User-Id`（既有 `isWebSocketUpgrade` helper 已備好；本 slice 補 spec）
- 新環境變數：`RECORDINGS_DIR`（預設 `~/MeetingPlaybook/recordings`）、`WHISPER_MODEL_SIZE`（預設 `large-v3-turbo`）、`WHISPER_DEVICE`（預設 `auto`）、`WHISPER_COMPUTE_TYPE`（預設 `auto`）
- i18n keys 雙語齊備（`meeting.session.*`、`errors.session.*`）

## Non-Goals

- BlackHole / 對方聲道 — Slice 7
- Speaker diarization 單聲道內分人 — 不做，speaker 由 stream 決定
- Tactical advisor — Slice 8
- 後會議 summary — Slice 10
- VibeVoice ASR provider — Slice 12
- Recording 自動清理 / TTL — Slice 13
- 會中編輯 playbook — Slice 8
- 瀏覽器關掉 / reconnect / replay — 關掉 tab 等於結束 session（不存 client-side state）
- 多裝置同步 — 一個 meeting 同時間只能有一個 session
- 模型自動下載到位 — 使用者第一次跑 dev 時 faster-whisper 會自動拉模型（README 提示），不在這 slice 寫下載 UX

## Capabilities

### New Capabilities

- `meeting-session`: 會中 session 的完整生命週期 — WS endpoint 契約、`ASRProvider` 介面、`WhisperProvider` 實作、`AudioCaptureService` deep module、`transcript_chunk` + `recording` 兩張表的 schema 與寫入路徑、5 種 server→client + 2 種 client→server WS 訊息契約、silence 偵測、meeting status 轉換（scheduled → in_progress → completed）

### Modified Capabilities

- `auth-gateway-contract`: 新增 WebSocket upgrade 處理 — gateway 接到 `/api/*` 帶 `Upgrade: websocket` header 時，先驗 session 再 proxy 到 FastAPI 並保留 `X-User-Id`；upgrade frame relay 與 close handshake 的契約
- `meeting-management`: meeting status 轉換 — 按下 Start Meeting 將 status 從 `scheduled` 推進到 `in_progress`（只允許一次轉換、目標必須是當前的下一個），按下 End Meeting 推進到 `completed`；新增 `MeetingRepository.transition_status(meeting_id, from, to)` 作為唯一寫入路徑

## Impact

- 後端新檔：
  - `packages/backend/alembic/versions/0003_create_session_tables.py`（transcript_chunk + recording）
  - `packages/backend/meeting_playbook/sessions/__init__.py`
  - `packages/backend/meeting_playbook/sessions/router.py`（WS endpoint）
  - `packages/backend/meeting_playbook/sessions/service.py`（session orchestration — 開 capture、串 ASR、發 WS frame、寫 DB）
  - `packages/backend/meeting_playbook/sessions/messages.py`（Pydantic WS message types）
  - `packages/backend/meeting_playbook/sessions/repository.py`（transcript_chunk + recording 寫入）
  - `packages/backend/meeting_playbook/sessions/models.py`（SQLAlchemy）
  - `packages/backend/meeting_playbook/audio/__init__.py`
  - `packages/backend/meeting_playbook/audio/capture.py`（AudioCaptureService — sounddevice 包裝、chunk buffer、WAV writer、silence 偵測）
  - `packages/backend/meeting_playbook/asr/__init__.py`
  - `packages/backend/meeting_playbook/asr/base.py`（ASRProvider Protocol + TranscriptChunk dataclass）
  - `packages/backend/meeting_playbook/asr/whisper_provider.py`（WhisperProvider — faster-whisper 包裝）
  - `packages/backend/tests/sessions/test_router.py`（WS endpoint 整合測試 + ownership gate）
  - `packages/backend/tests/sessions/test_service.py`（service orchestration 用 mock ASR + mock capture）
  - `packages/backend/tests/sessions/test_repository.py`
  - `packages/backend/tests/audio/test_capture.py`（device-guarded 整合測試）
  - `packages/backend/tests/audio/fixtures/short_speech.wav`（< 5 秒中文語音素材）
  - `packages/backend/tests/asr/test_whisper_provider.py`（real audio fixture，model load 慢但只跑一次）
- 後端新依賴：`faster-whisper`、`sounddevice`、`numpy`（faster-whisper 自帶但明示）
- 後端修改：
  - `packages/backend/pyproject.toml`（新依賴）
  - `packages/backend/meeting_playbook/server.py`（mount sessions router）
  - `packages/backend/meeting_playbook/config.py`（新增 RECORDINGS_DIR + WHISPER_* 設定）
  - `packages/backend/meeting_playbook/meetings/repository.py`（新增 `transition_status`）
  - `packages/backend/meeting_playbook/meetings/router.py`（如有需要對外暴露 status 轉換的 wrapper；目前只在 session router 內呼叫）
  - `packages/backend/tests/conftest.py`（補 transcript_chunk + recording TRUNCATE）
  - `packages/backend/tests/meetings/test_repository.py`（補 transition_status 測試）
- Auth gateway 修改：
  - `packages/auth/src/server.ts`（WebSocket upgrade 路徑 — 既有 isWebSocketUpgrade 會走 fetch proxy；本 slice 確認 X-User-Id + 三個 identity headers 在 upgrade 也都會帶；補 spec 要求的 close handshake 行為）
  - `packages/auth/src/__tests__/gateway-websocket.test.ts`（新檔 — assert WS upgrade 帶 X-User-Id；公開路徑不應被升級）
- 前端新檔：
  - `packages/web/src/lib/session-ws.ts`（WebSocket client 包裝 — open / send / close / 訊息解析 + 型別）
  - `packages/web/src/lib/session-ws.test.ts`
  - `packages/web/src/hooks/use-meeting-session.ts`（useReducer-based hook）
  - `packages/web/src/hooks/use-meeting-session.test.tsx`（mock WebSocket，驗 reducer 狀態轉換）
  - `packages/web/src/components/transcript-pane.tsx`
  - `packages/web/src/components/transcript-pane.test.tsx`
  - `packages/web/src/components/capture-indicator.tsx`
  - `packages/web/src/components/capture-indicator.test.tsx`
- 前端修改：
  - `packages/web/src/routes/meetings/detail.tsx`（加 Start/End 按鈕、嵌 TranscriptPane + CaptureIndicator、串接 useMeetingSession）
  - `packages/web/src/routes/meetings/detail.test.tsx`（新增 session 互動測試）
  - `packages/web/src/locales/zh-TW.json`、`packages/web/src/locales/en.json`、`packages/web/src/locales/locales.test.ts`
- 環境：
  - `.env.example` 新增 `RECORDINGS_DIR`、`WHISPER_MODEL_SIZE`、`WHISPER_DEVICE`、`WHISPER_COMPUTE_TYPE`
- 不動：所有 Calendar / playbook generation 模組、auth Better Auth 設定、其他 ASR provider
