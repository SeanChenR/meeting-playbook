## Context

`/meetings/$id` 是 single-user 工具最常停留的頁面。目前負擔太重：

- **MetadataCard** 是 800+ 行不到的元件但塞滿 12+ 個 affordance（status、time、對方、ASR selector、capture indicator、mode selector、Start/End、Upload、Export、Rerun、Delete、prev/next、linked meetings），垂直高度約佔 viewport 30–40%。
- **三欄主視角**（劇本 / 逐字稿 / 戰術建議）被擠在頁面下半，加上獨立 tags 列、editToggle、Attachments 區段，主視角實際可用高度常常只剩 50vh。
- `LayoutSwitcher` 在桌面端 `stack` 模式幾乎不會用 — 三欄是工作的真實樣態，stack 只是早期 hedge 的產物。
- 摘要 tab 之後要加 AI 對話功能（Sean 已決定），先把版位以雙欄結構卡好。

桌面端為主，無手機端 fallback。整頁需要設計上重新「呼吸」，把主視角推到第一視覺、次要 affordance 統一收進 `⋯` overflow menu。

## Goals / Non-Goals

**Goals:**

- 主視角（三欄）佔據 viewport 大部分垂直空間（約 60vh）；header bar + tabs 加總控制在 viewport 高度 25% 以內。
- 所有非主要 affordance（編輯 / 刪除 / 標籤 / 附件 / 相關會議 / ASR Provider / Recording mode / Rerun ASR）收進單一 overflow menu，發現性靠 icon + 數量 badge。
- 工作區三欄等寬、各自 scroll、有清楚欄頭、有該欄專屬工具按鈕；摘要 tab 改雙欄（左 markdown 右 AI 對話 slot）。
- 維持目前所有業務行為（Start/End/Upload/Export/Rerun/Edit/Delete/標籤/附件/相關會議的執行邏輯都不變），只改呈現位置。
- 整頁 max-w 從 1600px 收到 1440px，三欄主內容區 max-w 1380px 居中。

**Non-Goals:**

- 不實作摘要右欄 AI 對話的功能（只擺 slot + 標題 + placeholder + 「即將推出」狀態）。
- 不調整三個 pane（playbook / transcript / advisor）的內部邏輯與資料來源。
- 不更動 `MeetingAudioMiniPlayer`。
- 不做手機端 responsive collapse — 視窗寬度 < 1024px 視為未支援場景，元件可破版（保留現狀，未來再說）。
- 不重命名後端 API、資料庫欄位、code 內部變數（playbook 等英文 identifier 維持）。

## Decisions

### Decision 1: MeetingHeaderBar 取代 MetadataCard

新元件 `meeting-header-bar.tsx` 用一橫條呈現核心 metadata：

- 第一行：標題（h1，2xl bold） + status badge（含彩色 dot） + scheduled time window + 對方 + 我方 + 可選 capture indicator（live/ending 時）
- 第二行：主要 actions（依 status）+ `⋯` overflow menu trigger
- 上方第 0 行：`MeetingPrevNextNav`（保留）

`MetadataCard` 元件與測試一併刪除。`MetadataCard` 內部使用的 `MeetingLinksSection`（相關會議）改為被 overflow menu 內的 `[Link2] 相關會議` 項目（圖示用 `lucide-react` 的 `Link2`）開啟的 dialog。

Alternative 拒絕：保留 MetadataCard 但縮成 mini 版 — 結構複雜度沒降；插槽機制（`asrSelector` / `captureIndicator` / `rerunSlot` / `uploadSlot`）已過時，趁機砍掉。

### Decision 2: MeetingOverflowMenu — 統一收 8 個次要 affordance

新元件 `meeting-overflow-menu.tsx` 是一個 shadcn DropdownMenu trigger 在 header bar 右上。menu items：

| Item | i18n | Lucide icon | 開啟行為 | 條件 |
|---|---|---|---|---|
| 編輯會議 | `meetings.detail.menu.edit` | `Pencil` | 開原本 Edit dialog | 永遠 |
| 管理標籤 | `meetings.detail.menu.tags` | `Tag` | 開包含 `TagPicker` 的 dialog（內含現有 tag chips 列） | 永遠 |
| 附件 (N) | `meetings.detail.menu.attachments` | `Paperclip` | 開包含 `AttachmentDropzone` 的 dialog | 永遠（badge 顯示數量） |
| 相關會議 (N) | `meetings.detail.menu.linked` | `Link2` | 開包含 `MeetingLinksSection` 的 dialog | 永遠（badge 顯示數量） |
| —separator— | | | | |
| ASR Provider | `meetings.detail.menu.asr` | `Settings2` | popover 內含 `AsrProviderSelector` | 永遠 |
| Recording mode | `meetings.detail.menu.mode` | `Mic2` | popover 內含 `RecordingModeSelector` | `idle + scheduled` only |
| Rerun ASR | `meetings.detail.menu.rerun` | `RotateCw` | 直接觸發（或開 `RerunButton` 的確認 dialog） | 永遠（與 `RerunButton` 內部邏輯一致） |
| —separator— | | | | |
| 刪除會議 | `meetings.detail.menu.delete` | `Trash2` | 開現有 delete `AlertDialog` | 永遠（destructive 顏色） |

所有 icon 元件直接 import 自 `lucide-react`；每個 menu item 渲染時 icon 在文字左側、16px、`stroke-width: 1.5`。**禁止使用 emoji glyph** — 不論是 menu item、按鈕、column header tools、empty state，所有 UI affordance 一律走 Lucide / shadcn icon component。

