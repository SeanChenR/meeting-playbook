<!--
TDD vertical slice：每個 task 描述「交付什麼可觀察行為」+「怎麼驗收」。
File path 只是定位輔助，不能取代行為描述。
參考：proposal.md / design.md / specs/meeting-session/spec.md。
-->

## 1. WS 訊息合約：StartMeetingMessage 加入 mode 欄位

- [x] 1.1 Backend Pydantic `StartMeetingMessage` 接受 `mode: Literal["dual", "single"]`，缺欄位 default `"dual"`，非法值拒絕（D2 — Mode 欄位的 wire contract）。驗收：新增 `packages/backend/tests/sessions/test_messages.py::test_start_meeting_mode_default_dual`、`::test_start_meeting_mode_single_accepted`、`::test_start_meeting_mode_invalid_rejected` 三個 case 全綠（cf. spec "Pre-flight recording mode selector chooses dual-channel or single-channel capture" 的 Example table）；`bun run test` 對 `packages/backend` 通過。
- [x] 1.2 [P] Frontend TS type `StartMeetingMessage` 與新 `RecordingMode = "dual" | "single"` 型別 export 自 `packages/web/src/lib/session-ws.ts`，與 backend Literal 對齊（D2）。驗收：`bun --filter @meeting-playbook/web test` 通過 type-check 與既有 `session-ws.test.ts`；新增斷言 `StartMeetingMessage` 物件可賦值 `mode: "single"` 不報型別錯。

## 2. Capture factory：mode 參數 + single mode 不檢查 BlackHole

- [x] 2.1 `CaptureFactory` 簽名改為 `Callable[[str, RecordingMode], dict[Stream, AudioCaptureService]]`，single mode 回傳 dict 只含 `"me"`、**不**呼叫 `find_blackhole_device`（D3 — Pre-flight BlackHole 檢查改成 conditional；D9 — Backend test seam）。驗收：新增 `packages/backend/tests/audio/test_capture_factory_single_mode.py`，包含 `test_single_mode_skips_blackhole_lookup`（mock `find_blackhole_device`、斷言 `call_count == 0`）、`test_single_mode_returns_only_me_entry`（dict keyset == `{"me"}`、`stream_label == "me"`）、`test_single_mode_succeeds_when_blackhole_absent`（`find_blackhole_device` 回 `None` 仍成功）、`test_dual_mode_regression`（mode="dual" 行為與舊版本一致）四個 case 全綠。
- [x] 2.2 既有 router/service 測試 fixture（特別是 `tests/sessions/test_router.py` 的 `_FakeCaptureFactory`）更新成接受 `(meeting_id, mode)` 雙參數（D9）。驗收：`cd packages/backend && uv run pytest tests/sessions/ tests/audio/` 全綠，回歸沒有測試因簽名變更而 fail。

## 3. Router pre-flight：依 mode 路由 capture + warmup

- [x] 3.1 `packages/backend/meeting_playbook/sessions/router.py` 的 pre-flight 段把 client 的 `mode` 傳進 `capture_factory(meeting_id, mode)`；`mode="single"` 時 `providers` mapping 只包含 `"me"`、`asyncio.gather` 只 warmup `me_provider`，與 `captures` keyset 對齊（D4 — ASR provider warmup 在 single mode 只 warmup me_provider；D5 — Mode 在 session start 後 immutable，意指 router 採用一次後不再變）。實現 spec requirement "Pre-flight check rejects session start when BlackHole device is missing" 的 conditional 行為 + "Session captures BlackHole and microphone as two parallel streams with independent failure domains" 的 single-mode 分支。驗收：新增 `packages/backend/tests/sessions/test_router.py::test_single_mode_skips_blackhole_check`（無 BlackHole 仍成功進 `meeting_started`）、`::test_single_mode_finalize_writes_one_recording`（finalize 後 DB 只有 1 個 `stream="me"` recording row）、`::test_single_mode_warmup_calls_only_me_provider`（驗 counterparty provider 的 warmup 未被 await）、`::test_dual_mode_unchanged_regression`（dual mode 仍兩 stream + 兩 recording row）四個 case 全綠。
- [x] 3.2 Single-mode 下 mic 失敗仍走 `session.no_audio_device`、warmup 失敗仍走 `session.stream_failed_at_start`（spec requirement "Session captures BlackHole and microphone as two parallel streams with independent failure domains" 的 single-mode failure 段）。驗收：擴充 `packages/backend/tests/sessions/test_router.py` 加 `::test_single_mode_mic_missing_emits_no_audio_device` 與 `::test_single_mode_warmup_failure_emits_stream_failed_at_start` 兩個 case 全綠；status 在 mic 失敗後留在 `scheduled`，warmup 失敗後回到 `completed`。

