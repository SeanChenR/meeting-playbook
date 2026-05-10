## Context

Slice 6 把整條 in-meeting WebSocket pipe 立起來了 — 麥克風單聲道 → faster-whisper → transcript_chunk → broadcast。但兩個顯眼缺口：

1. **Speaker 一律標 me** — `transcript_chunk.speaker` 欄位 schema 已支援 `me|counterparty`、`recording.stream` 同樣，但實際只有單一 mic stream，違反 ADR-0004（dual-channel capture）+ ADR-0016（binary speaker labels）的設計意圖
2. **UI 三項暫存議題已積到第二個 slice**：detail 頁排版（memory: project_meeting_detail_layout_open）、playbook markdown 渲染（memory: project_playbook_markdown_rendering_deferred）、meetings list calendar 視圖（memory: project_meetings_list_calendar_view） — 繼續延後讓會中體驗持續打折

本 bundle 一次清掉。Slice 6 archive 中已建立的 `AudioCaptureService` / `WhisperProvider` / `SessionService` / `useMeetingSession` / `TranscriptPane` / `CaptureIndicator` 都會被擴充而非重寫。Slice 5 archive 中的 `/calendar` route + `from_calendar` import endpoint + `PlaybookGenerator` 同樣會擴充而非重寫。

`meeting` 表只有 `created_at` / `started_at` / `ended_at`，**缺 `scheduled_at`** — 這是 calendar view 的硬需求，必須在本 slice 補 migration 0004。

## Goals / Non-Goals

**Goals:**

- 雙聲道擷取真正生效：BlackHole 2ch（counterparty）+ system mic（me）兩條獨立 stream，各自走完 capture → ASR → DB → WS frame 路徑
- 兩條 stream 故障域隔離：跑一半某條 stream 故障不拖死整個 session
- Detail 頁支援使用者切換 Stack（上下三）↔ Columns（三欄 30/40/30）並持久化選擇
- Playbook freeform 編輯改成 WYSIWYG（TipTap），但 DB 儲存格式維持 markdown 不變
- Meeting 月/週行事曆視圖；route `/meetings/calendar`；只顯示自己的 meeting，不混 Google Calendar event
- 新增 `meeting.scheduled_start_at` / `scheduled_end_at` nullable 欄位 + /meetings/new 表單可選 + import 自動填入

**Non-Goals:**

- pyobjc / CoreAudio runtime 偵測 Multi-Output Device routing — 用 silence_warning 補位
- 改 playbook DB 儲存從 markdown 變成 HTML / JSON
- Calendar 跨日 meeting 視覺渲染（多日 bar）— MVP 不支援
- Calendar grid 上同時顯示自己 meeting + 未匯入的 Google Calendar event
- Drag-resize columns / autosave / Day view / Agenda view
- 既有 meeting 列的 scheduled_at backfill
- BlackHole stereo 通道分流（左右獨立的源頭）— ADR-0004 已決定 Multi-Output Device 在系統層匯流，本 slice 仍把 BlackHole 整體視為「對方 stream」
- Speaker diarization 單聲道內分多人
- Tactical advisor / 會後 summary / recording cleanup（Slice 8/10/13 各自的 issue）
- Whisper 模型自動下載 UX / 模型下載進度條

## Decisions

### Capture orchestration: two AudioCaptureService instances per stream

`SessionService` 改成持有 `capture_me: AudioCaptureService` + `capture_counterparty: AudioCaptureService` 兩個 instance，**不**重構 `AudioCaptureService` 內部成 multi-stream。理由：

- Slice 6 capture.py 是剛跑通 graceful-shutdown 的穩定狀態，動內部 risk 高
- 兩條 stream 的故障域天然隔離 — multi-stream 內部設計會把兩條的 lifecycle 綁在一起
- 兩個 ASRProvider instance 跟兩個 capture instance 一一對應，整條 per-stream pipeline 對稱
- Slice 12 (VibeVoice) 替換 ASR 時，per-stream provider 注入比共用一個更彈性

`AudioCaptureService.__init__` 改簽名加 `device_name: str | None = None` + `stream_label: Literal["me", "counterparty"] = "me"`（label 只在 emit `AudioChunk` 時帶出去，不影響行為）。Slice 6 的測試 + single-stream 用法不破。

**Alternatives 拒絕：**
- A. 重構 `AudioCaptureService` 收 `streams: list[StreamConfig]` — 更動 Slice 6 全部測試 + 把故障耦合
- 兩條共用一個 `RawInputStream`（多 channel） — BlackHole + mic 是不同 device，sounddevice 不能跨 device 開單一 stream

