## Context

slice-12 archive 完成後留下一個 production-unreachable 的 code path：

- `packages/backend/meeting_playbook/sessions/dependencies.py::_default_capture_factory()` 對所有 session 呼叫 `find_blackhole_device(...)`，缺 BlackHole 直接 `raise NoBlackholeDevice`，router 將其轉成 `session.no_blackhole_device` error frame 並關閉 WS。
- 但 `packages/backend/meeting_playbook/audio/capture.py::AudioCaptureService` 透過 `stream_label="me" | "counterparty"` 與 `wav_path` 已具備獨立 stream 能力；`packages/backend/meeting_playbook/sessions/router.py` 的 finalize loop（`for stream_label, cap in captures.items()`）也支援任意 stream 數量，speaker-attribution-strategy 的 `select_strategy` 又會根據 wav 檔數量自動挑 `SingleChannelStrategy`。

換句話說：single-channel（mic-only）finalize / attribution / playback 都跑得通 — 唯獨**沒有 UI 入口**讓使用者選。需求場景：

1. 自言自語、工作 covering（不需要對方音）
2. 新 macbook 還沒裝 BlackHole
3. Debug / 測試 ASR 行為

本 change 的範圍是把 mode selector 接上 pre-flight，並把 `mode` 透通到 capture factory 與 ASR provider warmup。Spec 屬於既有 `meeting-session` capability 的 MODIFIED 行為（pre-flight 條件鬆綁 + capture 行為加 single-mode 分支）+ 1 個 ADDED 行為（client mode field + selector contract）。

## Goals / Non-Goals

**Goals:**

- 使用者在 pre-meeting 階段顯式選擇 `dual` 或 `single` recording mode。
- `single` mode 下：pre-flight 不檢查 BlackHole；capture factory 只開 mic stream；ASR provider 只 warmup `me`；finalize 只寫一個 recording row（`stream="me"`）；既有的 `SingleChannelStrategy` 路徑自然被 `select_strategy` 觸發。
- `dual` mode 行為與今天完全一致（zero regression）。
- WS frame 加 `mode` 欄位向後相容：缺 `mode` 視為 `dual`（match 既有 client 行為，避免 mid-deploy 中斷）。
- i18n parity 維持：所有新 user-visible 字串同時加 `zh-TW.json` + `en.json`，CI 的 `locales.test.ts` deep-equal 通過。

**Non-Goals:**

- 不動 `speaker-attribution-strategy` capability — 它已經根據 recording 檔數量分流。
- 不做 in-meeting mode 切換（必須 end + new session）。
- 不做 mid-session 自動降級（dual → single 當 BlackHole 中途失聯）。
- 不動 device discovery / `BLACKHOLE_DEVICE_NAME` env 解析。
- 不動 ASR provider 選擇邏輯（`get_asr_providers_for_meeting` 還是回兩個 provider，但 single mode 只 warmup + 使用其中一個）。
- 不動 offline ingest path（`/api/meetings/{id}/upload_audio` 沒有 mode 概念，本來就是單檔）。
- 不動 Settings 頁面 / 不在 Settings 加全域預設（per-session UI 選擇即可，避免擴大範圍）。

## Decisions

### D1：Mode 預設值是 `dual`

新建 meeting 進入 detail 頁面、`status === "scheduled"`、selector 第一次出現時，預設選擇 `dual`。原因：

- 現存使用者體驗（dual）零退化。
- 大多數 meeting（calendar import）天然就是雙人對談，dual 是正解。
- single 屬於 explicit opt-in（自言自語、debug），值得多按一次。

**Alternative considered**: 用「BlackHole 偵測結果」決定預設 — 若偵測不到 BlackHole 就預設 single。否決：偵測會把 selector 變成 dynamic state，與 spec 「pre-flight 在 start 後才跑」的順序衝突；且設備臨時拔掉/插入會讓 default 飄動，UX 反而困惑。

### D2：Mode 欄位的 wire contract — `mode: "dual" | "single"`，缺欄位 → `dual`

`StartMeetingMessage` 加 `mode: Literal["dual", "single"] = "dual"`（Pydantic default）；frontend `StartMeetingMessage` type 加 `mode: "dual" | "single"`。Backend 接收時 `mode` 缺欄位 fallback 到 `"dual"` 保持向後相容（部署半途的舊 client 不會壞）。