## 4. Frontend：useMeetingSession 加 mode state

- [x] 4.1 [P] `packages/web/src/hooks/use-meeting-session.ts` 的 reducer 加 `mode: RecordingMode` state 與 `SET_MODE` action；新 `setMode(mode)` API 回傳；`start()` 把當前 `state.mode` 帶進 `start_meeting` frame；session end 後 mode reset 為 `"dual"`（D1 — Mode 預設值是 dual；D7 — State 放 useMeetingSession hook）。驗收：擴充 `packages/web/src/hooks/use-meeting-session.test.tsx` 加 `setMode("single") + start() 送出 frame 帶 mode:"single"`、`session end 後 mode reset 為 "dual"`、`已 start 後呼叫 setMode 不影響 in-flight session` 三個 case 全綠。

## 5. Frontend：RecordingModeSelector 元件 + MetadataCard 整合

- [x] 5.1 [P] 新增 `packages/web/src/components/recording-mode-selector.tsx` — shadcn `<RadioGroup>` 兩個 option（dual / single），props `{ value, onChange, disabled? }`；附 i18n label 與 helper text；無 emoji、用 oklch CSS variable（D6 — Selector 元件擺 MetadataCard 內、Start Meeting button 上方）。驗收：新增 `packages/web/src/components/recording-mode-selector.test.tsx` 加 `renders two radios with default value dual`、`onChange fires when user picks single`、`disabled prop makes both radios readonly`、`helper text comes from i18n keys` 四個 case 全綠。
- [x] 5.2 `packages/web/src/components/metadata-card.tsx` 與 `packages/web/src/routes/meetings/detail.tsx` 串入 selector：`status === "scheduled"` 時 render；`HeadphonesHint` 只在 `mode === "dual" && status === "scheduled"` 顯示（D6；spec ADDED requirement "Pre-flight recording mode selector chooses dual-channel or single-channel capture"）。驗收：擴充 `packages/web/src/routes/meetings/detail.test.tsx` 加 `selector renders when status is scheduled`、`selector hidden when status is in_progress`、`HeadphonesHint hidden when mode is single`、`HeadphonesHint visible when mode is dual` 四個 case 全綠。

## 6. i18n parity：新 keys 同步加 zh-TW.json + en.json

- [x] 6.1 [P] 新增 `meetings.session.recordingMode.{label,dual,single,dualHelper,singleHelper}` 五組 keys（D8 — i18n keys 命名）到 `packages/web/src/locales/zh-TW.json` 與 `packages/web/src/locales/en.json`；同步擴充 `errors.session.no_blackhole_device` 文案，加上「或切到只錄我方模式 / or switch to Mic only mode」尾巴。驗收：`bun --filter @meeting-playbook/web test packages/web/src/locales/locales.test.ts` deep-equal 通過；grep `recordingMode.label` 在兩個 locale 各出現 1 次。

## 7. 整合驗證：spec scenarios 端到端跑過