Alternative 拒絕：分成「會議資料」與「會議設定」兩個 menu — 單一 menu 更好預測；用 separator 區分群組已足夠。

### Decision 3: Workspace 永遠三欄、移除 LayoutSwitcher

修改 `workspace.tsx`：

- 永遠渲染 `[playbook | transcript | advisor]` grid（CSS Grid `1fr 1fr 1fr`）。
- 移除 `layout` prop 與 `stack` 模式（一併移除 `layout-switcher.tsx` 元件 + `use-detail-layout` hook + `meeting-detail.layout` localStorage key）。
- 每欄 wrap 一個 `<MeetingColumn>` shell（新 subcomponent in `workspace.tsx`）：
  - 欄頭固定（`sticky top-0`）含標題（i18n `meetings.detail.columnPlaybook` 等）+ 該欄工具 slot
  - 內容區 `flex-1 overflow-y-auto`
  - 高度 = `calc(100vh - var(--detail-header-h) - var(--mini-player-h))`，CSS 變數由 `MeetingDetail` 注入避免硬編
  - min-w `340px`、max-w `460px`
- 三欄區整塊 max-w `1380px`、`mx-auto`、`gap-4`、`px-6`。

`ProtectedShell` 的 `fullBleed` prop 維持（detail page 仍然 fullBleed，現有 contract 不動）。

Alternative 拒絕：保留 stack 模式但 deprecated — 沒人會用，code 變雜訊。

### Decision 4: MeetingDetailSummaryView 雙欄

新元件 `meeting-detail-summary-view.tsx`，取代 detail.tsx 中對 `SummaryPane` 的直接渲染。結構：

```
<div className="grid grid-cols-[1fr_1fr] gap-4 max-w-[1380px] mx-auto">
  <section> {/* 左欄：摘要本體 */}
    <SummaryPane meetingId={...} meeting={...} />
  </section>
  <section data-testid="meeting-summary-chat-slot"> {/* 右欄：AI 對話 slot */}
    <header>摘要對話</header>
    <div className="empty-state">即將推出（next change）</div>
  </section>
</div>
```

兩欄等高、各自 scroll、整塊 max-w 1380px。`SummaryPane` 內部不動。

Alternative 拒絕：摘要本體佔 2/3、AI 對話 1/3 — Sean 確認要對等雙欄，給 AI 對話足夠空間之後實作。

### Decision 5: i18n — Playbook → 劇本

只動 zh-TW + en 兩個 locale 檔。code 內部識別子（檔名、元件名、變數）保持英文 `playbook`：

- `playbook.heading`: zh-TW 從 `"Playbook"` 改 `"劇本"`；en 維持 `"Playbook"`
- 新增 `meetings.detail.columnPlaybook` / `columnTranscript` / `columnAdvisor`，三欄頭顯示文案：
  - zh-TW: `劇本` / `逐字稿` / `戰術建議`
  - en: `Playbook` / `Transcript` / `Advisor`
- 新增 9 條 menu i18n key（`meetings.detail.menu.*`），雙語各補。

CLAUDE.md 規定 UI 字串必須兩 locale 同步，否則 `locales.test.ts` 會 fail；本 change 補齊。

### Decision 6: HeadphonesHint 改 inline alert

從 Card 樣式改成單行 inline alert（shadcn `<Alert>` variant `info`），出現位置在 MeetingHeaderBar 下方、tabs 上方。內含 Lucide `X` icon button 作為 dismiss 觸發（dismiss 狀態持續到頁面卸載，不寫 localStorage）。觸發條件不變（`dual + idle + scheduled`）。

Alternative 拒絕：完全移除 — 第一次使用者仍需要這個提示。

### Decision 7: 不做手機端

CLAUDE.md 與 user feedback 確認桌面端為主。本次設計以 1440px 寬為基準，min 寬度 1024px 假設仍能勉強顯示（三欄各 340px = 1020px + gap），<1024px 不保證可用。未來若加手機端，當作另一個 change（會牽涉所有 pane 行為，scope 大）。

### Decision 8: 禁用 emoji，所有 UI affordance 用 Lucide icon

Sean 在 propose 收尾時強調：「能用 icon 就用 icon，不要用 emoji，顯得很廉價」。本 change 範圍內的所有可見 UI affordance（menu item 圖示、按鈕圖示、欄頭工具、empty state 視覺、alert 內 icon、dismiss 按鈕）一律使用 `lucide-react` 元件，不得用 unicode emoji glyph（包括但不限於 `✏ 🏷 📎 🔗 ⚙ 🔄 🗑 ▶ ■ ⤴ ⤓ × 📅 📋`）。

具體對照：

| 用途 | Lucide icon |
|---|---|
| 編輯 | `Pencil` |
| 標籤 | `Tag` |
| 附件 | `Paperclip` |
| 連結（相關會議） | `Link2` |
| 設定（ASR） | `Settings2` |
| 麥克風（Recording mode） | `Mic2` |
| 重跑 | `RotateCw` |
| 刪除 | `Trash2` |
| 播放 | `Play` |
| 結束 / Stop | `Square` |
| 上傳 | `Upload` |
| 下載 / 匯出 | `Download` |
| 關閉 / dismiss | `X` |
| Overflow menu trigger | `MoreHorizontal` |
| 展開 / 折疊 | `ChevronDown` / `ChevronRight` |
| 上一場 / 下一場 | `ChevronLeft` / `ChevronRight` |
| 摘要 AI 對話 placeholder | `MessageSquare` |
| 音量 | `Volume2` |
| 送出（advisor chat） | `SendHorizontal` |
| 清空對話 | `Eraser` |