### WAV persistence: two mono files per meeting

兩個 mono `.wav`：`{RECORDINGS_DIR}/{meeting_id}/me.wav` + `{RECORDINGS_DIR}/{meeting_id}/counterparty.wav`。**不**用 stereo interleaved。理由：

- faster-whisper 吃 mono；stereo 寫入後還是要拆兩個 mono buffer 餵 ASR
- 故障隔離天然 — 一條 stream 死另一條 WAV 照寫
- Issue #9 acceptance 已寫 `{counterparty,me}.wav`
- 兩個 `recording` 列（per-stream）在 Slice 6 schema 已支援；本 slice 只是真正把兩列都寫進去

**Trade-off：** 事後播放體驗略差（要兩個 player 同時放）。Post-MVP 若需要 stereo，加一個 `ffmpeg amerge` script 合成即可，本 slice 不做。

### ASR concurrency: two WhisperProvider instances with parallel warmup

`SessionService` 持有 `Mapping[Stream, ASRProvider]`，per-stream 各注入一個 `WhisperProvider` instance。`connecting` phase 並行 warmup：

```python
await asyncio.gather(
    self.providers["me"].warmup(),
    self.providers["counterparty"].warmup(),
)
```

`WhisperProvider` 新增 `async warmup()` 方法 — 內部叫 `_load_model()`（既有 lazy-load），把首次冷啟提前。**模型 RAM ~3GB（2× large-v3-turbo）在 M3 Pro 18GB 可接受。**

**Alternatives 拒絕：**
- 單一 instance + asyncio.Lock：12 chunks/min × ~6s/chunk = 72s wall-clock per minute → queue 會在 30 分鐘 meeting 裡無限累積
- 單一 instance + thread pool semaphore=2：CTranslate2 真平行性在 Metal 上要實測，賭沒中等於退回 Lock 方案

### Pre-flight check: device-exists only (relaxed)

Pre-flight 唯一檢查：`sounddevice.query_devices()` 中存在名稱含 `"BlackHole"` 且 `max_input_channels >= 2` 的 device。找不到 → 整個 session 拒絕啟動，error frame `error_code: session.no_blackhole_device` + 連 `docs/BLACKHOLE_SETUP.md`。

**不**檢查 macOS 系統 output 是否真的路由到 Multi-Output Device — sounddevice 沒這個 API，要 pyobjc / CoreAudio 才能查，本 slice 不引入新 platform binding。退而以 per-stream silence_warning 補位：BlackHole stream 連續 30s 無聲（既有 silence detection 機制） → broadcast `silence_warning {stream: "counterparty"}`，UI 文案「對方聲音 30s 沒收到，可能是 Multi-Output Device 沒設好」+ link to setup doc。

### Failure isolation: partial fault tolerance during in_progress

兩條 stream 的 lifecycle policy：

- **At connecting**：兩條都要 `start()` 成功；任一條失敗（device 開不了 / 權限被拒） → 整個 session abort + error frame，跟 Slice 6 一致
- **During in_progress**：一條 stream 的 capture task 拋例外（USB 拔掉 / driver 崩潰） → 該條結束、停止對應 ASR worker、broadcast 新 WS frame `stream_stopped {meeting_id, stream, reason}`；另一條 stream 繼續工作；session 不結束（要等使用者按 End）
- **At end**：每條 stream 各自 finalize 自己的 WAV；只有一條 stream 真正寫到資料就只有一個 `recording` 列；UI capture indicator 該格已經是「已停止」灰色

`SessionService` 維護 `active_streams: set[Stream]`；`stream_stopped` 後從 set 移除；當 `len(active_streams) == 0` 時等同 client end_meeting，主動結束 session。

### Device discovery: name pattern with env override

實際 device 解析：

```python
def find_blackhole_device(env_override: str | None) -> int | None:
    devices = sd.query_devices()
    if env_override:
        for i, d in enumerate(devices):
            if d["name"] == env_override:
                return i
        raise NoBlackholeDeviceError(f"env override {env_override!r} not found")
    for i, d in enumerate(devices):
        if "BlackHole" in d["name"] and d["max_input_channels"] >= 2:
            return i
    return None  # pre-flight surfaces this

def find_mic_device(env_override: str | None) -> int:
    if env_override:
        ...
    return sd.default.device[0]  # system input default
```

兩個 env var 都 optional，預設 auto：