- [x] 7.1 跑滿 spec ADDED requirement "Pre-flight recording mode selector chooses dual-channel or single-channel capture" 的 7 個 Scenario + Example table（D2/D5/D6）：default dual、切 single 隱藏 hint、frame 帶 mode、status in_progress 後隱藏 selector、缺 mode default dual、invalid mode reject、mode 不持久化。驗收：將每個 scenario 對應到既有測試（任務 1.1 / 4.1 / 5.2）並在 PR description 中列出對映 table；`bun run test`（root） 全綠。
- [x] 7.2 跑滿 spec MODIFIED requirement "Pre-flight check rejects session start when BlackHole device is missing" 的 5 個 Scenario + "Session captures BlackHole and microphone as two parallel streams with independent failure domains" 的 4 個 Scenario（D3/D4）：dual missing BlackHole reject、single missing BlackHole 不 reject、mic missing 兩 mode 都 reject、env override dual mode 生效、single mode 忽略 env override、dual 兩 stream 並行、dual 其中一 stream 起不來整 session 失敗、single 只一個 mic stream、single finalize 只 1 個 recording row。驗收：將每個 scenario 對應到任務 2.1 / 3.1 / 3.2 的測試 case，在 PR description 中列出對映 table；`cd packages/backend && uv run pytest --cov=meeting_playbook.sessions --cov=meeting_playbook.audio --cov-report=term-missing` 覆蓋率 ≥ 80%。
- [x] 7.3 手動驗證：在 dev 環境拔掉 BlackHole device（或 unload kext），開新 meeting → 看到 Recording Mode selector default Dual → 切到 Single → 看到 HeadphonesHint 消失 → 按 Start → 看到 `meeting_started` frame → 講幾句話 → End → 確認 `recordings/<meeting_id>/me.wav` 存在、DB 有 1 個 `stream="me"` recording row、attribution 走 single-channel cluster 路徑、meeting 進 `completed`。驗收：在 PR description 附手動 log + DB query 截圖（`SELECT stream, file_path FROM recording WHERE meeting_id = '<id>'` 結果只有一行 `me`）。

## 8. Design 決策對映檢查（analyzer cross-reference 用）

此節在 PR review 時用來檢查每個 design.md 決策都有對應 implementation task，也讓 spectra analyzer 偵測到完整的 design-to-tasks 連結。

- [x] 8.1 確認 D1：Mode 預設值是 `dual` 由 task 4.1（reducer initial state）+ task 5.2（selector default rendering）涵蓋；D7：State 放 `useMeetingSession` hook，與 session lifecycle 同生死 由 task 4.1 涵蓋；D8：i18n keys 命名 由 task 6.1 涵蓋。驗收：手動 review PR description 中的對映 table，三項皆能指到對應 task 編號與測試名稱。
- [x] 8.2 確認 D2：Mode 欄位的 wire contract — `mode: "dual" | "single"`，缺欄位 → `dual` 由 task 1.1（backend Pydantic）+ task 1.2（frontend TS type）涵蓋；D5：Mode 在 session start 後 immutable 由 task 3.1 與 task 5.2（selector 在 in_progress 隱藏）涵蓋；D6：Selector 元件擺 `MetadataCard` 內、Start Meeting button 上方 由 task 5.1 + task 5.2 涵蓋。驗收：手動 review PR description 中的對映 table，三項皆能指到對應 task 編號與測試名稱。
- [x] 8.3 確認 D3：Pre-flight BlackHole 檢查改成 conditional — 僅 `dual` mode 才驗 由 task 2.1（factory single mode skip BlackHole）+ task 3.1（router pre-flight 帶 mode）涵蓋；D4：ASR provider warmup 在 single mode 只 warmup `me_provider` 由 task 3.1 涵蓋；D9：Backend test seam — capture factory 傳 mode 由 task 2.2（既有 fixture 升級）涵蓋。驗收：手動 review PR description 中的對映 table，三項皆能指到對應 task 編號與測試名稱。
- [x] 8.4 確認 Implementation Contract 段 — Behavior / Interface / Data Shape / Failure Modes / Acceptance Criteria / Scope Boundaries — 皆在 task 1～7 中對應實作與測試。Behavior 由 7.3 手動驗證；Interface / Data Shape 由 1.1+1.2+2.1；Failure Modes 由 3.2；Acceptance Criteria 由 7.1+7.2；Scope Boundaries 在 PR review 時對照 proposal.md 的 Non-Goals 確認沒有實作越界。驗收：PR description 中的 contract 對映 table 涵蓋全部六項。
