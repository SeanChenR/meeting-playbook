## Why

`/meetings/$id` 目前最肥的是 MetadataCard：title、status、scheduled time、對方/我方、ASR selector、capture indicator、mode selector、Start/End、Upload、Export、Rerun、Delete、prev/next、相關會議全擠在一張卡內。加上獨立的 tags 列、editToggle、可展開 attachments 區，垂直空間被次要 affordance 吃光，主視角（劇本 / 逐字稿 / 戰術建議）反而被擠扁。原本還允許 stack / columns 兩種 layout，但桌面端永遠用 columns 是更好的對焦選擇。摘要 tab 之後會加 AI 對話，現在改成雙欄就先把版位留好。

## What Changes

- **BREAKING**：移除 LayoutSwitcher（含 `stack` 模式 + `localStorage` `meeting-detail.layout` key）。工作區永遠三欄。
- **BREAKING**：移除 MetadataCard 元件；以新 `MeetingHeaderBar` 取代，只露出 title / status / scheduled time / 對方 + 我方 + capture indicator + 主要 actions（Start/End/Upload/Export）+ `⋯` overflow menu。
- 所有次要 affordance 收進 `⋯` menu：編輯會議、管理標籤、附件（dialog 內含 dropzone）、相關會議、ASR Provider、Recording mode（僅 idle scheduled）、Rerun ASR、刪除會議。
- 移除頁面上獨立的 tags 列、editToggle 按鈕、可展開 attachments section。
- 工作區三欄各自有欄頭（標題 + 該欄工具按鈕）、各自 `overflow-y-auto`、min-w 340px / max-w 460px、等寬、整塊 max-w 1380px 居中。
- 摘要 tab 改雙欄：左欄為現有 markdown 摘要（含 metadata + 工具按鈕），右欄為 AI 對話 slot — 本次只渲染 placeholder 區塊與最小骨架，實際對話功能另開 change。
- i18n：`playbook.heading` 從 `"Playbook"` 改為 `"劇本"`；新增 `meetings.detail.columnPlaybook / columnTranscript / columnAdvisor` 三欄頭文案；en locale 同步補對應字串（劇本→Playbook，逐字稿→Transcript，戰術建議→Advisor）。
- HeadphonesHint 從 card 樣式改為 inline alert，僅在 `dual + idle + scheduled` 同時成立時出現於 header bar 下方。
- 所有 UI affordance（menu icon、按鈕 icon、dismiss button、欄頭工具）一律用 `lucide-react` 元件；本 change 範圍內**禁用 emoji glyph**（Sean 強調「顯得很廉價」）。
- 摘要對話 placeholder 多 3 顆示例 prompt chips（純展示「未來能問什麼」，無 fetch、無互動 callback），文案：「Joyce 那項做完了嗎？」/「對方資安要求摘要」/「下次該準備什麼？」。
- HeadphonesHint copy 改完整版：「建議戴耳機避免回音 — 雙路 ASR 模式下，喇叭外放會被麥克風重複擷取。」（取代簡短版）。
- Overflow menu 內 `ASR 引擎` 與 `錄音模式` item 在 label 右側顯示當前值 sub-hint（例如 `Whisper Large v3`、`雙路 ASR`），讓使用者不點開就知道目前設定。
- 逐字稿欄新增「反對訊號」flag chip 視覺契約：當 chunk 的 `flag_reason` 欄位為非空字串時，該 chunk row 套 `is-flag` highlight class，meta 列加 destructive 色的小 chip 顯示 `flag_reason` 內容。**本 change 僅做 UI 殼**（從 chunk 屬性讀取），後端偵測 / LLM pipeline 另開 change。
- 戰術建議 AI bubble 新增「套用為回覆 / 換一個說法」chips：「套用為回覆」按下後將 bubble 的 `suggestion_text` 塞入 advisor input（純前端 callback）；「換一個說法」**先 disabled** 並掛 tooltip「下版本上線」，等 regeneration endpoint 另開 change 再啟用。
- 新增 `AsrLoadingDialog` 元件：`session.phase === "connecting"` 時自動彈出 modal Dialog，內含 ElevenLabs `<BarVisualizer>` 動畫 + 「正在啟動轉錄引擎…」標題 + 「首次使用會下載 ASR 模型，視網路狀況可能需要 30 秒。背景下載中，請勿關閉視窗。」副標；phase 變 `in_progress` 或 `error` 時自動關閉；modal 不可手動關閉。新增 `@elevenlabs/react` 套件依賴。
- 逐字稿 chunk 列表用 framer-motion `<AnimatePresence>` 包覆，新 chunk arrive 時從底部 slide-up + fade-in（duration 200ms）。維持「最新在下」chronological 順序。不額外引入 MagicUI animated-list 套件 — 動畫直接寫在 transcript-pane 內。
- MeetingHeaderBar 對方 (`counterparty_display_name`) 用 regex `/[,，、]\s*/` parse 為名字陣列：1 個顯示既有 `<Avatar>`；2+ 顯示 animate-ui `<AvatarGroup>`（前 3 個 avatar overlap + 第 4 個起變 `+N` chip）。Backend schema 不動，純 client-side 字串拆分。
- 錄音指示燈擴充為 3 個狀態 + 隱藏：`錄音可用`（`recordings_available === true`，--color-success 綠）、`待上傳`（`bucket === "needs_recording"`，--color-warning 橘）、`錄音已過期`（`bucket === "completed"` && `!recordings_available`，--color-accent 紫 mauve）、`bucket === "upcoming"` 時整個指示燈隱藏（meeting 還沒發生）。原本只有 boolean 兩狀態 + 灰色「已過期」全部移除。
- 在 `MeetingPrevNextNav` row 最左側加回「會議列表」back link（之前 propose 移除過、Sean 第二輪 review 要求加回）：使用 Lucide `ArrowLeft` icon + `會議列表` label、navigates to `/meetings`、與 prev/next 用 vertical divider 分隔。視覺上用 `ArrowLeft`（粗）vs `ChevronLeft/Right`（細）區分「父層導覽」與「同層切換」。
- **修正第一輪 propose 漏改**：Overflow menu **移除「ASR 引擎」item**，從 9 項減為 8 項；ASR Provider 切換只在 `/settings/integrations`。9c sub-hint 只剩「錄音模式」一個保留（顯示當前 mode）；`asrCurrentLabel` prop 移除。
- 劇本欄 6 個欄位（目標 / 對方輪廓 / 預期主題 / 預期反對 / 談話要點 / 紅線）改用 animate-ui Radix Accordion（`type="multiple"` 可同時展開、有 height 動畫、Radix 內建 a11y）取代手刻 `PlaybookField`。預設展開「目標」+「談話要點」兩個常看欄位。新增 `@radix-ui/react-accordion` 套件依賴（如未安裝）。
- 新元件 `SuccessResultOverlay`：上傳音訊完成 + 匯出 ZIP 完成兩個 async 流程結束時，用 hazeover backdrop (`backdrop-blur-sm` + `bg-black/30`) 顯示勾勾 + title + subtitle 的 success overlay，3 秒自動關閉。上傳完成附「查看逐字稿」primary action；匯出完成無 action（browser download 已是自然 closure）。
- 沒有手機端 fallback；元件以桌面 1440px 為基準設計。