預設尺寸 16px、`stroke-width: 1.5`、`currentColor`；hover state 隨 button variant 顏色變化。

Alternative 拒絕：用 emoji 當 icon — 跨平台呈現不一致、感覺廉價（Sean 明確 reject）；用純文字按鈕 — 失去視覺記憶點且 menu item 排版會跑掉。

### Decision 9: 從 Claude Design 回稿吸收 5 個 UI 細節

Sean 將 propose 拿給 Claude Design 跑出 3 個 artboards（workspace / workspace+menu / summary）後回稿，新增以下 5 項，本 change 收進來：

**9a. 摘要對話 placeholder 示例 chips（純 UI）**

`<MeetingDetailSummaryView>` 右欄（摘要對話 placeholder）下方多渲染 3 顆灰階 chip 展示「未來能問什麼」：
- `「Joyce 那項做完了嗎？」`
- `「對方資安要求摘要」`
- `「下次該準備什麼？」`

Chip 為純展示元素 — `<span>` with `cursor: default`，**不可點**、無 onClick、無對應 i18n key（直接 hardcode，未來實作 chat 時再 i18n 化）。視覺：`bg-(--color-surface-2)`、`text-(--color-muted-foreground)`、`rounded-full`、`px-3 py-1`。

**9b. HeadphonesHint copy 完整版**

`headphones.alert` i18n key 從現有簡短版改為：
- zh-TW: `建議戴耳機避免回音 — 雙路 ASR 模式下，喇叭外放會被麥克風重複擷取。`
- en: `Recommended: wear headphones to avoid echo — in dual ASR mode, speaker output will be re-captured by the microphone.`

Copy 變長 → alert 高度可能變 2 行；設計上仍維持 single-line（用 `truncate` + tooltip 顯示完整）或允許 wrap 2 行（建議 wrap，避免截斷重要警示）。實作選 wrap。

**9c. Overflow menu sub-hint 顯示當前值**

`<MeetingOverflowMenu>` 內的 `asr` 與 `mode` items 在 label 右側 + 左側 chevron（如有 popover）之間，加一個 sub-hint span 顯示當前值：
- `asr` item label = `ASR 引擎`，sub-hint = `meeting.asr_provider` 對應的人類可讀名（如 `Whisper Large v3`、`Qwen3` 等，從現有 `<AsrProviderSelector>` 內的 options 表查）
- `mode` item label = `錄音模式`，sub-hint = `session.mode` 對應的人類可讀名（`雙路 ASR` / `單路（合流）`）

Sub-hint 樣式：`text-xs text-(--color-muted-foreground)`，與 chevron 之間有 8px gap。`MeetingOverflowMenu` props 新增 `asrCurrentLabel: string | undefined` 與 `modeCurrentLabel: string | undefined`，由 detail.tsx 計算後傳入；undefined 時 sub-hint 不渲染。

**9d. 逐字稿「反對訊號」flag chip 視覺契約**

`<TranscriptPane>` 渲染 chunk 時，若 chunk 物件含 `flag_reason: string | null | undefined` 且為非空字串，該 chunk row 套 `is-flag` highlight class（左側 4px destructive 色直條 + `bg-(--color-destructive)/4` 微染），且 meta 列在 timestamp 右側加一個 destructive 色小 chip 顯示 `flag_reason` 內容（例如 `反對訊號`）。

**範圍邊界（重要）：**

- 本 change **只做 UI 殼**：TranscriptChunk type 加 optional `flag_reason?: string` 欄位（純 frontend type，backend schema 不動）；frontend 把 backend 回傳的 chunk JSON 內 `flag_reason` 直接 read through。
- backend 目前 **不會回傳** `flag_reason`，所以實際 UI 上不會出現任何 flagged chunk — 但版位 / 樣式 / type 全部就緒。
- 偵測邏輯（要靠 LLM 分析 chunk text 標出「反對訊號 / 紅線觸發 / 時間敏感」等）另開 change `feature-transcript-objection-flag`。
- 測試以 mock chunk（手動塞 `flag_reason: "反對訊號"`）驗證視覺契約。

**9e. 戰術建議 reply chips**

`<AdvisorPane>` 渲染 AI bubble 時，若 bubble 物件含 `suggestion_text: string | null | undefined` 且為非空字串，bubble 內容下方加一個 chip 列：
- `[套用為回覆]` — 啟用；click 後呼叫 `onApplySuggestion(suggestion_text)` callback，將 `suggestion_text` 塞入 advisor input。`onApplySuggestion` 為新增的 `AdvisorPane` prop。
- `[換一個說法]` — `disabled`，掛 tooltip「下版本上線」，點不到任何 callback。

**範圍邊界（重要）：**

- 本 change **只做 UI 殼 + 套用 callback 串接**：AdvisorMessage type 加 optional `suggestion_text?: string` 欄位（純 frontend type）；advisor input 元件接受 controlled value（既有設計）。
- backend 目前 **不會回傳** `suggestion_text`，UI 上不會自動出現 chips — 版位 / 樣式 / callback wiring 就緒。
- 「換一個說法」功能（呼叫 LLM regenerate）另開 change `feature-advisor-regenerate`。
- 測試以 mock bubble（手動塞 `suggestion_text: "..."` ）驗證視覺契約 + click「套用為回覆」後 input value 更新。