- `BLACKHOLE_DEVICE_NAME` — escape hatch for 多 BlackHole 版本（2ch/16ch 並存）
- `MIC_DEVICE_NAME` — escape hatch for 多 mic 不想用系統 default

### TranscriptPane visual: left accent border + display name prefix

每個 chunk 一個 card：

- 左邊 4px 寬的 accent strip（`border-l-4`）
  - counterparty: `border-l-(--color-primary)`
  - me: `border-l-(--color-secondary)` 或 `border-l-(--color-muted-foreground)`（實作時挑能在 dark / light mode 都清楚的）
- 上方一行 small muted prefix line：`{display_name} · {HH:mm:ss}`（`text-xs text-muted-foreground`）
- 內文 body 用預設 `text-foreground`（**不**染色）

排序嚴格依 `started_at` 升冪，**不**按 speaker 分組（對話交錯流）。display name 從 `meeting.counterparty_display_name` / `me_display_name` 取（Slice 5 已正確填入）。

### Capture indicator: two pills side-by-side

Slice 6 的單一 pill 改成兩個並列：

```
[● 林經理 擷取中]  [● Sean 擷取中]
```

每個 pill 對應一條 stream，色票對應 transcript accent（counterparty primary / me secondary）。State 變化：

- `active`：對應色 + 脈動小點
- `silence_warning`：紅色背景 + 紅點 + 「{display_name} 30s 無聲」（counterparty 版本多一行小字 link to BlackHole setup doc）
- `stream_stopped`：灰背景 + 灰點 + 「{display_name} 已停止」
- `ending`：灰 + 脈動

### New WS message type: stream_stopped

`packages/backend/meeting_playbook/sessions/messages.py` 的 Pydantic discriminated union 新增：

```python
class StreamStopped(BaseModel):
    type: Literal["stream_stopped"]
    meeting_id: str
    stream: Literal["me", "counterparty"]
    reason: str  # human-readable，i18n 在前端做
```

加入 `OutboundMessage` union。`silence_warning` 的 schema 也加 `stream: Literal["me","counterparty"]` 欄位（既有 schema 沒這欄，跟著動），前端 reducer 改用 `silenceSinceByStream: Record<Stream, string|null>`。

### Detail page layout switcher: localStorage-persisted Stack/Columns

新 hook `useDetailLayout()` 讀寫 `localStorage["meeting-detail.layout"]`，initial 預設 `"columns"`（寬螢幕主流；個人筆電都夠）。回傳 `[layout, setLayout]`。

新 component `<LayoutSwitcher />` — 兩個 icon button（`⊟` Stack / `▦` Columns），active 高亮。放在 detail 頁 top bar 右上（跟 `← 返回列表` 同一條）。

`detail.tsx` 根據 layout 切結構：

- Stack：現有的 `<Card>...</Card>` `<PlaybookPane>` `<TranscriptPane>` `<AdvisorPlaceholder>` 縱向疊（順序 P→T→A）
- Columns：CSS grid `grid-template-columns: 30% 40% 30%`，三欄並列；上方 meta card 全寬不切

### ProtectedShell fullBleed prop

`<ProtectedShell fullBleed?: boolean = false>`：

- 預設 false → 維持既有 max-width container 居中（list / new / login etc 不受影響）
- true → container 拿掉 max-width，左右 padding 也降到最小（gridded 內容自己 padding）

`detail.tsx` 永遠傳 `fullBleed`（不管 layout 是 Stack 還 Columns，detail 頁全寬）。

### Playbook editor: textarea + react-markdown preview

**Round 2 reversal — 原本的 TipTap WYSIWYG 在窄欄 detail 頁體驗不佳，整批退回 textarea。**

`<PlaybookPane>` 的 freeform tab 結構：
- 內嵌一個小 toggle「編輯 / 預覽」（控制狀態 `freeformView: "edit" | "preview"`）
- `edit` 模式：原本的 `<textarea>` 直接編輯 markdown 原文
- `preview` 模式：唯讀，用 `react-markdown` + `remark-gfm` 渲染；`rehype-sanitize` 擋 `<script>` / `on*` event handler 等危險節點

`packages/web/src/lib/markdown-preview.tsx` 是新的 wrapper：
```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

export function MarkdownPreview({ source }: { source: string }) {
  return (
    <div className="prose prose-sm max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
```

新 i18n keys：`playbook.freeform.editTab` / `playbook.freeform.previewTab`。
刪除：`playbook.toolbar.*` 6 個 key（不再需要）。

