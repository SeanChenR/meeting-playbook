- GitHub Issue：https://github.com/SeanChenR/meeting-playbook/issues/9 （Part A 對應；Parts B/C/D 為 memory 中暫存的 UI deferred 項目）

## Why

Slice 6 解掉「會中即時逐字稿」的整條 pipe，但只跑單聲道 mic — 對方講話一律被標 `me`，違反 ADR-0004 + ADR-0016 的 dual-channel 設計。同時 detail 頁排版、playbook markdown 渲染、meetings 行事曆視圖三個 UI 議題已在 memory 中暫存兩個 slice，繼續延後會讓「會中體驗」打折。本 bundle 一次解掉。

**Smoke-test 回饋輪（Round 2 ingest，2026-05-10）**：實際跑通整條 pipeline 後，Sean 抓到 5 個額外議題，本 slice 順手收尾，不另開 follow-up：(1) Calendar 匯入把會議室名稱當對方；(2) Vite proxy 在 WS 關閉時噴 `socket has been ended` log 噪音；(3) 雙 stream me.wav 收到喇叭聲（echo loop）— Sean 選擇加 UI hint + 強化 setup doc，不做 DSP；(4) TipTap WYSIWYG 體驗不佳，回 textarea + react-markdown 預覽；(5) 整頁 UI 不一致、配色亂、三欄高度不平衡 — 用 `ui-ux-pro-max` 全頁 redesign。

## What Changes

- **Slice 7**：兩條 `AudioCaptureService` instance（mic + BlackHole 2ch）+ 兩個 `WhisperProvider` instance（並行 warmup）+ 雙 mono WAV 寫檔；transcript_chunk.speaker 真實生效；新 WS frame `stream_stopped`；per-stream silence_warning；BlackHole device 名稱比對 + optional env override；BLACKHOLE_SETUP.md 一篇
- **Detail 排版**：top-bar 切換器（Stack ⇄ Columns），3 欄 30/40/30 固定、全寬 detail（`ProtectedShell.fullBleed`）、Advisor pane placeholder
- **Playbook 編輯器**：~~TipTap WYSIWYG~~ → 回到 `<textarea>` 為主 + 內嵌 「編輯 / 預覽」 toggle（preview 用 `react-markdown` + `remark-gfm` + `rehype-sanitize` 渲染）；儲存仍 markdown；TipTap deps 一律刪除
- **Calendar 視圖**：`react-big-calendar` Month/Week 新路由 `/meetings/calendar`，Slice 5 `/calendar` 改名 `/calendar/import`；migration 0004 補 `meeting.scheduled_start_at` + `scheduled_end_at`；/meetings/new 加可選日期；from-calendar 寫入排程時間
- **Round 2 patch — Calendar resource attendees**：`_format_attendee` / `_event_from_resource` 過濾 Google Calendar 的 resource 帳號（`resource: true` / `resourceEmail` / `@resource.calendar.google.com` 結尾），room name 不再被當 counterparty
- **Round 2 patch — Vite WS proxy 噪音**：`packages/web/vite.config.ts` 給 `/api/*` proxy 加 `onError` handler 吸收 `socket has been ended by the other party` 這類 post-close write 錯誤
- **Round 2 patch — Echo loop UX**：detail 頁 Start Meeting 按鈕上方常駐 hint「建議戴耳機，避免麥克風收到喇叭聲音」（status === scheduled 時顯示）；`docs/BLACKHOLE_SETUP.md` 把 echo gotcha 從表格末段提到頁首 callout
- **Round 2 patch — UI overhaul**：跑 `ui-ux-pro-max` skill audit 整個 web app；統一 color tokens / spacing scale / typography pairing；component 變體（Card / Button / Alert）；detail 三欄等高（CSS grid + min-height / aspect-ratio）；list / new / detail / calendar / calendar-import / login / signup / totp / home 全頁套用

## Non-Goals

- pyobjc / CoreAudio runtime 偵測 Multi-Output Device routing — 用 silence_warning 補
- ~~TipTap WYSIWYG 改 HTML / JSON 儲存~~ —（編輯器已被 Round 2 reverted；無此議題）
- Calendar 跨日 meeting 渲染 — MVP 不支援
- Calendar 直接顯示 Google Calendar 未匯入 event — 留在 `/calendar/import`
- Drag-resize columns、autosave、Day / Agenda view、existing rows 的 scheduled_at backfill
- BlackHole 雙 channel 真分流（左右獨立）— ADR-0004 Multi-Output Device 已在系統層匯流
- Speaker diarization、tactical advisor、會後 summary、recording cleanup（Slice 8/10/13）
- DSP echo cancellation（WebRTC AEC、numpy/scipy 自製） — Round 2 決定靠 UI hint + 戴耳機，不投資 DSP
- Storage / 機制改動 calendar event location 欄位 — 只是把 resource attendees 從 counterparty 候選裡踢掉，location 暫時 drop
- 新增 dark mode 主題切換 — Round 2 UI overhaul 只動 default theme tokens，不開 dark/light toggle

