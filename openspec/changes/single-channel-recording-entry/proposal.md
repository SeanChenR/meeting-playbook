## Why

slice-12 留下一個 production-unreachable 的 code path：`audio/devices.py` 的 pre-flight 強制要求 BlackHole device（否則直接 raise + 拒絕開 session），但 `audio/capture.py` 跟 `sessions/router.py` 的 finalize 路徑其實有 single-channel（mic-only）分支可以走。結果是「只想錄自己」的場景（自言自語、工作 covering、新機器還沒裝 BlackHole、debug ASR）完全沒有 UI 入口可選。

需要在 pre-meeting 補一個顯式的 mode selector，讓使用者在 Start 之前選「Dual-channel capture（我方 + 對方）」或「Single-channel（只錄我方）」，並把選擇透通到 capture factory 跟 pre-flight 檢查 — 只有 dual mode 才驗 BlackHole。

## What Changes

- Pre-flight UI 新增 mode selector（meeting detail 頁面 `MetadataCard` 上、Start Meeting 按鈕附近），預設 `dual`；切到 `single` 時 `HeadphonesHint` 隱藏（無 echo loop 風險）。
- `StartMeetingMessage` WS frame 新增 `mode: "dual" | "single"` 欄位（保留 backwards-compat：missing → `dual`）。
- `CaptureFactory` 簽名改成 `(meeting_id, mode) → dict[Stream, AudioCaptureService]`：
  - `mode="dual"` → 同今天（BlackHole + mic 兩個 stream，BlackHole 缺則 raise `NoBlackholeDevice`）。
  - `mode="single"` → 只回 `{"me": AudioCaptureService(...)}`，**不**驗 BlackHole。
- `sessions/router.py` pre-flight 改成把 client 傳的 `mode` 帶進 factory；ASR provider 對應 single mode 時只 warmup `me_provider`，避免 `counterparty_provider` 多餘 cold-start。
- i18n parity：mode selector 字串、tooltip、`session.no_blackhole_device` 文案小幅調整（補一句「或切到 mic-only mode」），新字串同時加 `zh-TW.json` + `en.json`。

## Non-Goals

- 不動 `speaker-attribution-strategy` capability — 既有的 recording-count → `SingleChannelStrategy` 路徑會自然吃到 single-mode 產出的單一 wav。
- 不做 mode 切換在 in-meeting 期間（session start 後鎖死，要換就 end + new session）。
- 不動 device discovery / ASR provider 切換 / Settings 頁面整體 — out of scope，留給後續 change。
- 不做 `mid-session 自動 fallback`（BlackHole 突然消失就降級成 single）— 這次 user 必須顯式選；自動 fallback 是另一個 design 題目。
- 不改 offline ingest path（upload audio 的單檔模式不受 mode selector 影響）。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `meeting-session`: pre-flight 加 recording mode selection 行為；既有「Pre-flight check rejects session start when BlackHole device is missing」requirement 改成 conditional（只在 dual mode 才檢查 BlackHole）；「Session captures BlackHole and microphone as two parallel streams with independent failure domains」requirement 加 single-mode 分支（只 capture mic stream，single recording row）。

## Impact

- Affected specs: `meeting-session`（MODIFIED — 2 個既有 requirement 改寫 + 1 個 ADDED requirement 描述 mode selector 行為）
- Affected code:
  - Modified:
    - packages/backend/meeting_playbook/sessions/messages.py
    - packages/backend/meeting_playbook/sessions/router.py
    - packages/backend/meeting_playbook/sessions/dependencies.py
    - packages/backend/meeting_playbook/audio/capture.py
    - packages/web/src/hooks/use-meeting-session.ts
    - packages/web/src/lib/session-ws.ts
    - packages/web/src/components/headphones-hint.tsx
    - packages/web/src/components/metadata-card.tsx
    - packages/web/src/routes/meetings/detail.tsx
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
  - New:
    - packages/web/src/components/recording-mode-selector.tsx
    - packages/web/src/components/recording-mode-selector.test.tsx
    - packages/backend/tests/audio/test_capture_factory_single_mode.py
  - Removed: (none)