**LLM 整合不動：** Slice 5 `PlaybookGenerator` 仍吐 markdown，textarea 直接顯示原文，preview 直接渲染。

**Cleanup：** 刪 `packages/web/src/lib/markdown-editor.tsx` + 對應 test，從 `package.json` 移除 `@tiptap/*` + `tiptap-markdown` deps，從 `src/test-setup.ts` 拿掉 MarkdownEditor mock。

### Migration 0004: scheduled_start_at + scheduled_end_at columns

```python
def upgrade():
    op.add_column("meeting", sa.Column(
        "scheduled_start_at", sa.TIMESTAMP(timezone=True), nullable=True
    ))
    op.add_column("meeting", sa.Column(
        "scheduled_end_at", sa.TIMESTAMP(timezone=True), nullable=True
    ))

def downgrade():
    op.drop_column("meeting", "scheduled_end_at")
    op.drop_column("meeting", "scheduled_start_at")
```

兩欄都 nullable，**不 backfill**。`MeetingRepository.create()` 簽名加兩個 optional kwarg；`list_for_user()` 回傳的 row 多帶兩欄；`/meetings POST` schema 加兩個 optional ISO string 欄位；`/meetings/from-calendar POST` 內部從 Google Calendar event 的 `start.dateTime` / `end.dateTime` 直接寫入。

### Calendar view library: react-big-calendar Month/Week

`packages/web/src/routes/meetings/calendar.tsx`：

- 用 `react-big-calendar` 的 `<Calendar>` + `dateFnsLocalizer`（date-fns Slice 5 已用）
- Views: `["month", "week"]`，default `"month"`
- 切換 view 用內建 `<Toolbar>` 或自製 toolbar（為了配 shadcn 樣式建議自製）
- Events：從 `meetingsListQueryOptions` 拿 `Meeting[]`，過濾出 `scheduled_start_at != null`，map 成 `{ id, title, start, end, resource: meeting }`
- 顏色：`eventPropGetter` 依 `meeting.status` 給 className（`scheduled` 藍、`in_progress` 綠、`completed` 灰），用 Tailwind utility class
- 週起始日：Monday（`localizer` config）
- 「今天」格 highlight：用 `dayPropGetter`
- NULL `scheduled_start_at` 的 meeting 顯示在 calendar 下方折疊 `<Collapsible>`「未排程 Meetings」list

### Calendar route: /meetings/calendar with /calendar → /calendar/import rename

新路由 `/meetings/calendar`（TanStack Router file-based）→ `routes/meetings/calendar.tsx`。

`/meetings` (list 頁) top bar 加按鈕「Calendar 視圖」→ navigate to `/meetings/calendar`；新 calendar 頁 top bar 同樣有「List 視圖」按鈕回去。

**Slice 5 既有的 `/calendar`（從 Google Calendar 一鍵匯入頁）改名 `/calendar/import`：**

- 檔案搬：`packages/web/src/routes/calendar.tsx` → `packages/web/src/routes/calendar/import.tsx`
- TanStack Router 自動偵測新 path
- `home` 頁 / 任何連到 `/calendar` 的內部連結（grep 出來）改成 `/calendar/import`
- i18n keys 不動（`calendar.heading` 之類），純路徑改名

避免 `/meetings/calendar`（「我自己 meeting 的 view」）跟 `/calendar`（「Google import wizard」）兩個概念混淆。

### Calendar event click behavior

- Click 已排程 meeting (event card) → `navigate({ to: "/meetings/$id", params: { id: meeting.id } })`
- Click 空白日期格（`onSelectSlot`） → `navigate({ to: "/meetings/new", search: { date: "YYYY-MM-DD" } })`，新表單預填日期欄位
- Click 未排程 meeting（在折疊 list 裡的 row） → `navigate({ to: "/meetings/$id" })`

`/meetings/new` 表單 `useSearch` 讀 `?date=`，optional 日期欄位 default 該值（時間預設 09:00）。

## Implementation Contract

### Behavior — observable end-state