## Capabilities

### New Capabilities

- `meeting-detail-layout`: detail 頁的 layout 切換（Stack ⇄ Columns）+ ProtectedShell full-bleed 行為 + 三欄等高（Round 2 加）
- `meetings-calendar-view`: meeting 的 month/week 行事曆視圖 + 未排程列表
- `ui-design-system`: 全頁設計系統 — color tokens、spacing scale、typography pairing、Card / Button / Alert 變體標準（Round 2 新增）

### Modified Capabilities

- `meeting-session`: 雙 stream 擷取契約、兩 WhisperProvider、stream_stopped frame、partial fault tolerance、per-stream silence warnings、Round 2 加上 detail 頁戴耳機 hint
- `meeting-management`: scheduled_start_at + scheduled_end_at 欄位 + /meetings/new optional 排程
- `playbook-management`: ~~TipTap WYSIWYG~~ → textarea 為主 + 內嵌「編輯 / 預覽」toggle（react-markdown 渲染預覽，儲存仍 markdown）
- `calendar-integration`: `/calendar` → `/calendar/import` 改名 + from-calendar import 寫入排程時間 + Round 2 加 resource-attendee 過濾

## Impact

- 後端新檔：
  - `packages/backend/alembic/versions/0004_add_meeting_scheduled_times.py`
  - `packages/backend/tests/test_alembic_meeting_scheduled.py`
  - `packages/backend/tests/asr/fixtures/counterparty_short.wav`（macOS `say` TTS 產生）
- 後端修改：
  - `packages/backend/meeting_playbook/audio/capture.py`（新增 device 探測、name pattern 比對；保留 single-stream API 不變）
  - `packages/backend/meeting_playbook/sessions/service.py`（持有兩 capture + 兩 ASRProvider；per-stream routing；partial fault tolerance）
  - `packages/backend/meeting_playbook/sessions/router.py`（兩 stream 並行啟動 + warmup）
  - `packages/backend/meeting_playbook/sessions/messages.py`（新增 `StreamStopped` 並加入 discriminated union）
  - `packages/backend/meeting_playbook/sessions/repository.py`（per-stream WAV 寫入、recording 兩列）
  - `packages/backend/meeting_playbook/asr/whisper_provider.py`（新增 `warmup()` async 方法）
  - `packages/backend/meeting_playbook/meetings/router.py`（/meetings POST + /from-calendar POST 收 scheduled_start/end）
  - `packages/backend/meeting_playbook/meetings/repository.py`（create / list 帶 scheduled_at）
  - `packages/backend/meeting_playbook/meetings/models.py` + `schemas.py`（新增兩欄）
  - `packages/backend/meeting_playbook/calendar/service.py`（PlaybookGenerator 帶入 event start/end，呼 meetings.from_calendar 時填入）
  - `packages/backend/meeting_playbook/config.py`（新增 BLACKHOLE_DEVICE_NAME / MIC_DEVICE_NAME 兩個 optional 欄位）
  - `packages/backend/tests/audio/test_capture_protocol.py`、`test_capture_integration.py`（雙 stream 新測試）
  - `packages/backend/tests/sessions/test_service.py`、`test_router.py`、`test_messages.py`（雙 stream + stream_stopped + 部分容錯）
  - `packages/backend/tests/sessions/test_repository.py`（雙 WAV）
  - `packages/backend/tests/asr/test_whisper_provider.py`（warmup 測試）
  - `packages/backend/tests/meetings/test_router.py`、`test_repository.py`（scheduled_at 寫入 + 讀取）
  - `packages/backend/tests/calendar/test_service.py`（import 寫入 scheduled_at）
- 後端依賴：無新增（faster-whisper / sounddevice 已在 Slice 6）
- Auth gateway：不動
- 前端新檔：
  - `packages/web/src/lib/markdown-editor.tsx`（TipTap editor wrapper，6-button toolbar）
  - `packages/web/src/lib/markdown-editor.test.tsx`
  - `packages/web/src/hooks/use-detail-layout.ts`（localStorage `meeting-detail.layout` 讀寫）
  - `packages/web/src/hooks/use-detail-layout.test.tsx`
  - `packages/web/src/components/layout-switcher.tsx`（Stack/Columns icon button）
  - `packages/web/src/components/layout-switcher.test.tsx`
  - `packages/web/src/routes/meetings/calendar.tsx`（react-big-calendar 視圖）
  - `packages/web/src/routes/meetings/calendar.test.tsx`
  - `packages/web/src/lib/meetings-calendar-utils.ts`（meeting → react-big-calendar event 轉換 + status → color）
  - `packages/web/src/lib/meetings-calendar-utils.test.ts`