**Alternative 拒絕：**

- 把 9d / 9e 整個延後到後續 change — 已經寫到 spec / 設計上的東西最好現在把版位卡好，避免之後 refactor 又動 column 結構。
- 9d / 9e 把後端邏輯也做進來 — scope 失控；refactor change 應該只負責 UI，feature change 負責邏輯。

### Decision 10: 第二輪 Sean review 加 4 個 UI 項

**10a. AsrLoadingDialog（ASR 啟動中遮罩）**

Qwen ASR 目前是 in-process lazy load，按下「開始」會卡在 `session.phase === "connecting"` 直到模型載入 / 暖機完成 — 首次 30s+，cached 後 ~2s。期間使用者沒有任何回饋。

新元件 `asr-loading-dialog.tsx`：
- shadcn `<Dialog>` modal，不可手動關閉（`onOpenChange` 忽略 dismiss request）
- `open` = `session.phase === "connecting"`；phase 變 `in_progress` 或 `error` 自動關閉
- 內容：ElevenLabs `<BarVisualizer>` 動畫 + 標題 + 副標兩段文案
  - i18n key `meetings.session.asrLoading.title`：`正在啟動轉錄引擎…` / `Starting transcription engine…`
  - i18n key `meetings.session.asrLoading.subtitle`：`首次使用會下載 ASR 模型，視網路狀況可能需要 30 秒。背景下載中，請勿關閉視窗。` / `First-time use will download the ASR model and may take up to 30 seconds depending on network. Downloading in background — please don't close this window.`
- BarVisualizer 配色：bar fill `--color-primary`、background `--color-primary-soft`、約 24 條 bar，autoplay 不需 audio source（純裝飾動畫模式）
- 在 detail.tsx render，與 MeetingHeaderBar 平級

**範圍邊界（重要）：**

- 本 change 只實作 UI 殼與既有 `connecting` phase 的 hook。
- 不細分「downloading / warming / handshake」階段 — 目前 backend 只丟 `phase=connecting` 一個訊號，dialog 顯示通用「正在啟動」即可。
- ASR runtime 抽出 process（讓 backend 能發 download progress 訊號）另開 `refactor-asr-runtime-isolation` change；屆時 dialog 內容可以再升級成有進度條的版本。
- 不加 cancel 按鈕（backend 無對應 endpoint）。

Alternative 拒絕：用 toast 而非 modal — toast 容易被忽略，使用者可能誤以為已經開始，又重複按；modal 強制等待最清楚。

**10b. Transcript chunk 動畫**

`<TranscriptPane>` 渲染 chunk 列表時，外層用 framer-motion `<AnimatePresence initial={false}>` 包覆。每個 chunk row 為 `motion.div`，新 chunk arrive 時：

- `initial = { opacity: 0, y: 12 }`
- `animate = { opacity: 1, y: 0 }`
- `transition = { duration: 0.2, ease: "easeOut" }`
- `exit` 不定義（chunks 不會消失，只會增加 / rerun 後整體替換）

維持「最新 chunk 在下方」chronological 順序；新 chunk 從底部 12px 下方 slide-up 進來。`initial={false}` 避免初次 mount 時所有 chunks 一起做進場動畫。reduced-motion 環境下沿用 framer-motion `useReducedMotion` 把 duration 設 0。

Alternative 拒絕：

- 引入 MagicUI animated-list 整包套件 — 該套件是「最新在上」push-down 邏輯，與我們「最新在下」相反；改方向需要 reverse children 順序、心智成本高。
- 用 CSS `@keyframes` 動畫 — 無法與 React 的 key-based reconciliation 整合，新 chunk 識別變繁瑣。

**10c. 對方 avatar-group**

MeetingHeaderBar 渲染對方那一格時：

1. 把 `meeting.counterparty_display_name` 用 `String.split(/[,，、]\s*/)` 切成 `string[]`，過濾空字串。
2. 若陣列長度 `=== 1`，沿用現有 `<Avatar>` + 名字。
3. 若 `>= 2`，渲染 animate-ui `<AvatarGroup>`：
   - 最多顯示 **3 個 avatar** overlapping（z-index 由前到後遞減；最後一個 avatar 在最右）
   - 第 4 個起變 `+N` chip（N = 總數 - 3），chip 樣式 `bg-(--color-surface-2) text-(--color-muted-foreground) text-xs rounded-full size-6`
   - 名字 label 顯示「前 1 個名字 等 N 人」（例「林經理 等 5 人」）— 較不擠

支援的分隔符：`,`（半形逗號）/`，`（全形逗號）/`、`（頓號），分隔符前後可有空白。空白本身不算分隔。

`<AvatarGroup>` 元件採 animate-ui copy-paste 模式 — 把元件原始碼放進 `packages/web/src/components/animate-ui/avatar-group.tsx`，不裝外部套件（與本專案既有 animate-ui icons 處理方式一致）。

**範圍邊界：**

- 純 frontend；backend `counterparty_display_name` schema 不動，仍是單一 `string`。
- 不改動 meeting create / edit form — 使用者本來就可以在該欄位輸入「林經理, 王董」，只是現在會以 avatar-group 呈現。
- 未來若要正式支援多對方資料（個別 avatar 圖、個別職稱），另開 change 改 schema。

Alternative 拒絕：backend schema 直接改成 `counterparty_display_names: string[]` — scope 跨層；此 refactor 應該只動 UI。

**10d. Recording 指示燈擴充為 3 狀態 + 隱藏**