1. 使用者在 detail 頁按 Start Meeting：BlackHole 找不到 → 立即 error frame `session.no_blackhole_device` + UI 顯示錯誤 + 連 setup doc，meeting status 不前進。BlackHole 存在 + mic 存在 → 兩條 stream 並行 capture，兩個 model 並行 warmup（首次 ~10-25s），WS 收到 `meeting_started`，capture indicator 兩格亮起對應顏色
2. 開會中對方講話：transcript pane 出現新 chunk 帶 counterparty 顏色 accent + display name；自己講話帶 me accent。兩條 stream 在同一個 transcript pane 依時間排序交錯顯示
3. 開會中 BlackHole device 突然不能用（拔 USB 等）：counterparty 的 capture indicator 變灰「{counterparty_display_name} 已停止」，me stream transcript 持續進來；session 不結束
4. 使用者切 detail 頁 layout：右上 icon button 點 ▦ → 三欄（30/40/30）；點 ⊟ → 上下三疊；切換立即生效；reload 維持選擇（localStorage）
5. 使用者編輯 playbook freeform：打字所見即所得（粗體、列表、標題即時渲染），按 Save → DB 存的是 markdown 純文字，下次 mount 還原為相同的視覺呈現
6. 使用者按 `/meetings` top bar「Calendar 視圖」→ 跳 `/meetings/calendar`；月視圖預設；事件按 status 上色；點某 meeting → 進 detail；點空白日 → 進 new 表單，date 預填
7. 使用者進 `/calendar`（舊路由）→ 404 或自動 redirect 到 `/calendar/import`（用後者）
8. import from Google Calendar 後新建的 meeting：DB 中 `scheduled_start_at` / `scheduled_end_at` 已填入 Google event 的時間；calendar 視圖能正確釘到對應日期格

### Interface / data shape

- WS frame `stream_stopped`：`{"type": "stream_stopped", "meeting_id": str, "stream": "me"|"counterparty", "reason": str}`
- WS frame `silence_warning`（**modified**）：原本 `{"type":"silence_warning","meeting_id","since"}` → 新增 `"stream": "me"|"counterparty"` 欄位
- WS frame `transcript_chunk`（已存在 schema 不變）：`speaker` 真實生效兩個值
- DB schema 新欄：`meeting.scheduled_start_at TIMESTAMPTZ NULL`、`meeting.scheduled_end_at TIMESTAMPTZ NULL`
- HTTP `/meetings POST`：request body 加兩個 optional `scheduled_start_at: ISO8601 | null` / `scheduled_end_at: ISO8601 | null`；response 帶這兩欄
- HTTP `/meetings GET` (list)：response item 多兩欄
- HTTP `/meetings/{id} GET`：response 多兩欄
- HTTP `/meetings/from-calendar POST`：response 的 meeting 物件帶上自動填入的兩欄
- env var：`BLACKHOLE_DEVICE_NAME` (str, optional, default unset) / `MIC_DEVICE_NAME` (str, optional, default unset)
- localStorage：`meeting-detail.layout` 值為 `"stack"` 或 `"columns"`，其他值 fallback `"columns"`
- React Router：新 route `/meetings/calendar`；既有 `/calendar` 路徑檔案搬到 `/calendar/import`，舊 path 不保留 redirect（個人專案，bookmark 影響面小）
- Python `AudioCaptureService.__init__(device_name: str | None = None, stream_label: Literal["me","counterparty"] = "me", ...)`
- Python `WhisperProvider.warmup() -> Awaitable[None]`（idempotent；多次呼叫只 load 一次）

### Failure modes

- `session.no_blackhole_device`：pre-flight 找不到 BlackHole device → 整個 session 拒絕啟動 + error frame + WS 關閉
- `session.no_audio_device`：mic 找不到（既有 code）— 沿用 Slice 6 行為
- `session.stream_failed_at_start`：兩條中任一條 `start()` 拋例外 → 整個 session abort
- 跑一半某條 stream 死：broadcast `stream_stopped`，**不** error frame，session 繼續
- 兩條都死（任一條 `stream_stopped` 後 active set 空）→ session 主動結束（finalize WAV，broadcast `meeting_ended`）
- TipTap `setContent` 拋例外（極端 markdown 解析失敗）→ editor 顯示 raw markdown + console error；不擋 save
- localStorage write 拋例外（隱私模式 / quota 滿）→ silently 退回記憶體狀態，不擋使用
- Calendar `/meetings/calendar` 讀 meetings 失敗 → 沿用 list 頁的 error envelope 處理
- Migration 0004 失敗 → Alembic 自動 rollback；既有 meeting 資料不損壞

### Acceptance criteria

每個 Decision 對應的驗證 target：