**Alternative considered**: enum 用 `"with-counterparty" | "mic-only"`。否決：domain glossary 用 `dual-channel capture` / `single-channel`，wire 也跟著用 `dual` / `single` 更一致；selector UI 顯示文案用 i18n 翻成自然語（「我方 + 對方」/「只錄我方」）。

**Alternative considered**: `dual_channel: boolean`。否決：boolean 後續想加第三種 mode（例如 system-audio-only）就要 breaking change。enum 留空間。

### D3：Pre-flight BlackHole 檢查改成 conditional — 僅 `dual` mode 才驗

`_default_capture_factory.make(meeting_id, mode)`：

- `mode == "dual"` → 不變：`find_blackhole_device(...)`, `None` 則 raise `NoBlackholeDevice`。
- `mode == "single"` → 完全不呼叫 `find_blackhole_device`；只解析 mic device，回 `{"me": AudioCaptureService(...)}` 一個 entry。

`MicDeviceNotFound` 兩個 mode 都會 raise（mic 在兩個 mode 都必要），router 仍轉 `session.no_audio_device`。

**Alternative considered**: factory 簽名不變，BlackHole 失敗時改回 single mode（隱式降級）。否決：使用者沒選 single 卻拿到 single recording，違反「explicit > implicit」；錄完才發現少對方音很傷。

### D4：ASR provider warmup 在 single mode 只 warmup `me_provider`

`sessions/router.py` 的 warmup 區段改為依 mode 選 providers：

- `dual` → `asyncio.gather(me_provider.warmup(), counterparty_provider.warmup())`（不變）
- `single` → `await me_provider.warmup()` 只跑一個

`providers` dict 在 single mode 也只放 `{"me": me_provider}`，與 `captures` 的 keyset 對齊（`SessionService` 已用 dict 抽象，不需改）。

**Alternative considered**: 兩個 mode 都 warmup 兩個 provider（簡化 code path）。否決：cold-start 10–25s × 2 是真實成本（faster-whisper / Qwen3-ASR 都要 load model），多花 GPU/MPS 記憶體沒道理；測試 ASR 場景對快速啟動很敏感。

### D5：Mode 在 session start 後 immutable

Selector 在 `meeting.status === "scheduled"` 顯示，`in_progress` 或 `completed` 隱藏（或 read-only 顯示已用 mode — 看 D6）。送出 `start_meeting` 後 client 不再傳 mode 變更 frame，backend 也不接受。要切 mode 必須 end + 新 session。

**Alternative considered**: 中途加上 BlackHole stream（dual → single 反向不可能，因為錄到一半才加 stream 會破壞 timeline）。否決：複雜度爆炸，本 change 範圍守不住。

### D6：Selector 元件擺 `MetadataCard` 內、Start Meeting button 上方

新元件 `packages/web/src/components/recording-mode-selector.tsx`：shadcn `<RadioGroup>` + 兩個 `<RadioGroupItem>`（dual / single），附 i18n label + 一行 helper text。`MetadataCard` 透過 props 接收 `mode` 與 `onModeChange`，在 `meeting.status === "scheduled"` 時 render selector，否則隱藏。`HeadphonesHint` 改成只在 `mode === "dual" && status === "scheduled"` 顯示（single mode 無 echo loop 風險）。

**Alternative considered**: 放在 Start Meeting 按鈕的 dropdown（「Start ▾」展開兩個 mode）。否決：dropdown 把 mode 變成「按鈕的附屬選項」，UX 較隱晦；明確 radio group 一眼看到目前的設定。

**Alternative considered**: 新開 Modal 在按 Start 後彈出選 mode。否決：多一次 click，破壞既有 Start → 立即錄音的節奏。

### D7：State 放 `useMeetingSession` hook，與 session lifecycle 同生死

`useMeetingSession` 加 `mode: "dual" | "single"`（reducer state）與 `setMode(mode)` action。`start()` 把當前 mode 帶進 `start_meeting` frame。session end 後 mode reset 為預設值（D1）。Mode 不持久化到 server / localStorage — 每個 session 獨立決定，避免「上次選 single 這次忘了切回 dual 結果錄錯」。

**Alternative considered**: 在 `MetadataCard` 自己持有 `useState`。否決：start frame 在 hook 內送出，hook 需要讀到 mode；把 state 留在 component 然後 prop drill 進 hook 反而散落。

### D8：i18n keys 命名