- 前端修改：
  - `packages/web/src/components/protected-shell.tsx`（新增 `fullBleed?: boolean` prop）
  - `packages/web/src/components/playbook-pane.tsx`（freeform 從 textarea 換 MarkdownEditor；structured / freeform tabs 不動）
  - `packages/web/src/components/playbook-pane.test.tsx`
  - `packages/web/src/components/transcript-pane.tsx`（雙 speaker 視覺差異化 — 左 accent border + display name prefix）
  - `packages/web/src/components/transcript-pane.test.tsx`
  - `packages/web/src/components/capture-indicator.tsx`（兩 pill 並列、per-stream 狀態）
  - `packages/web/src/components/capture-indicator.test.tsx`
  - `packages/web/src/routes/meetings/detail.tsx`（fullBleed shell + layout switcher + 3-col grid + Advisor placeholder）
  - `packages/web/src/routes/meetings/detail.test.tsx`
  - `packages/web/src/routes/meetings/new.tsx`（optional 日期+時間欄位 + URL `?date=` 預填）
  - `packages/web/src/routes/meetings/new.test.tsx`
  - `packages/web/src/routes/meetings/list.tsx`（top bar 加「Calendar 視圖」切換按鈕）
  - `packages/web/src/routes/meetings/list.test.tsx`
  - `packages/web/src/routes/calendar.tsx` → `packages/web/src/routes/calendar/import.tsx`（檔案搬移 + URL 更新）
  - `packages/web/src/lib/meetings-api.ts`（create / from-calendar 帶 scheduled_at；list 拉 scheduled_at）
  - `packages/web/src/lib/calendar-api.ts`（i18n 標籤更新）
  - `packages/web/src/lib/use-meeting-session.ts`（reducer 新增 `stream_stopped` 處理 + per-stream UI 狀態）
  - `packages/web/src/lib/session-ws.ts`（discriminated union 新增 StreamStopped 型別）
  - `packages/web/src/lib/use-meeting-session.test.tsx`
  - `packages/web/src/locales/zh-TW.json`、`packages/web/src/locales/en.json`、`packages/web/src/locales/locales.test.ts`（playbook.toolbar.*、meetings.detail.layout.*、meetings.calendar.*、meetings.session.streamStopped、errors.session.blackhole_*）
- 前端依賴新增：`react-big-calendar`、`react-markdown`、`remark-gfm`、`rehype-sanitize`（date-fns 已存在）
- 前端依賴移除：`@tiptap/react`、`@tiptap/starter-kit`、`@tiptap/extension-link`、`tiptap-markdown`（Round 2 反轉）
- Round 2 patch 文件：
  - `packages/web/vite.config.ts`（給 `/api/*` proxy 加 onError handler）
  - `packages/backend/meeting_playbook/calendar/client.py`（過濾 resource attendees）
  - `packages/backend/meeting_playbook/calendar/identity.py`（pick_counterparty 走過濾後的 attendees）
  - `packages/backend/tests/calendar/test_client.py`（resource 過濾測試）
  - `packages/backend/tests/calendar/test_identity.py`（resource attendees 不會成為 counterparty 的 case）
  - `packages/web/src/components/playbook-pane.tsx`（textarea 回來；Edit/Preview toggle）
  - `packages/web/src/lib/markdown-preview.tsx`（新檔 — react-markdown 包裝）
  - `packages/web/src/lib/markdown-preview.test.tsx`（新檔）
  - `packages/web/src/components/headphones-hint.tsx`（新檔 — Start Meeting 上方常駐 callout）
  - `packages/web/src/components/headphones-hint.test.tsx`
  - `packages/web/src/index.css`（design tokens 全面更新；color/spacing/typography）
  - `packages/web/src/components/ui/card.tsx`、`button.tsx`、`alert.tsx`（變體統一）
  - `packages/web/src/routes/{login,signup,home,meetings/list,meetings/new,meetings/detail,meetings/calendar,calendar/upcoming,totp/enroll,totp/verify}.tsx`（套新設計）
  - 移除：`packages/web/src/lib/markdown-editor.tsx`、`packages/web/src/lib/markdown-editor.test.tsx`、`src/test-setup.ts` 內 MarkdownEditor mock 區塊
- 文件：
  - `docs/BLACKHOLE_SETUP.md`（新檔 — install + Audio MIDI Setup walkthrough + meeting-app 設定 + 常見問題）
  - `docs/agents/audio.md`（更新雙 stream 內容）
  - `docs/agents/sessions.md`（更新 stream_stopped + partial fault tolerance）
- 環境：
  - `.env.example` 新增 `BLACKHOLE_DEVICE_NAME`（optional）+ `MIC_DEVICE_NAME`（optional）兩行 + 註解
- 不動：所有 auth / Better Auth tables / Calendar OAuth 流程 / Whisper 模型載入策略