- 雙 capture：`packages/backend/tests/audio/test_capture_integration.py` 新增 `test_dual_stream_writes_two_files`，跑後 `RECORDINGS_DIR/{meeting_id}/{me,counterparty}.wav` 兩個檔案存在 + 各為 mono
- 雙 ASR：`packages/backend/tests/sessions/test_service.py::test_dual_stream_routes_chunks_per_speaker` mock 兩個 ASRProvider，assert me chunks 走到 me provider、counterparty chunks 走 counterparty provider
- Pre-flight：`packages/backend/tests/sessions/test_router.py::test_no_blackhole_device_aborts_session` mock `find_blackhole_device` 回 None，assert WS 收到 `error: session.no_blackhole_device` + 連線關閉
- 部分容錯：`test_stream_stopped_keeps_session_alive` mock 一條 capture task 中途拋例外，assert WS 收到 `stream_stopped`，另一條 transcript_chunk 仍流入
- WS schema：`test_messages.py::test_stream_stopped_serialization` + `test_silence_warning_includes_stream`
- 雙 WhisperProvider warmup：`test_whisper_provider.py::test_warmup_loads_model_once`
- TranscriptPane 雙樣式：`packages/web/src/components/transcript-pane.test.tsx::test_counterparty_chunk_has_primary_accent` / `test_me_chunk_has_secondary_accent`
- CaptureIndicator 雙 pill：`capture-indicator.test.tsx::test_renders_two_pills_per_stream` / `test_silence_warning_only_affects_one_pill` / `test_stream_stopped_renders_grey_pill`
- Layout switcher：`use-detail-layout.test.tsx::test_persists_to_localstorage` / `test_defaults_to_columns_when_unset`；`detail.test.tsx::test_columns_layout_renders_three_grid_columns` / `test_stack_layout_renders_vertical_order`
- ProtectedShell fullBleed：`protected-shell.test.tsx::test_fullbleed_removes_max_width`
- TipTap editor：`markdown-editor.test.tsx::test_round_trips_markdown_through_editor` / `test_toolbar_renders_six_buttons`
- Migration 0004：`packages/backend/tests/test_alembic_meeting_scheduled.py` upgrade + downgrade
- /meetings POST scheduled_at：`test_router.py::test_create_with_scheduled_times` / `test_create_without_scheduled_times_stays_null`
- /meetings/from-calendar：`test_router.py::test_from_calendar_populates_scheduled_at`
- Calendar view：`packages/web/src/routes/meetings/calendar.test.tsx::test_renders_meeting_in_correct_day_cell` / `test_click_meeting_navigates_to_detail` / `test_click_empty_day_navigates_to_new_with_date_param` / `test_unscheduled_meetings_appear_in_collapsible`
- /calendar 改名：`packages/web/src/routes/calendar/import.test.tsx`（測試檔搬到對應路徑）+ all internal link grep 不再有 `to="/calendar"` (without `/import`)
- BlackHole setup doc 存在：`docs/BLACKHOLE_SETUP.md` 包含 `brew install blackhole-2ch` / Audio MIDI Setup 步驟 / Zoom 等 app 設定 / 常見問題四大段
- i18n drift test：`locales.test.ts` 兩語系 deep-equal 通過所有新 keys

### Scope boundaries

**In scope:**
- 上述 Decisions 列出的所有變更
- BlackHole pre-flight + setup doc
- TipTap WYSIWYG（markdown storage）
- Detail 頁兩種 layout + localStorage 持久化
- Calendar Month + Week 視圖 + 路由改名 + scheduled_at 欄位 + 表單 + import 寫入

**Out of scope:**
- pyobjc CoreAudio routing 偵測
- Stereo WAV 寫入
- Single ASRProvider + concurrency lock 的賭看實作
- TipTap 改 HTML / JSON 儲存
- Drag-resize / autosave / Day view / Agenda view / Calendar 跨日 bar / Calendar 顯示 Google event
- 既有 meeting 列的 scheduled_at backfill
- BlackHole 左右聲道分流獨立 processing
- Speaker diarization
- Tactical advisor (Slice 8) / 會後 summary (Slice 10) / recording cleanup (Slice 13) / VibeVoice (Slice 12)

## Risks / Trade-offs