MeetingHeaderBar 第一行右側的 recording 指示燈從原本 2 狀態 boolean（綠 `錄音可用` / 灰 `錄音已過期`）改為 3 狀態 + 隱藏：

| 狀態 | 觸發條件 | 顏色 token | i18n key |
|---|---|---|---|
| **錄音可用** | `meeting.recordings_available === true` | `--color-success`（綠） | `meetings.detail.recordingAvailable` |
| **待上傳** | `bucket === "needs_recording"` | `--color-warning`（橘，與 Kanban needs_recording 欄一致） | `meetings.detail.recordingPending`（新） |
| **錄音已過期** | `bucket === "completed"` && `!recordings_available` | `--color-accent`（mauve magenta，過去式靜止感） | `meetings.detail.recordingExpired`（既有 key，文案維持） |
| **隱藏** | `bucket === "upcoming"` | — | — |

派生邏輯抽到 `lib/meetings-recording-status.ts` helper：

```ts
type RecordingStatus = 'available' | 'pending' | 'expired' | 'hidden';
function resolveRecordingStatus(meeting): RecordingStatus { ... }
```

灰色（`--color-muted-foreground` 或 `--color-surface-3`）**禁用**於 recording 指示燈 — Sean 認為過期狀態用灰色太「黯淡無生氣」，Aura 配色 palette 顏色夠多，過去式用 mauve 就好。

**範圍邊界：**

- Backend schema **不動**（仍只有 `recordings_available: boolean`）；新 `待上傳` / `錄音已過期` 從 `bucket` 派生。
- 語意瑕疵：「meeting 完成但從未錄音」（offline interview）目前與「TTL 過期」合併視為 `錄音已過期`。Sean 接受此妥協（side project，少見案例）。若未來要分開：backend 加 `recordings_ever_existed: boolean` 欄位 → 另開 change。

Alternative 拒絕：「錄音已過期」用 destructive 紅 — Sean 試色覺得太 alarming，TTL 過期是設計上的清理不是錯誤；mauve 較貼切。

### Decision 11: 加回「會議列表」back link 到 PrevNextNav 列

Sean 第二輪 review 指出：之前的 propose 在 spec MODIFIED 階段把 standalone BackLink 完全移除，理由是「prev/next 列本身就能藉由跳到鄰居 meeting 回到列表 + ProtectedShell 全域導覽有 /meetings 連結」— 但實際使用時：

- prev/next 跳的是另一場 meeting，不是回到列表
- ProtectedShell 全域導覽的 `/meetings` 連結藏在 nav 內，使用者不會把它當作「返回」按鈕

需要一個明確的「返回到 meeting 列表」affordance。

**設計：**

`<MeetingPrevNextNav>` 元件擴充為三段 layout，全部在同一橫 row 內：

```
[ArrowLeft] 會議列表   │   [ChevronLeft] 上一場 「Q3 review」  /  下一場 「客戶 X kickoff」 [ChevronRight]
```

- 最左：back link，包含 Lucide `ArrowLeft` icon (14px) + 「會議列表」label，整個 wrap 在 TanStack `<Link to="/meetings">` 中
- 中間：vertical divider，`w-px h-3 bg-(--color-border)`，作為「父層導覽」與「同層切換」的視覺分隔
- 右側：原有 prev/next 群組（用 `ChevronLeft / ChevronRight`，細箭頭）

**為何不是 breadcrumb（如「會議列表 / 客戶 ACME 第二輪需求討論」）：**
- detail page 已經有大字 H1 標題在 MeetingHeaderBar 內，重複顯示 meeting 名稱多餘
- breadcrumb 必須跟 title 配，且要思考省略策略，複雜化 layout

**為何不是兩 row（back link 一 row、prev/next 一 row）：**
- 增加 ~32px 垂直高度，吃掉主視角（三欄）的空間
- 同一 row 三段視覺上仍清楚（icon 不同 + divider）

**為何 label 是「會議列表」而非「返回」/「首頁」：**
- 「返回」沒指明目的地（返回哪裡？）
- 「首頁」語意模糊（這個 app 的「首頁」就是 `/meetings`，但使用者不一定這樣認知）
- 「會議列表」直接點明目的地，breadcrumb-style 語意

**i18n：**
- 新增 key `meetings.detail.backToList`：zh-TW `會議列表` / en `All meetings`

**範圍邊界：**

- 純前端；無 backend 變動
- 不重新引入 `back-link.tsx` 舊元件 — 直接在 `MeetingPrevNextNav` 內 inline 渲染
- ProtectedShell 全域導覽的 `/meetings` 連結保留不動（兩個入口並存，detail page 內優先用 back link）

Alternative 拒絕：

- 把 back link 放進 MeetingHeaderBar 內（如 title 左側小 arrow）— 跟 H1 title 視覺上會打架
- 把 back link 跟 prev/next 整合（如「← 上一場 / 列表 / 下一場 →」）— 「列表」不是平輩，混在 prev/next 群組裡語意錯亂
- 在 ProtectedShell global nav 加 breadcrumb — 全域改動 scope 太大、影響其他頁面

### Decision 12: ASR Provider 移到 /settings、menu 只剩 8 項（修正 propose 漏改）

我在第一輪 propose 收尾時答應 Sean「ASR Provider 移到 `/settings`、menu 只留 Recording mode」（Q2 確認後 Sean 答「都 OK」），但 spec 與 design 都沒實際反映 — overflow menu 仍有 9 個 item 含 ASR 引擎，9c sub-hint 也對 ASR 著色顯示當前值。Sean 第三輪 review 抓到。