## Non-Goals

- 不實作摘要右欄的 AI 對話功能（只留 slot + 標題 + placeholder + 示例 chips）— 下個 change 處理。
- **不實作**逐字稿「反對訊號」的偵測 / 標記邏輯：本 change 只渲染 chip 視覺（讀 chunk.flag_reason）；後端 LLM pipeline 另開 `feature-transcript-objection-flag` change。資料庫先不新增欄位 — 渲染端對 undefined 視為「無 flag」。
- **不實作**戰術建議「換一個說法」功能：本 change 該 chip 渲染為 disabled + tooltip，後端 regeneration endpoint 另開 `feature-advisor-regenerate` change。
- **不實作** ASR Model runtime 拉出 process — 仍是 in-process lazy load；`AsrLoadingDialog` 只是 UI 殼，loading 期間實際還是 backend lazy load Qwen。runtime 抽離另開 `refactor-asr-runtime-isolation` change，做完之後 backend 可發更細的 download/warm-up 狀態，dialog 再依此分階段顯示。本 change 不細分階段。
- **不修改** backend recording schema — 錄音狀態擴充 3 個 state 是純 frontend 派生（從 `recordings_available` + `bucket` 算出來），不新增 DB 欄位。「錄音已過期」與「meeting 完成但從未錄音」目前合併視為「錄音已過期」（語意不完美但實用，side project 接受）。
- 不調整劇本 / 逐字稿 / 戰術建議三個 pane 的核心資料邏輯（劇本欄位、transcript chunks GET、advisor chat history、播放、ASR rerun…維持原樣，只是上面套新 UI 殼）。
- 不更動底部 sticky `MeetingAudioMiniPlayer`。
- 不更動 prev/next 切換邏輯（沿用 `MeetingPrevNextNav`）。
- 不更動 meeting 編輯 dialog 內容（只是把它的觸發點從 toggle button 改成 menu 項目）。
- 不調整 `/settings` 內 ASR Provider 設定的位置（只是把 detail page 上的 selector 改成 menu 內 popover）。
- 不重做 Spectra 已存在的非 `meeting-detail-layout` 業務 spec（playbook-management、tactical-advisor 內容不動，只動 UI 呈現）。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `meeting-detail-layout`: 永久三欄；MetadataCard → MeetingHeaderBar；次要 affordance 收進 overflow menu；摘要 tab 改雙欄；移除 layout switcher 與 localStorage key。