- [雙 WhisperProvider 同時跑可能在 M3 Pro 18GB 上熱起來導致系統卡頓] → 第一場真實 30 分鐘 meeting 跑完後 Sean 觀察體感；若卡頓嚴重，下個 change 改 thread pool semaphore=2 或退回單 provider + 縮短 chunk 長度
- [TipTap markdown 序列化有 round-trip drift（`*` ↔ `_`、清空白）] → prep notes 場景看不出來；若 Sean 有強烈意見再評估換 library 或改 HTML 儲存
- [Pre-flight relaxed 模式下，Multi-Output Device 沒設好的使用者開會時才知道（30s 後 silence warning）] → 文件 + UI hint 是主要防線；Slice 12 之後若需求強烈再加 pyobjc routing 偵測
- [`/calendar` → `/calendar/import` 改名可能 break 外部 bookmark] → 個人專案、Slice 5 才剛 ship，影響面小；不加 redirect
- [scheduled_at 兩欄 nullable 沒 backfill，既有 imported meeting 進 calendar view 都掉到「未排程」] → Sean 可手動編輯任一筆補上（或 dev 期間直接重 import）
- [Bundle scope 大（預估 25-30 tasks）超過 spectra 15-task 軟限制] → Sean 已知會、grilling 階段已壓縮設計；apply 時可分段做，但 propose 不拆

---

## Round 2 ingest decisions（2026-05-10 smoke-test 後追加）

### Calendar import: filter resource attendees

Google Calendar API 在 `event.attendees[]` 裡同時放真人 + meeting room（resource accounts）。Resources 的特徵：
- `attendee.resource === true`
- 或 `attendee.resourceEmail` 有值
- 或 `email` 結尾為 `@resource.calendar.google.com`

Slice-5 的 `pick_counterparty` 邏輯沒過濾，所以遇到 `Sean (organizer) + 陳尚恩 + 龍貓會議室` 這種事件會挑到「龍貓會議室」當對方（看順序）。

**Fix in `client.py::_event_from_resource`：**

```python
def _is_resource_attendee(a: dict) -> bool:
    if a.get("resource") is True:
        return True
    if a.get("resourceEmail"):
        return True
    email = (a.get("email") or "").lower()
    return email.endswith("@resource.calendar.google.com")

def _event_from_resource(item: dict) -> CalendarEvent:
    attendees_raw = item.get("attendees") or []
    attendees_raw = [a for a in attendees_raw if not _is_resource_attendee(a)]
    attendees = [_format_attendee(a) for a in attendees_raw if a]
    ...
```

`identity.py::pick_counterparty` 邏輯本身不改 — resource 不會出現在 attendees 列表裡了。

**驗證：**
- `tests/calendar/test_client.py::test_event_from_resource_drops_room_accounts` — 餵一個 attendees 含 `{resource: True, displayName: "MCTW - 6/F-6-龍貓 (3)"}` 的事件，assert `event.attendees` 只剩真人
- `tests/calendar/test_identity.py::test_pick_counterparty_skips_room` — 同樣的 input，assert counterparty 是真人不是會議室

### Vite WS proxy: silence post-close write errors

Vite proxy（http-proxy 底層）在 WS upgrade 完成後不再插手，但 close 時 Vite 仍會在 socket 上留 listener。當 server 端先 FIN（end_meeting 後 backend 主動 close WS），Node 拋 `Error: This socket has been ended by the other party` 進 stderr。功能正常，純噪音。

**Fix in `packages/web/vite.config.ts`：**

```ts
server: {
  proxy: {
    "/api": {
      target: "http://localhost:3001",
      ws: true,
      configure: (proxy) => {
        proxy.on("error", (err) => {
          // Suppress benign post-close write errors from WS sessions.
          const msg = (err as Error).message ?? "";
          if (msg.includes("socket has been ended") || msg.includes("ECONNRESET")) {
            return; // swallow
          }
          // eslint-disable-next-line no-console
          console.error("[vite proxy]", err);
        });
      },
    },
  },
},
```

不影響其他 proxy 行為；保留真正的 proxy 錯誤輸出。

**驗證：手動 — `bun run dev`，跑一個完整 session，按 End → console 不再噴 `socket has been ended`。**

### Echo loop UX: detail page headphones hint + setup doc callout

跨硬體 echo cancellation 是大坑（WebRTC AEC 要 native binding 或 sox/scipy 自寫 NLMS filter，且效果視麥克風品質而定）。Sean 選擇 documentation + UX 提醒。

**UI changes：**

新元件 `packages/web/src/components/headphones-hint.tsx`：
- 接 prop `visible: boolean`（detail 頁傳 `meeting.status === "scheduled"` 時 true）
- 渲染 `<Alert>` 樣式 callout，i18n 文案 `meetings.session.headphonesHint`，例如：
  - zh-TW：「⚠️ 講話時建議戴耳機 — 否則麥克風會收到喇叭播放的對方聲音，導致兩條 stream 重疊」
  - en：「⚠️ Headphones recommended — otherwise the mic will pick up speaker output, causing both streams to overlap」
