## Why

Slice-06 起，dual-channel session 把 BlackHole（對方 / system audio）跟 microphone（我方）**分成兩個獨立 mono WAV 檔**（`{recordings_dir}/{meeting_id}/{counterparty|me}.wav`）。Backend `audio-playback` capability 提供 per-recording range-aware streaming endpoint，但 `<MeetingAudioMiniPlayer>` 的 `pickMeetingRecording()` **只挑 `stream === "me"` 那筆**，導致：

- 任何 dual-channel meeting 在 detail 頁按播放 → 只聽得到「**我方**」說的話，**對方完全靜音**
- 從 Sean 的 use case 看，meeting 回顧主要是想聽**對方**講什麼（重點客戶反饋、決策邏輯），player 卻把對方那邊整段切掉 —— UX 嚴重斷裂

Single-channel meeting（mic-only — 目前 capture 強制 BlackHole 所以實際 unreachable，等 S27 補入口）沒這個問題，因為 `pickMeetingRecording` 對單 recording 直接挑那一筆。

## What Changes

- **Backend：server-side mix 新 endpoint**
  - `GET /api/meetings/{id}/recordings/mixed/audio?start=...&end=...` 跟現有 per-recording endpoint 同 contract（mono WAV 16 kHz 16-bit、HTTP Range-aware、`AUDIO_RANGE_MAX_BYTES` cap）
  - 第一次 range request 觸發 lazy mix：讀 `me.wav` + `counterparty.wav` → sample-by-sample 平均（`mixed_n = clamp((me_n + counterparty_n) / 2, INT16_MIN, INT16_MAX)`）→ 寫進 `{recordings_dir}/{meeting_id}/mixed.wav`（mono 16 kHz 16-bit）→ 後續 range request 直接讀 cached 檔
  - Single-channel meeting 沒這 endpoint（404 `recording.mixed_not_applicable`）—— 只有一個 stream 不需要 mix
  - 退化情境：兩個 stream 長度不一致時，**短的那邊 zero-pad**（per design D2）；總長度 = `max(len(me), len(counterparty))`
- **Backend：WAV mix helper module**
  - 新模組 `meeting_playbook/audio_playback/mixer.py`：純函式 `mix_pcm_int16(left: bytes, right: bytes) -> bytes` 跟編排 helper `ensure_mixed_wav(meeting_id, recordings_dir) -> Path`（idempotent — 已存在就直接 return）
  - 既有 `wav_header.parse_wav_header` 行為**不變**（仍然只接受 mono 16 kHz 16-bit）—— mix 後輸出仍是 mono，header 校驗共用
- **Frontend：mini-player source toggle**
  - `<MeetingAudioMiniPlayer>` 新增 source toggle：`mixed | me | counterparty` 三選一（dual-channel 時三個都可選；single-channel 時整個 toggle 隱藏）
  - **預設改成 `mixed`**（dual-channel meeting）—— 修 bug 的核心路徑就是這條
  - Toggle 切換時 `<audio>` `src` 換到對應 endpoint，`currentTime` 保留（per design D5），`playbackRate` / `play` 狀態保留
  - User 選擇透過 `localStorage.miniPlayerSource` 跨 page-reload 持久化（同 `miniPlayerRate` 機制）
- **Frontend：`pickMeetingRecording` 升級**
  - 既有 dual-channel 路徑「挑 `stream === "me"`」改成「回 `{ source: "mixed", url: /api/.../recordings/mixed/audio, ... }`」當預設；toggle UI 切到 me / counterparty 時用對應 `recording.id`
  - Single-channel 路徑 不變

## Non-Goals

- **不做 client-side mix**：client mix 需要兩個 `<audio>` element + Web Audio API 同步 + scrubbing 排程，複雜度遠高於 server-side 一次 mix；前端 toggle UI 只是切 URL，不引入 Web Audio API
- **不做 stereo (L/R) 輸出**：mix 後仍是 mono —— stereo 在 player 上把 me 跟 counterparty 分流到左右耳，用單耳會聽不到一邊（這就是 Sean 一開始懷疑的 UX）；mono 平均對「想聽完整對話」場景最直覺
- **不改 `parse_wav_header` 接受 stereo**：mix output 仍 mono，既有 「Stereo file is rejected」 scenario 行為不變
- **不做 mix 的個別音量平衡 / ducking**：兩邊 50/50 平均；對方音量過小 / 我方麥太大這類 user-perceived 失衡留給未來 slice（需要 audio analysis）
- **不前端 fallback 到 me-only 當 mixed endpoint 失敗**：mix 失敗（disk 滿、wav 壞）是 backend 500 / 422，前端顯示 localized error，不靜默 swap source —— 否則 user 不會知道對方聲音其實沒在播
- **不改 retention sweep**：cached `mixed.wav` 跟既有 `me.wav` / `counterparty.wav` 共用同 30 天 retention window（retention job sweep `{meeting_id}/` 整個目錄），不另外加 TTL
- **不做單聲道 finalize 路徑 UI 入口**：那是 S27 範圍，本 slice 只動 dual-channel 既有 path
- **不引入 background pre-warm**：mix 是 lazy（first range request 觸發），不在 finalize 時 pre-compute —— 避免動 sessions/router.py finalize 邏輯、scope 控小
- **不改 transcript chunk 對應的 `?start=&end=` slicing 語意**：chunk-level 「play this chunk」按鈕走的還是 me-stream timeline（chunk `started_at` 來自 BlackHole / mic chunking 邏輯，跟 mixed timeline 等長），所以切到 mixed 後 chunk slice 仍能對應到正確的時間區段

## Capabilities

### New Capabilities

(none — 整個變更 fold 進既有 `audio-playback`)

### Modified Capabilities

- `audio-playback`：新加 mixed-stream endpoint requirement + mix algorithm requirement + mini-player source-toggle requirement；既有 `MeetingAudioMiniPlayer is a sticky bottom control bar...` requirement 從「dual-channel meetings → recording with `stream === "me"`」改成「dual-channel meetings → mixed source by default; user-overridable via toggle」

## Impact

- Affected specs: audio-playback
- Affected code:
  - New:
    - packages/backend/meeting_playbook/audio_playback/mixer.py
    - packages/backend/tests/audio_playback/test_mixer.py
    - packages/backend/tests/audio_playback/test_router_mixed.py
  - Modified:
    - packages/backend/meeting_playbook/audio_playback/router.py
    - packages/web/src/components/meeting-audio-mini-player.tsx
    - packages/web/src/components/meeting-audio-mini-player.test.tsx
    - packages/web/src/hooks/use-mini-player.ts
    - packages/web/src/lib/meetings-api.ts
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
  - Removed: (none)