**修正：**

- Overflow menu items 從 **9 項減為 8 項**。被移除的是「ASR 引擎」row（icon `Settings2`，本來開 popover 含 `<AsrProviderSelector>`）。
- 9c sub-hint 只保留「錄音模式」一個（顯示「雙路 ASR」/「單路（合流）」當前值）。`asrCurrentLabel` prop 整個移除。
- 使用者要切換 ASR Provider 走 `/settings/integrations`（既有頁面已含 `<AsrProviderSelector>`）。
- **不**在 menu 加「在設定中切換 ASR」提示連結 — 過度提示反而擾人；使用者真要切的時候自己會找到 settings。

**範圍邊界：**

- 仍保留 `MeetingOverflowMenu` 元件 + 8 項 + 兩 separator + nested popover（只剩 mode）。
- 既有 `<AsrProviderSelector>` 元件不動（在 `/settings/integrations` 繼續使用）。

Alternative 拒絕：把 ASR 引擎 item 變成「navigate to /settings/integrations#asr」link — 等於用兩步達成「點 menu → 跳設定頁」，不如直接讓 menu 不出現此 affordance。

### Decision 13: 劇本欄位用 animate-ui Radix Accordion 取代手刻

Claude Design 回稿的 `PlaybookField` 是手刻 expand/collapse — `useState` + 條件渲染 + 沒有 height 動畫。Sean 要求改用 animate-ui Radix Accordion，享受：

- Radix UI 內建 a11y（`aria-expanded`、`aria-controls`、keyboard nav）
- animate-ui 包好的 height 動畫（framer-motion 動 max-height）
- `type="multiple"` 支援同時展開多個

**設計：**

複製 animate-ui Radix Accordion 元件原始碼進 `packages/web/src/components/animate-ui/radix-accordion.tsx`（與既有 animate-ui icons / avatar-group 一致 copy-paste 模式）。需要 `@radix-ui/react-accordion` 依賴；若 `packages/web/package.json` 已有就 reuse，否則 `bun add`。

PlaybookPane 改寫：

```tsx
<Accordion type="multiple" defaultValue={["objective", "talkingPoints"]}>
  <AccordionItem value="objective">
    <AccordionTrigger>目標</AccordionTrigger>
    <AccordionContent>{playbook.objective}</AccordionContent>
  </AccordionItem>
  ... (6 items total)
</Accordion>
```

`type="multiple"` 因為劇本本來就會交叉看（目標 vs 紅線、預期反對 vs 談話要點）。預設展開兩個常看的：目標 + 談話要點。

**範圍邊界：**

- 純前端視覺；playbook 資料來源不變
- 不動「自由格式 / 結構化」切換 toggle 的邏輯
- 不動 AI 草稿 badge

Alternative 拒絕：手刻 + 加 framer-motion `<motion.div>` 動 height — 等於重新發明 Radix Accordion 的輪子；用現成元件省心又 a11y。

### Decision 14: 上傳 / 匯出完成顯示 SuccessResult overlay（hazeover）

Sean 在 third-round review 提議引入 DevSloka `success-result` 元件，用在「上傳音訊完成」與「匯出 ZIP 完成」兩個 async 流程結束時，以 hazeover（backdrop blur + dim）方式給使用者明確 closure。

**設計：**

新元件 `success-result-overlay.tsx`：

- DevSloka `success-result` 的勾勾動畫 + title + subtitle + 可選 primary button → 內含元件樣式 / motion
- 外層用 `fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[60]` 達到 hazeover 視覺
- props：
  ```ts
  {
    open: boolean;
    title: string;
    subtitle?: string;
    autoDismissMs?: number;  // 預設 3000；0 代表不自動關
    onClose: () => void;
    primaryAction?: { label: string; onClick: () => void };
  }
  ```
- 行為：
  - mount 後若 `autoDismissMs > 0`，setTimeout 後呼叫 `onClose`
  - 按 ESC 或點 backdrop → `onClose`
  - 點 primaryAction button → 先觸發 `primaryAction.onClick` 再 `onClose`

**Wire 到既有 async flow：**

| 場景 | 觸發點 | overlay 內容 | primaryAction |
|---|---|---|---|
| **上傳音訊完成** | `UploadDialog` 內 `state === "done"` → close dialog → set `uploadSuccessOpen=true` | title「音檔處理完成」 + subtitle「逐字稿已自動生成」 + 自動 3s 關 | `{label: "查看逐字稿", onClick: () => 切到 workspace tab + focus transcript column}` |
| **匯出 ZIP 完成** | `ExportMeetingButton` ZIP fetch + browser download triggered → onExportSuccess callback → set `exportSuccessOpen=true` | title「匯出完成」 + subtitle「ZIP 已儲存到下載資料夾」 + 自動 3s 關 | （無）— 沒有自然的下一步動作 |

兩個 state 都由 `detail.tsx` 管理，overlay 也在 detail.tsx 渲染（與 MeetingHeaderBar 平級）。

**i18n（新 5 key）：**

| key | zh-TW | en |
|---|---|---|
| `meetings.detail.uploadSuccessTitle` | `音檔處理完成` | `Audio processed` |
| `meetings.detail.uploadSuccessSubtitle` | `逐字稿已自動生成` | `Transcript generated` |
| `meetings.detail.exportSuccessTitle` | `匯出完成` | `Export complete` |
| `meetings.detail.exportSuccessSubtitle` | `ZIP 已儲存到下載資料夾` | `ZIP saved to Downloads` |
| `meetings.detail.viewTranscript` | `查看逐字稿` | `View transcript` |