- 永遠顯示（不可關），直到 status 進 in_progress

新元件位置：detail 頁 meta card 內、Start Meeting 按鈕的上方。

**Doc changes：**

`docs/BLACKHOLE_SETUP.md` 開頭加一個 `## ⚠️ Important — Use headphones` 區塊，解釋為什麼，並列「不戴耳機會發生什麼」（兩條 stream 內容雷同、transcript 重複）。原本表格底下的 echo gotcha row 簡化為「see top of doc」。

**驗證：**
- `headphones-hint.test.tsx::test_hint_visible_when_scheduled` / `test_hint_hidden_when_in_progress`
- `detail.test.tsx::test_renders_headphones_hint_above_start_button`
- 手動：訪問 setup doc 應該第一眼看到耳機警告

### Three columns share equal visible height

當前 detail.tsx 三欄 `grid-template-columns: 30% 40% 30%`，但每欄高度自然撐開 → Playbook 短的話高度小、Transcript 長的話 stretch。視覺上左欄縮一塊、中欄拉很長，看起來不平衡。

**Fix：** CSS grid 的 `grid-auto-rows` 不行（grid item 各自高度）；改用：
- 容器加 `h-[calc(100vh-200px)]`（detail 頁 viewport 減 header + meta card 高度）
- 三欄 `<Card>` 加 `h-full` 充滿 grid cell
- 內容 overflow 用 `overflow-y-auto`（每欄獨立 scroll）

`detail.tsx` 在 columns mode 的容器：

```tsx
<div className="grid grid-cols-1 gap-4 lg:grid-cols-[30%_40%_30%] lg:h-[calc(100vh-220px)]">
  <div data-testid="detail-pane-playbook" className="lg:h-full lg:overflow-y-auto"><PlaybookPane .../></div>
  <div data-testid="detail-pane-transcript" className="lg:h-full lg:overflow-y-auto"><TranscriptPane .../></div>
  <div data-testid="detail-pane-advisor" className="lg:h-full lg:overflow-y-auto"><AdvisorPlaceholder /></div>
</div>
```

PlaybookPane / TranscriptPane / AdvisorPlaceholder 內的 `<Card>` 加 `h-full`。

**Stack mode 不變** — 縱向疊在 stack mode 高度自然伸縮才合理。

**驗證：** `detail.test.tsx::test_columns_mode_three_panes_equal_height` — render in columns mode, assert each `data-testid="detail-pane-*"` 容器有 `h-full` 或計算後 boundingClientRect 高度差異 < 1px。

### UI overhaul via ui-ux-pro-max

跑 `ui-ux-pro-max` skill 對整個 web app 做 audit + 提案 design system，然後 apply 到所有 routes。

**Scope：** in scope = 純樣式 + Tailwind token + shadcn variant；out of scope = 業務邏輯重寫、route 重組、新功能。

**Tokens（草案，最終以 ui-ux-pro-max 輸出為準）：**
- 主色（primary）：保留 brand 藍但飽和度下降一階（目前太刺眼）
- 中性色階：6 階灰（從 background → muted → border → input → ring → foreground）
- Spacing scale：4 / 8 / 12 / 16 / 24 / 32 / 48 / 64（限 8 個 token，禁用任意數字）
- Typography pairing：Inter / sans (UI) + Geist Mono / mono (code)；3 個 size scale（xs / sm / base / lg / xl / 2xl）
- Card：subtle border + soft shadow（取代目前 hard 1px border）
- Button：primary / outline / ghost / destructive 4 個變體；同尺寸（h-9）固定 padding；hover state 微妙
- Alert：destructive / warning / info / success 4 個變體；icon + body + 關閉按鈕

**檔案：**
- `packages/web/src/index.css`：替換 Tailwind layer 的 CSS variables (--color-* / --spacing-* / --font-*)
- `packages/web/src/components/ui/{card,button,alert}.tsx`：套新 variants
- 每個 route page：refactor 排版層級、移除 inline arbitrary 數字（如 `mt-[7px]`）改用 token

**Out-of-scope cleanup：** 不重寫 PlaybookPane / TranscriptPane / CaptureIndicator 內部邏輯；只動 className。

**驗證：**
- 既有所有 component test 仍 pass（樣式不影響行為）
- locales test 仍 pass
- 手動 smoke：每個 route 視覺一致、3 欄等高、配色不刺眼、字體統一