- `meetings.session.recordingMode.label` — selector aria-label / 標題
- `meetings.session.recordingMode.dual` — radio label「雙聲道擷取（我方 + 對方）」/「Dual-channel (Me + Counterparty)」
- `meetings.session.recordingMode.single` — radio label「只錄我方」/「Mic only (Me)」
- `meetings.session.recordingMode.dualHelper` — 一行說明「需要 BlackHole 路由系統聲音」/「Requires BlackHole to route system audio」
- `meetings.session.recordingMode.singleHelper` — 一行說明「不會錄到對方聲音；適合自言自語或測試」/「Counterparty audio will not be captured; useful for solo recording or testing」
- `errors.session.no_blackhole_device` 既有字串擴充一句：「或將模式切換為『只錄我方』」/「or switch to 'Mic only' mode」

### D9：Backend test seam — capture factory 傳 mode

`tests/sessions/test_router.py` 既有 fixture `_FakeCaptureFactory` 已是 `Callable[[str], dict[...]]`；本 change 把簽名改成 `Callable[[str, Literal["dual", "single"]], dict[...]]`，現有測試會自動接住新參數（傳 dual）。新測試檔 `tests/audio/test_capture_factory_single_mode.py` 驗 single mode 不呼叫 `find_blackhole_device`、回 1 entry dict、key 是 `"me"`。

## Implementation Contract

#### Behavior

End-user observable behavior：

- 進 `/meetings/<id>` 頁面，`status === "scheduled"` 時看到 Recording Mode selector（radio group），預設 Dual。
- 切到 Single → `HeadphonesHint` 消失。
- 按 Start：dual 模式行為今天 = 今天；single 模式即使沒裝 BlackHole 也能成功進入 `in_progress`、產生一個 `me.wav` 與一筆 `recording` row、speaker attribution 走 single-channel cluster 路徑、finalize 進 `completed`。
- session 結束後新 session 預設回到 Dual（mode 不持久化）。

#### Interface / Data Shape

**WS client → server frame**（既有 `StartMeetingMessage`）：

```json
{ "type": "start_meeting", "meeting_id": "m_abc", "mode": "dual" }
```

- `mode`: `"dual" | "single"`，缺欄位視為 `"dual"`。

**Backend Pydantic 模型**（`packages/backend/meeting_playbook/sessions/messages.py`）：

```python
class StartMeetingMessage(BaseModel):
    type: Literal["start_meeting"] = "start_meeting"
    meeting_id: str
    mode: Literal["dual", "single"] = "dual"
    model_config = {"extra": "forbid"}
```

**Capture factory 簽名**（`packages/backend/meeting_playbook/sessions/dependencies.py`）：

```python
RecordingMode = Literal["dual", "single"]
CaptureFactory = Callable[[str, RecordingMode], dict[Stream, AudioCaptureService]]
```

`mode == "single"` → 回傳 dict 只包含 `"me"` 一個 entry，且 factory **不**呼叫 `find_blackhole_device`。

**Frontend types**（`packages/web/src/lib/session-ws.ts`）：

```ts
export type RecordingMode = "dual" | "single";
export type StartMeetingMessage = {
  type: "start_meeting";
  meeting_id: string;
  mode: RecordingMode;
};
```

**Hook API**（`packages/web/src/hooks/use-meeting-session.ts`）：新增 `state.mode: RecordingMode` 與 `setMode(mode: RecordingMode): void`；`start()` 用當前 `state.mode`。

**Component**（`packages/web/src/components/recording-mode-selector.tsx`）：

```ts
interface RecordingModeSelectorProps {
  value: RecordingMode;
  onChange: (mode: RecordingMode) => void;
  disabled?: boolean;
}
```

#### Failure Modes

- `mode === "dual"` 且 BlackHole 缺 → server emit `session.no_blackhole_device`（既有錯誤；i18n 文案補一句提示可切 single）；status 留在 `scheduled`。
- `mode === "single"` 且 mic 缺（`MIC_DEVICE_NAME` 設了卻找不到，或系統無 default input）→ server emit `session.no_audio_device`；status 留在 `scheduled`。
- `mode === "single"` 且 BlackHole 也缺 → **不**檢查 BlackHole，所以走不到 `no_blackhole_device`；session 正常啟動。
- ASR warmup 失敗（任一 mode、任一 provider）→ server emit `session.stream_failed_at_start`；status 從 `in_progress` 轉回 `completed`（既有行為）。
- 未知 `mode` 值（不是 `"dual"` 也不是 `"single"`）→ Pydantic ValidationError → router emit `session.unknown_message`（既有 invalid first message 行為）。

#### Acceptance Criteria