**範圍邊界：**

- 只 wire 兩個 async 場景（upload + export），不擴張到 ReRun ASR / Playbook 生成（後者本來就有自己的 pending 狀態 UI）。
- 不做「失敗 overlay」對應元件 — error 狀態沿用既有 inline alert / toast；本元件只做 success。
- 元件僅在 detail page 內使用；不全域；其他頁面要用可在後續 change 提升。

Alternative 拒絕：

- 用 toast 取代 overlay — 沒有 hazeover 視覺強度，Sean 明確要 modal-style closure。
- 把 ASR 啟動成功也用 success overlay — 啟動成功直接進 in_progress（transcript 跳出新 chunk）就是 closure，再加 overlay 過度。

## Implementation Contract

**Behavior**

- 載入 `/meetings/$id`：頁面渲染順序 — `MeetingPrevNextNav` → `MeetingHeaderBar` → 條件式 inline alerts（headphones hint / session error）→ Tabs（工作區 / 摘要）→ tab panel。
- 工作區 tab：渲染 `<Workspace>` 三欄（永遠三欄、永遠等寬、永遠獨立 scroll）。
- 摘要 tab：僅在 `meeting.status === "completed"` 時可點；點擊渲染 `<MeetingDetailSummaryView>` 雙欄。
- 點 `⋯` overflow menu：顯示 9 項 menu items（依條件顯示／隱藏 Recording mode），點擊各項觸發對應 dialog / popover。
- 點 menu 內「附件 (N)」：開 dialog 內含現有 `<AttachmentDropzone>`，N 為 `meeting.attachments?.length ?? 0`。
- 點 menu 內「相關會議 (N)」：開 dialog 內含現有 `<MeetingLinksSection>`，N 為已連結會議數。
- HeadphonesHint：dual + idle + scheduled 三條件同時成立才出現；用戶點 Lucide `X` icon button 後本次頁面停留期間不再顯示，重新進入頁面才重置。
- 載入 `/meetings/$id?action=upload` 行為不變：開 UploadDialog、scrub query。
- `MeetingAudioMiniPlayer` 行為不變：sticky bottom、跨 tab 切換不卸載。

**Interface / data shape**

- `MeetingHeaderBar` props: `{ meeting, phase, onStart, onEnd, startDisabled, bucket, capture: { streamStatus, meDisplayName, counterpartyDisplayName, ending, chunks }, primaryActions?: ReactNode, menuTrigger: ReactNode }`。
- `MeetingOverflowMenu` props: `{ meeting, bucket, phase, onEdit, onDelete, onAttachmentsOpen, onTagsOpen, onLinkedOpen, onAsrOpen, onModeOpen, onRerun }`。
- `MeetingDetailSummaryView` props: `{ meetingId: string, meeting: { title, created_at, status } }`。
- `Workspace` props 縮減為 `{ playbook, transcript, advisor }`（移除 `layout`）。
- 新 CSS 變數 `--detail-header-h`（從 wrapper 算出）、`--mini-player-h`（從 mini-player 高度算出），用 inline style 或 layout effect 注入；fallback 值寫在 CSS。

**Failure modes**

- `meeting === null`：MeetingHeaderBar 不渲染，仍顯示「載入中」文字；tabs 不可點。
- `meeting.attachments` undefined：附件 badge 顯示 `0`。
- `meeting.tags` undefined / 空陣列：標籤 menu 項仍可點開（dialog 內顯示空狀態 + TagPicker）。
- ASR Provider popover 在沒有 provider 列表時顯示 loading skeleton（沿用 `<AsrProviderSelector>` 既有錯誤處理）。
- Recording mode menu 項：當 `status !== "scheduled" || phase !== "idle"` 時整項從 menu 隱藏（不是 disabled），避免讓使用者以為「點得到但不能用」。
- Reduced-motion：tab 切換沿用現有 cross-fade 邏輯（transition duration: 0）。

**Acceptance criteria**

- `bun --filter @meeting-playbook/web test` 全綠（含新元件單元測試 + i18n locale 對齊測試）。
- 手動瀏覽器驗證：
  - MetadataCard 不再出現於 DOM，`data-testid="meeting-metadata-card"` 不存在；改為 `data-testid="meeting-header-bar"`。
  - `data-testid="detail-layout-switcher-slot"` 不再出現；`<LayoutSwitcher>` 模組已刪除。
  - 主視角三欄各自有 `data-testid="meeting-column-playbook|transcript|advisor"`，每欄欄頭含對應 i18n 文案。
  - Overflow menu 開啟後 9 項可見（Recording mode 條件式），點擊各項打開對應 dialog / popover 並可正常操作。
  - 摘要 tab（completed meeting）渲染 `[data-testid="meeting-summary-chat-slot"]` 並含 placeholder 文案。
  - HeadphonesHint 以單行 alert 樣式出現在 header 下方（dual + idle + scheduled 三條件同時成立），可透過 Lucide `X` icon button 關閉。
- Spec sync：`meeting-detail-layout` capability spec 與本次 delta 一致（修改 / 刪除 / 新增 requirements 全部 covered）。

**In scope:**