## Impact

- Affected specs: `meeting-detail-layout`
- Affected code:
  - New:
    - packages/web/src/components/meeting-header-bar.tsx
    - packages/web/src/components/meeting-header-bar.test.tsx
    - packages/web/src/components/meeting-overflow-menu.tsx
    - packages/web/src/components/meeting-overflow-menu.test.tsx
    - packages/web/src/components/meeting-detail-summary-view.tsx
    - packages/web/src/components/meeting-detail-summary-view.test.tsx
    - packages/web/src/components/asr-loading-dialog.tsx
    - packages/web/src/components/asr-loading-dialog.test.tsx
    - packages/web/src/components/animate-ui/avatar-group.tsx
    - packages/web/src/components/animate-ui/radix-accordion.tsx
    - packages/web/src/components/success-result-overlay.tsx
    - packages/web/src/components/success-result-overlay.test.tsx
    - packages/web/src/lib/meetings-recording-status.ts
    - packages/web/src/lib/meetings-recording-status.test.ts
  - New (dependencies):
    - `@elevenlabs/react`（提供 BarVisualizer 元件）— `bun add @elevenlabs/react` 加在 `packages/web/`
    - `@radix-ui/react-accordion`（animate-ui Radix Accordion 的底層）— 如已安裝就 reuse
    - animate-ui `avatar-group` / `radix-accordion`：copy-paste 模式（仿 shadcn），不裝套件，原始碼放進 `packages/web/src/components/animate-ui/`
    - DevSloka `success-result` 視覺：copy-paste 原始碼進 `success-result-overlay.tsx`，不裝套件
  - Modified:
    - packages/web/src/routes/meetings/detail.tsx
    - packages/web/src/routes/meetings/detail.test.tsx
    - packages/web/src/components/workspace.tsx
    - packages/web/src/components/workspace.test.tsx
    - packages/web/src/components/playbook-pane.tsx
    - packages/web/src/components/transcript-pane.tsx
    - packages/web/src/components/advisor-pane.tsx
    - packages/web/src/components/headphones-hint.tsx
    - packages/web/src/components/summary-pane.tsx
    - packages/web/src/locales/zh-TW.json
    - packages/web/src/locales/en.json
    - packages/web/src/hooks/use-detail-layout.ts
    - packages/web/src/components/protected-shell.tsx
  - Removed:
    - packages/web/src/components/metadata-card.tsx
    - packages/web/src/components/metadata-card.test.tsx
    - packages/web/src/components/layout-switcher.tsx
    - packages/web/src/components/layout-switcher.test.tsx