- `packages/backend/tests/audio/test_capture_factory_single_mode.py`：
  - test 1：`mode="single"` 不呼叫 `find_blackhole_device`（用 mock 驗證 call_count == 0）。
  - test 2：`mode="single"` 回傳 dict 只有 `{"me"}`，`stream_label == "me"`。
  - test 3：`mode="single"` 即使 `BLACKHOLE_DEVICE_NAME` 設為亂值也能成功 build。
  - test 4：`mode="dual"` 行為不變（regression）。
- `packages/backend/tests/sessions/test_router.py` 新增 case：client send `start_meeting` with `mode="single"` → server 不檢查 BlackHole、發 `meeting_started`、finalize 產生 1 個 recording row（`stream="me"`）。
- `packages/backend/tests/sessions/test_messages.py` 新增 case：`parse_client_message` 接受 `{"type":"start_meeting", "meeting_id":"x"}`（缺 `mode`）並 default 到 `"dual"`；接受 `{"type":"start_meeting", "meeting_id":"x", "mode":"single"}`；拒絕 `mode="invalid"`。
- `packages/web/src/components/recording-mode-selector.test.tsx`：渲染兩個 radio、切換時呼叫 `onChange`、`disabled` 時 radio readonly。
- `packages/web/src/hooks/use-meeting-session.test.tsx` 新增 case：`setMode("single")` 後 `start()` 送出 frame 帶 `mode: "single"`。
- `packages/web/src/routes/meetings/detail.test.tsx` 新增 case：mode === single 時 `HeadphonesHint` 不渲染。
- `packages/web/src/locales/locales.test.ts` deep-equal 通過（新 keys 兩個 locale 都有）。
- 手動驗：拔掉 BlackHole device → 切到 single → Start → 看到 `me.wav` 生成、`recording` row 入庫、attribution 走 cluster 路徑。

#### Scope Boundaries

**In scope:**
- `StartMeetingMessage` 新增 `mode` 欄位（FE + BE）。
- `CaptureFactory` 簽名加 `mode` 參數，single mode 只開 mic stream。
- `sessions/router.py` pre-flight 把 client mode 帶進 factory、依 mode 選 warmup providers、`providers` dict 對齊 `captures` keyset。
- `useMeetingSession` 加 mode state + setter。
- 新元件 `RecordingModeSelector` + `MetadataCard` 接 selector + `HeadphonesHint` conditional。
- 新 i18n keys（D8）+ `errors.session.no_blackhole_device` 文案微調。
- 新測試：capture factory single-mode test、router single-mode test、messages parse test、selector component test、hook setMode test、locale deep-equal。

**Out of scope:**
- `speaker-attribution-strategy` capability（無 spec 變更；行為已自動分流）。
- In-meeting mode switch、mid-session 自動降級。
- Device discovery / `BLACKHOLE_DEVICE_NAME` 解析。
- ASR provider 切換 / Settings 頁面 / 全域預設。
- Offline ingest path。

## Risks / Trade-offs

- **[Risk] 既有測試 fixture `_FakeCaptureFactory` 簽名變更會破壞其他測試 case** → Mitigation：D9 — 既有測試會在編譯/類型階段失敗，TDD 階段同步更新，預設傳 `"dual"` 還原舊行為。
- **[Risk] 漏改 `providers` dict 導致 single mode 的 `SessionService.run()` 收到 `me` chunk 卻找不到 provider** → Mitigation：在 router 構造 `providers` 時與 `captures` 用同一 keyset（單一 source of truth），加 invariant assert 在 dev 模式。
- **[Risk] `errors.session.no_blackhole_device` 文案變更跨越既有測試的字串斷言** → Mitigation：grep 全 repo 既有 assertion 用 error_code（`"session.no_blackhole_device"`），文案應該沒人 hard-code 中文/英文比對；若有，更新該測試斷言。
- **[Risk] 使用者切到 single 卻沒注意，事後抱怨「對方音呢」** → Mitigation：selector helper text 明確寫「不會錄到對方聲音」；session 開始後 `CaptureIndicator` 已只渲染存在 stream（不會顯示空 counterparty 卡），UI feedback 足夠。
- **[Trade-off] 不做自動 fallback** → 使用者多一次選擇，但避免「想 dual 結果拿 single」這種隱性錯誤；明確 > 自動。
- **[Trade-off] Mode 不持久化** → 連續多場 single 場景要重複切，但避免「上次 single 這次忘了切回 dual」隱性錯誤；同樣明確 > 記憶。