- `meeting-header-bar.tsx` + 測試（新）
- `meeting-overflow-menu.tsx` + 測試（新）— 含 9c：`asrCurrentLabel` / `modeCurrentLabel` props + sub-hint 渲染
- `meeting-detail-summary-view.tsx` + 測試（新）— 含 9a：3 顆灰階示例 prompt chips（純展示）
- 改寫 `detail.tsx` + 對應測試 — 含 wire 9c 的 current-label 計算
- 改寫 `workspace.tsx` + 測試（移除 layout prop）
- 改 `playbook-pane.tsx` / `transcript-pane.tsx` / `advisor-pane.tsx`：補欄頭結構，內部邏輯不動
  - `transcript-pane.tsx`：9d UI 殼 — chunk type 加 optional `flag_reason?: string`，渲染 `is-flag` highlight + destructive 色 chip
  - `advisor-pane.tsx`：9e UI 殼 — bubble type 加 optional `suggestion_text?: string`，渲染 chip 列，「套用為回覆」呼叫新 prop `onApplySuggestion`；「換一個說法」disabled + tooltip
- 改 `headphones-hint.tsx`：card → inline alert + 9b 完整版 copy（zh-TW + en）+ 允許 wrap 2 行
- 改 `summary-pane.tsx`：不再吃整寬，作為 `MeetingDetailSummaryView` 左欄 child
- 改 `protected-shell.tsx`：不變（檢查 fullBleed 仍 work）
- 刪 `metadata-card.tsx` + 測試
- 刪 `layout-switcher.tsx` + 測試
- 刪 `use-detail-layout.ts` 與相關 localStorage migration 邏輯
- i18n：zh-TW.json + en.json（playbook.heading、欄頭文案、menu 文案、headphones hint 完整 copy、9e chip labels、10a AsrLoadingDialog 文案、10d `recordingPending` 新 key）
- 10a：新建 `asr-loading-dialog.tsx` + 測試；`bun add @elevenlabs/react`；在 detail.tsx 接 `session.phase === "connecting"` 條件渲染
- 10b：在 `transcript-pane.tsx` 內把 chunk 列表用 framer-motion `AnimatePresence` 包覆，新 chunk 從底部 slide-up + fade-in 200ms；不引入 MagicUI 套件
- 10c：新建 `animate-ui/avatar-group.tsx`（copy-paste 模式）；MeetingHeaderBar 在對方那格依名字數量切換 `<Avatar>` / `<AvatarGroup>`
- 10d：新建 `lib/meetings-recording-status.ts` helper + 測試；MeetingHeaderBar 改吃 helper 派生的 4 狀態（available/pending/expired/hidden）

**Out of scope:**

- 摘要右欄 AI 對話功能（只渲染 placeholder + 9a 示例 chips）
- 9d 反對訊號的偵測 / 標記邏輯（後端 LLM pipeline，另開 `feature-transcript-objection-flag`）
- 9e 「換一個說法」的 regeneration endpoint（後端，另開 `feature-advisor-regenerate`）
- backend schema 為 9d 加 `flag_reason` 欄位（先 frontend type only，不動 DB）
- backend schema 為 9e 加 `suggestion_text` 欄位（先 frontend type only，不動 DB）
- **10a：ASR runtime 拉出 process** — backend 仍是 in-process lazy load；dialog 只 hook 既有 `connecting` phase，不細分 download / warm-up 階段。另開 `refactor-asr-runtime-isolation` change。
- **10a：dialog 內進度條 / cancel 按鈕** — 等 backend 能發 download progress 訊號再做
- **10c：backend `counterparty_display_name` schema 改成 array** — 純 client-side 字串拆分；未來改 schema 另開 change
- **10c：對方 avatar 個別圖檔 / 職稱欄位** — 目前所有 avatar 都用首字母占位；未來支援上傳圖另開 change
- **10d：backend `recordings_ever_existed` 欄位** — 「meeting 完成但從未錄音」與「TTL 過期」目前合併視為 `錄音已過期`；如需分開另開 change
- 三個 pane 內部既有資料 / API / 行為
- 手機端 responsive
- `MeetingAudioMiniPlayer`
- ASR provider 選擇邏輯本身
- recording 模式選擇邏輯本身

## Risks / Trade-offs

- **Risk**: 大幅刪除元件（MetadataCard / LayoutSwitcher / use-detail-layout）可能其他地方還在 import → Mitigation: 全 repo grep 該 export name，並依賴 `bun tsc --noEmit` + 全綠測試集
- **Risk**: 把 8 個 affordance 收進單一 menu 後，使用者第一次找不到「刪除」/「重跑 ASR」 → Mitigation: menu 內加 icon + 文案清楚分群（資料 / 設定 / 危險）；常用的編輯擺第一項
- **Risk**: 三欄高度用 `calc(100vh - …)` 在縮放或 mini-player 顯示/隱藏時抖動 → Mitigation: 用 ResizeObserver 監測 mini-player 元素高度，注入 CSS variable
- **Risk**: 摘要雙欄右欄空著看起來像 bug → Mitigation: 渲染明確 placeholder「摘要對話 · 即將推出」+ 灰階圖示，視覺上是「保留位置」
- **Risk**: 移除 `meeting-detail.layout` localStorage key 後，使用者瀏覽器仍殘留該 key → Mitigation: 純前端 key，殘留不影響任何邏輯（用不到就好），不寫 migration

## Migration Plan

無 DB / runtime migration。

部署：純前端 build；deploy 後使用者 reload 即取到新 UI。`meeting-detail.layout` localStorage key 殘留在使用者本機無害，留待自然失效。

Rollback：revert commit。
