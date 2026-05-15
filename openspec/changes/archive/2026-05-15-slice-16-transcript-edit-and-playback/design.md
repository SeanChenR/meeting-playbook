## Context

S11 已經把 recording 30 天 retention 接通，S6+S7 已經把 `recording` row 寫 DB，`transcript_chunk` 也固定有 `started_at` / `ended_at` 兩個欄位（per-chunk wall-clock 起訖）。但目前兩個 UX 缺口：

1. **Transcript 唯讀** — ASR 偶爾錯字（中英文混講、口音 chunk、低 confidence）使用者只能皺眉繼續看，不能修。對 Sean 自己的用法（事後寫 follow-up）很痛。
2. **Recording 雖在但聽不回去** — `me.wav` / `counterparty.wav` 還躺在 disk 上 30 天，但 UI 沒任何 affordance 把該段聽回確認。

S16 解兩個缺口：給 chunk 開放 text 編輯、給每個 chunk 對應的音訊片段做可點播。**關鍵技術風險**是 `AudioRangeServer` 的 byte ↔ second 數學：WAV header 有可變長度（44 bytes 不一定）、PCM block-aligned 截斷（不能切到 sample 中間）、HTTP Range 語義（inclusive / Content-Range / 206 Partial Content）。這條路徑必須走 TDD，PRD 已點名。

`recording` 表目前**只有** `created_at`（DB insert 時間，可能在 finalize 後幾秒），缺一個欄位描述「recording 第一個 sample 對應的 wall-clock」（finalize 結束後 backend 才寫 DB，所以 created_at 永遠 lag 一段時間）。沒有這個欄位的話，`(chunk.started_at - recording.first_sample_wall_clock).total_seconds()` 算不出來。新增 `recording.started_at TIMESTAMPTZ NOT NULL` 並 backfill 既有 row 為 `created_at`（既有資料夠近似，不致命）。

## Goals / Non-Goals

**Goals:**

- Chunk text 內嵌編輯，speaker / 時間戳 immutable。
- 每個 chunk 對應的音訊片段可單獨重播；不需要播完整檔。
- HTTP `Range` 走標準路徑，Chrome / Safari `<audio>` element 直接吃。
- Speaker-aware：dual-channel 場景按 chunk speaker 自動挑對應 stream WAV；single-channel 場景挑唯一 recording。
- Retention-aware：過期 recording 直接 410，UI 同步顯示 disabled + tooltip。
- TDD：`AudioRangeServer` 的 WAV header + byte 數學在實作前先有失敗測試。

**Non-Goals:**

- 編輯 speaker、時間戳、ASR provider、confidence。
- Chunk merge / split。
- Edit history / 還原舊版 chunk text。
- Auto-advance 跨 chunk 連播。
- Waveform 視覺化。
- Edit 後重跑 LLM summary / advisor。
- 修動 ASR / capture pipeline。
- Recording 過期後再恢復播放能力。

## Decisions

### Migration：`recording.started_at TIMESTAMPTZ NOT NULL` + backfill 為 `created_at`

`recording` 既有欄位是 `(id, meeting_id, stream, file_path, bytes, created_at, deleted_at)`，缺一個「第一個 sample 對應的 wall-clock」。新增 `started_at TIMESTAMPTZ NOT NULL`：在 session finalize 時，由 audio capture 模組記錄第一個 sample 寫進 WAV 的瞬間（已存於 capture 內部 `_first_sample_ts`），傳進 `recording_repo.create(...)`。Alembic up：`ADD COLUMN started_at TIMESTAMPTZ`（先 nullable）→ `UPDATE recording SET started_at = created_at WHERE started_at IS NULL`（backfill）→ `ALTER COLUMN started_at SET NOT NULL`。Down：drop column。**Alternative considered**：另開 `recording_metadata` 表存 first_sample_ts ——被否決，多一層 join 拖慢 byte-offset 查詢，欄位本身就屬於 recording 主資料。**Alternative considered**：把 `recording.created_at` 改成「第一個 sample 時間」語意——被否決，會破壞既有 retention 邏輯（retention 用 `created_at` 比 `now() - retention_days`，破口會 leak 30 天的真實意義）。

### `AudioRangeServer` 為 deep module + 純函式 WAV header 解析

分兩層：

1. **`wav_header.py`（純函式 / 無 IO）**：`parse_wav_header(bytes) -> WavHeaderInfo`，回 `(data_offset: int, sample_rate: int, channels: int, bits_per_sample: int, data_bytes: int)`。處理 RIFF / fmt / data chunk，支援標頭 ≥ 44 bytes、容忍 `LIST` 等中間 chunk。
2. **`range_server.py`（business logic）**：`serve_chunk(*, file_path, recording_started_at, start_ts, end_ts, range_header) -> RangeResponse`，把 wall-clock 區間 `(start_ts, end_ts)` 轉成 `start_second / end_second` 相對於 recording，再用 header info 轉成 byte offset，做 HTTP Range parsing（含 `bytes=START-`, `bytes=START-END`, `bytes=-N` 三種語法），回 `(status_code, headers, body_iterator)`。

關鍵 byte math：對 16kHz mono 16-bit PCM（slice-7 已定 invariant），`bytes_per_second = sample_rate * channels * (bits_per_sample // 8) = 16000 * 1 * 2 = 32000 bytes`。`start_byte = data_offset + round(start_second * bytes_per_second)`，需要 align 至 `(channels * bits_per_sample / 8) = 2` 的整數倍（block align）：`start_byte = data_offset + ((round(start_second * bytes_per_second) // block_align) * block_align)`，`end_byte` 用 `ceil(end_second * bytes_per_second)` 並一樣 block-align。回 Range 後 `Content-Range: bytes <start>-<end>/<total>`，`Content-Length: end - start + 1`，body 用 `aiofiles` 限 chunk size = `AUDIO_RANGE_MAX_BYTES` 串流。

**Alternative considered**：用 ffmpeg seek + 即時編碼 mp3 stream——被否決，引入 ffmpeg 外部依賴 + 編碼 latency，本機 WAV 直接 stream byte 在 LAN 已秒回。**Alternative considered**：在 frontend 用 `<audio src=full-wav#t=START,END>` Media Fragment URI——被否決，Chrome / Safari `#t=` 對 WAV 支援不一致且 still 會載整檔，retention disable 也難做。**Alternative considered**：合 wav_header 與 range_server 為單一 class——被否決，WAV header 解析是純函式應該獨立可測，混入 IO / HTTP 邏輯反而降低測試密度。

### `GET /api/meetings/{id}/recordings/{recording_id}/audio` 支援 `Range`，無 `Range` 回 200 全檔

Endpoint 接受 query string `?start=<chunk.started_at iso8601>&end=<chunk.ended_at iso8601>` （optional——若無則整段 recording 都可放），加 HTTP `Range` header（瀏覽器 `<audio>` 元素自動帶）。流程：

1. 載 `recording` row，驗 `meeting.owner_id == X-User-Id`（meeting → recording → owner gated by gateway header）。
2. 若 `recording.deleted_at IS NOT NULL` → `410 Gone` + body `{"error_code": "audio_playback.expired", "message": "..."}`。
3. 若有 `start` / `end` query → 算 wall-clock 區間相對 `recording.started_at` 的 seconds offset；若沒帶就回整檔。
4. 解析 `Range` header；若無 → 200 + full content；若有 → 206 + Partial Content + 上面 byte math 算出的 slice。

Response headers `Accept-Ranges: bytes`、`Content-Type: audio/wav`、`Cache-Control: private, max-age=300`。**Alternative considered**：分兩個 endpoint `/audio` 全檔 + `/audio_slice` 帶 query——被否決，HTTP Range 已是這個語意，分兩個 endpoint 是反 REST。

### Speaker-aware playback：dual 用 chunk.speaker 選 stream WAV、single 用唯一 recording

Frontend `<TranscriptChunkRow>` 按 ▶ 時，從 chunk 找對應 recording 的演算法：

- **Dual-channel meeting**（`recordings` 內有 stream=`me` 與 stream=`counterparty` 兩 row）：依 `chunk.speaker` 字串對映到 stream — `chunk.speaker == "me"` → 挑 me.wav；`chunk.speaker == "counterparty"` → 挑 counterparty.wav；single-channel cluster label（`speaker_cluster_*`）或 `me` 來自 voice enrollment rename → 挑 single-channel 唯一 recording（其實 dual-channel 不會出現 cluster label，但 defensive 回 me）。
- **Single-channel meeting**（`recordings` 只有一 row）：永遠挑那一 row。

Mapping 寫在 frontend hook `useChunkAudioSource(chunk, recordings) -> Recording`。後端 endpoint 本身對 recording_id 是 generic 的——「選哪個 recording」的決策留在前端，後端純粹做 byte serving。**Alternative considered**：後端用 `chunk_id` 自動挑——被否決，session 結束後 frontend 已經有 recordings list，前端直接挑簡單且後端無狀態；同時讓 mini-player 可以「跨多個 chunk 都用同一個 recording 開啟單一 `<audio>` 元素」省 HTTP 連線。

### Retention-aware UI：`deleted_at IS NOT NULL` → ▶ disabled + tooltip

Meeting detail load 時，`GET /api/meetings/{id}` 已含 recordings array（slice-7 起就回）。Frontend 對每個 chunk 用 `useChunkAudioSource` 取對應 recording，若 `recording.deleted_at != null` → `<TranscriptChunkRow>` 的 ▶ button 加 `disabled` + `<Tooltip>` 顯示「錄音已過 30 天保留期」/「Recording exceeded the 30-day retention window」（雙 locale 必備）。後端 `GET /audio` 同時 410 是 defense-in-depth：即使前端 race condition / 使用者複製 URL 也擋住。**Alternative considered**：404 而非 410——被否決，410 Gone 的 RFC 語意「資源曾存在已永久刪除」精確匹配 retention 語意，回 404 會讓使用者誤以為是 bug。

### `<MeetingAudioMiniPlayer>` 黏在 detail 頁面底部，狀態存 zustand store

Mini-player 是 sticky bottom bar（CSS `position: sticky; bottom: 0`），不參與 meeting detail 三欄/三 tab 切換邏輯（per `meeting-detail-layout` Modified）。內部 `<audio>` 元素 + 顯式 control（play / pause / prev / next / speed dropdown）。狀態（current chunk_id、playback rate、playing flag）存進新 zustand store `useMiniPlayerStore`，因為 chunk row 按 ▶ → mini-player 接管播放 / 換段，是 cross-component 通訊。speed options `[0.5, 0.75, 1.0, 1.25, 1.5, 2.0]`，存使用者 last-pick 至 `localStorage.miniPlayerRate`（default 1.0）。Prev/Next 對「同一 meeting 的所有 chunk 依 `started_at` 排序」做 index ±1；到頭/到尾按鈕 disabled。**Alternative considered**：直接用 React Context 不開 zustand——被否決，現有專案已用 zustand（layout store / settings），多開 store 比走多重 context 直觀；同時 mini-player 邏輯獨立易測。

### `PATCH /api/meetings/{id}/transcript_chunks/{chunk_id}` 只允許 `text`

Request body `{"text": "<new_text>"}`。Server 驗：
1. `meeting.owner_id == X-User-Id`。
2. `chunk.meeting_id == path_meeting_id`。
3. `text` 是 string、`1 <= len(text) <= 10000`。
4. 任何不在 allow-list 的 field（如 `speaker`、`started_at`、`asr_provider_used`）出現在 body → 422 `transcript_edit.immutable_field` 不嘗試靜默忽略。

回 `200 { "id": ..., "text": ..., "updated_at": ... }`。`transcript_chunk` row 加新欄位 `text_edited_at TIMESTAMPTZ NULL`（追加 column，per `meeting-session` Modified 但 ADR 範圍小到不需另開 ADR）；用 `text_edited_at IS NOT NULL` 判斷「使用者改過」（UI 可標 ✎ icon 提示）。

**Alternative considered**：開放 PATCH `speaker`——被否決，speaker 是 capture-time fact，後 voice-enrollment slice 又加了 rename 邏輯，重複 source of truth 會打架。**Alternative considered**：開放 PUT 全 row——被否決，PATCH text-only 表達能力比 PUT 嚴格易守。

### Cluster color customisation：預定 5 scheme + per-cluster override + `localStorage` 持久化

Transcript pane 既有的 `_CLUSTER_HUES = [300, 150, 30, 240, 90, 0]` 是「Default」scheme。S16 把這份 palette 通用化成 5 個 hard-coded scheme，並讓使用者在 transcript 內右鍵（或行動裝置 long-press）speaker name 開 popover 套個別 cluster override。`me` / `counterparty` 屬於 domain glossary 語意色（紫羅蘭 / 暖灰），popover 對這兩個 speaker 不顯示，避免破壞 domain meaning。

**Scheme constants**（寫在 `packages/web/src/lib/transcript-color-schemes.ts`，全部 6-entry 的 hue 陣列）：

- `default`: `[300, 150, 30, 240, 90, 0]` — 與既有 transcript-pane 行為一致，紫 / 綠 / 橘 / 藍 / 黃綠 / 紅。
- `vivid`: `[330, 170, 50, 210, 110, 10]` — 整體 chroma 偏高（`oklch(0.62 0.24 <hue>)`），accent 色更飽和。
- `pastel`: `[320, 160, 40, 230, 100, 5]` — 低 chroma 柔色（accent 用 `oklch(0.78 0.08 <hue>)`、background tint 用 `oklch(0.96 0.04 <hue>)`），印刷友善。
- `high-contrast`: `[280, 130, 25, 215, 95, 355]` — 鄰位 hue 差 ≥ 65°，accent lightness 拉低（`oklch(0.42 0.20 <hue>)`），符合 WCAG 對 non-text colour 的視覺分離建議。
- `grayscale`: 6 個 `null` hue + 預定 lightness ladder `[0.72, 0.58, 0.45, 0.32, 0.85, 0.20]`；accent 與 background 都不帶 chroma（`oklch(<L> 0 0)`），給黑白印刷 / 強 color vision deficiency 使用者使用。

Scheme module 對外暴露 `TRANSCRIPT_COLOR_SCHEMES`（id → `{ hues: (number|null)[], lightness?: number[] }` 的 readonly map）與 `TRANSCRIPT_COLOR_SCHEME_IDS = ["default", "vivid", "pastel", "high-contrast", "grayscale"] as const`。`scheme: SchemeId` 為這個 union。Scheme 列表是常數，**不允許**運行期增刪。

**Pref storage**：`packages/web/src/hooks/use-transcript-color-pref.ts` 用 `useSyncExternalStore` 把 `localStorage["meeting-playbook:transcript-color-pref"]` 對應到 React state。Schema：

```ts
type TranscriptColorPref = {
  scheme: "default" | "vivid" | "pastel" | "high-contrast" | "grayscale";
  overrides: Record<number, string>; // cluster N (1-indexed) -> oklch() / hex string
};
```

Parsing：JSON parse 失敗、`scheme` 不在常數 union、`overrides` 不是 plain object 或 value 不是 `oklch(...)` / `#rrggbb` / `#rgb` 字串 → 回 `{ scheme: "default", overrides: {} }` 預設值（fail-soft，不丟錯）。Write 時 deep-clone 再 `JSON.stringify` 寫回，跨 tab 透過 `storage` event 自動同步。Single-user app，不寫 DB。

**Resolver `_resolveClusterColor(speaker, prefs)`**（在 `transcript-color-schemes.ts` 內，pure function）：

```
_resolveClusterColor(speaker, prefs) -> { background: string; accent: string }

- speaker 命中 cluster regex /^speaker_cluster_(\d+|unknown)$/：
  1. 若 "unknown" → 回 muted 色（沿用既有 `var(--color-muted)` 行為）
  2. 解出 N (1-indexed)。若 prefs.overrides[N] 存在 → 該 override 同時用於 accent 與 background tint（background 走 `color-mix(in oklch, <override> calc(var(--them-tint-alpha) * 1000%), transparent)`）
  3. 否則套 scheme：
     - 一般 scheme：hue = scheme.hues[(N - 1) % 6]，accent = `oklch(<scheme.accentL> <scheme.accentC> <hue>)`，background = `color-mix(in oklch, oklch(<scheme.bgL> <scheme.bgC> <hue>) calc(var(--them-tint-alpha) * 1000%), transparent)`
     - `grayscale`：lightness = scheme.lightness[(N - 1) % 6]，accent = `oklch(<L * 0.7> 0 0)`，background tint = `color-mix(in oklch, oklch(<L> 0 0) calc(var(--them-tint-alpha) * 1000%), transparent)`
- speaker === "me" / "counterparty" → 沿用既有 `var(--color-me)` / `var(--color-them)` 路徑，prefs **完全忽略**
- 其他字串 → fallback 與既有相同（`var(--color-muted-foreground)` accent + transparent background）
```

`transcript-pane.tsx` 內既有 `_chunkBackground` 與 `_speakerAccent` 統一改用 `_resolveClusterColor` 回傳值，刪除原本內嵌的 `_CLUSTER_HUES` 常數（移到 scheme module）。`me` / `counterparty` 分支不動，per 上面語意保留。

**Popover UX**：`<SpeakerColorPopover>` 用 shadcn `<Popover>` + lucide `Palette` icon。Trigger 是 transcript 列上 speaker name `<button>` 的右鍵 (`onContextMenu` preventDefault) 或 long-press（行動裝置 ≥ 500ms `touchstart` + 取消 `touchmove` 觸發）；用 `useLongPress` hook 抽離 long-press 偵測。Popover content：

1. Scheme picker：5 個 radio chip（label 為 i18n `transcript.color.scheme.<id>`），即時 set scheme。
2. Per-cluster swatch grid：6 個預設 hue 對應 swatch（從目前 scheme 算）+ shadcn `<Input type="color">` 自訂；點擊 swatch 等於設 override；點擊 "Reset to scheme color" 鍵 `delete prefs.overrides[N]`。
3. `me` / `counterparty` 點右鍵不開 popover，因為 popover 對這兩個 speaker 整體不掛 listener（component level guard）。

Popover 為 **inline 渲染**（不是頁面層 modal），透過 shadcn `<Popover>` 的 portal 跟 trigger 對齊。狀態完全是 props + `useTranscriptColorPref()` hook 的 setter，不另開 store。

**Alternative considered**：把 schemes 存進後端 `user_preferences` 表——被否決，現階段單機，徒增 DB schema 與 sync 邏輯；scheme 是 hard-coded constant，使用者只挑不編，無 user-content 資料需要保存。**Alternative considered**：開放使用者自編 scheme（命名 + 5 hue 自填）——被否決，scope 失控且 hard-coded 5 個 scheme 已覆蓋常見視覺需求；未來真有需求可單獨開 slice。**Alternative considered**：把 popover 做成獨立 `<Dialog>` modal——被否決，inline popover 對「右鍵那個 speaker name」這個交互更自然，免一次 modal context switch。**Alternative considered**：用 React Context 廣播 prefs——被否決，`useSyncExternalStore` 對 `localStorage` 是最薄的 React 整合方式，且 prefs 寫頻率低（使用者偶爾切），不需要 context 廣播。

**Scope boundary** — In scope：scheme module + resolver pure function、`useTranscriptColorPref` hook（`useSyncExternalStore` + `localStorage` r/w + 跨 tab `storage` event 同步）、`<SpeakerColorPopover>` inline 元件（含 long-press 偵測）、`transcript-pane.tsx` 換用 resolver、i18n 命名空間 `transcript.color.*`。Out of scope：把 prefs 存進後端 DB、跨裝置 sync、自編 scheme 編輯器、自動 colorblind 偵測切換、`me` / `counterparty` 也可自訂。

### env var：`AUDIO_RANGE_MAX_BYTES` default 2 MiB

單一 Range request 至多回 2 MiB（約 64 秒 16kHz mono 16-bit WAV）。瀏覽器 `<audio>` 預設 fetch buffer 約 5–10 秒，2 MiB 給足兩位數秒數覆蓋。若 client 要更多會自動發第二個 Range request（HTTP 標準行為）。寫入 `.env.example` 註解。

## Implementation Contract

- **新 Alembic migration `0009_add_recording_started_at`**：up 加 nullable `started_at TIMESTAMPTZ` → backfill = `created_at` → `NOT NULL`；down 是 drop column。Up/down 可逆，跑 round-trip pytest 確認；既有 recording row 全部有非 NULL `started_at` 等於 `created_at`。
- **新模組 `packages/backend/meeting_playbook/audio_playback/`** 暴露：
  - `WavHeaderInfo` dataclass + `parse_wav_header(bytes) -> WavHeaderInfo`：純函式，IO 由 caller 負責。回 `data_offset / sample_rate=16000 / channels=1 / bits_per_sample=16 / data_bytes`。對非 16kHz mono 16-bit WAV raise `UnsupportedWavFormat`。
  - `compute_byte_range(*, header: WavHeaderInfo, start_second: float, end_second: float) -> tuple[int, int]`：回 inclusive `(start_byte, end_byte)`，block-aligned（block_align=2 bytes for 16-bit mono），夾在 `[data_offset, data_offset + data_bytes - 1]` 範圍內，end < start 時 raise `InvalidRange`。
  - `parse_range_header(value: str, total_length: int) -> tuple[int, int]`：支援 `bytes=A-B` / `bytes=A-` / `bytes=-N`；不合 RFC 語法 raise `MalformedRange`。
  - `AudioRangeServer.serve(*, file_path, recording_started_at, chunk_start, chunk_end, range_header, max_bytes) -> RangeResponse`：deep module，整合 IO + header + Range parse + block-align byte slice + cap `max_bytes`。回 `(status_code: 200|206, headers: dict, body: AsyncIterator[bytes])`。
- **新 endpoint `GET /api/meetings/{id}/recordings/{recording_id}/audio`** at `audio_playback/router.py`：query string `start` / `end` 為 ISO8601 wall-clock optional；header `Range` optional；owner gating 由 `X-User-Id` + meeting / recording 串查驗證。失敗模式：404 `audio_playback.recording_not_found`（recording 不屬於該 meeting）、403 `audio_playback.forbidden`（meeting 非當前 user）、410 `audio_playback.expired`（recording.deleted_at IS NOT NULL）、416 `audio_playback.range_not_satisfiable`（Range 超出檔案邊界）、422 `audio_playback.malformed_range`（Range header 語法錯）。Success：206 + `Content-Range / Accept-Ranges / Content-Type: audio/wav`。
- **新 endpoint `PATCH /api/meetings/{id}/transcript_chunks/{chunk_id}`** at `transcript_edit/router.py`：JSON body `{"text": str}`；只更新 `transcript_chunk.text` 與 `text_edited_at = now()`；reject 其他 field 422 `transcript_edit.immutable_field`；len 0 或 > 10000 → 422 `transcript_edit.invalid_text`。回 200 含更新後 row。
- **既有 `packages/backend/meeting_playbook/sessions/router.py`** finalize 區段：呼叫 `recording_repo.create(...)` 時把 `first_sample_ts` 傳入新欄位 `started_at`（已存於 audio capture 內部 state）。
- **新前端 component `<MeetingAudioMiniPlayer>`**：sticky bottom，含 `<audio>` 元素 + play / pause / prev / next / speed dropdown；狀態走 zustand `useMiniPlayerStore` (`current_chunk_id / playback_rate / is_playing / chunks_sorted`)；rate 存 `localStorage.miniPlayerRate`，6 段速度（0.5 / 0.75 / 1.0 / 1.25 / 1.5 / 2.0）。
- **`<TranscriptChunkRow>` 升級**：hover 顯示 ▶ 與 ✎ 兩 icon button；▶ 對應 recording 過期時 disabled + Tooltip 文案雙 locale；✎ 進入 inline edit mode（`<textarea>` autosize + Save / Cancel button）；Save 呼叫 `PATCH` API，成功後 chunk row 文字更新 + ✎ icon stays（標示已編輯過）。
- **新 hook `useChunkAudioSource(chunk, recordings) -> Recording`**：依 dual / single 邏輯選對應 recording row。
- **`packages/web/src/locales/zh-TW.json` 與 en.json** 同步新增：`transcript.chunk.edit.startEdit / save / cancel / placeholder / errors.invalidText / errors.immutableField`、`meeting.detail.audioPlayer.play / pause / prev / next / speed / chunkExpired / errors.audioFailed`、`transcript.color.scheme.{default,vivid,pastel,highContrast,grayscale}`、`transcript.color.swatch / resetToScheme / customColor / popoverTitle`。
- **新模組 `packages/web/src/lib/transcript-color-schemes.ts`** 暴露：`TRANSCRIPT_COLOR_SCHEME_IDS` `as const`、`TRANSCRIPT_COLOR_SCHEMES` 唯讀 map（每個 entry 含 `hues: (number | null)[]`、optional `lightness?: number[]`、`accentL / accentC / bgL / bgC` 數字）、`type TranscriptColorPref`、`type SchemeId`、純函式 `_resolveClusterColor(speaker, prefs) -> { background, accent }` 與 `parseTranscriptColorPref(raw: string | null) -> TranscriptColorPref`（fail-soft，回 default）。
- **新 hook `packages/web/src/hooks/use-transcript-color-pref.ts`** 用 `useSyncExternalStore` 包 `localStorage["meeting-playbook:transcript-color-pref"]`，暴露 `{ pref, setScheme, setOverride, resetOverride }`；跨 tab `storage` event 觸發 re-render。
- **新組件 `packages/web/src/components/speaker-color-popover.tsx`** 為 shadcn `<Popover>` 包裝：trigger 觸發來自 `<TranscriptChunkRow>` speaker name 右鍵 / long-press；content 含 scheme radio chip × 5、目前 scheme 6 個 swatch、custom `<Input type="color">`、Reset 鍵；對 `me` / `counterparty` 不渲染（caller 在 mount 階段以 speaker 條件分支跳過）。
- **`packages/web/src/components/transcript-pane.tsx` 改寫**：刪除既有 `_CLUSTER_HUES` 常數，改 `import { _resolveClusterColor } from "@/lib/transcript-color-schemes"` 並在 `_chunkBackground` / `_speakerAccent` 之外 expose `useTranscriptColorPref()`；對每個 chunk 用 `_resolveClusterColor(chunk.speaker, pref)` 取色；speaker name 渲染為 `<button>` 並掛右鍵 / long-press handler 開 `<SpeakerColorPopover>`（`me` / `counterparty` 不掛 handler）。
- **`.env.example` + `config.py`** 加 `AUDIO_RANGE_MAX_BYTES`（default `2097152` = 2 MiB），加註解。
- **`CONTEXT.md` glossary** 加「Mini-player」一條（meeting detail 底部 sticky audio player，承擔 chunk-level 重播）；同時加「Transcript chunk edit」一條（chunk text post-edit；speaker / 時間戳 immutable）。

**Scope boundary** — In scope：`recording.started_at` migration、`audio_playback` 模組（wav_header + range_server + router）、`transcript_edit` 模組（router 與 text-only validation）、`<MeetingAudioMiniPlayer>` 與 `<TranscriptChunkRow>` UI、`useChunkAudioSource` hook、speaker-aware stream selection、retention-aware disable、雙 locale i18n、cluster color customisation（5 hard-coded scheme + per-cluster override + `localStorage` 持久化 + `<SpeakerColorPopover>`）。Out of scope：chunk merge / split、edit history、waveform 視覺化、auto-advance 連播、edit 後 LLM 再生成、修改 ASR pipeline、recording 過期復原、使用者自編 scheme、color pref 存後端 DB、自動 colorblind 偵測、`me` / `counterparty` 改色。

## Risks / Trade-offs

- **WAV header 長度可變**（不一定 44 bytes，可能含 `LIST` 中繼 chunk）→ `parse_wav_header` 必須 scan chunks 找 `data` 而非硬 offset 44；TDD 用 librosa 產生的真實 fixture 加合成的 `LIST` chunk fixture 各跑一次。
- **Block-align 漂秒**：16-bit mono block_align = 2 bytes，每 second = 32000 bytes，整除沒問題；但 future 萬一 ASR 改 24-bit 或 stereo 會踩坑——記在 wav_header 內檢查 sample_rate / channels / bits_per_sample，三項其中任一不對直接 `UnsupportedWavFormat`，逼遷移 ADR。
- **Recording.deleted_at race**：retention job 在 `cleanup` 那一刻把 row 標 deleted，但前端可能在 retention 跑前讀了 meeting detail 拿到 `deleted_at = null` 然後按 ▶——後端 `GET /audio` 再驗 deleted_at IS NOT NULL → 410；前端 catch 後把該 chunk row UI 立即標為 expired（同 tooltip 文案）。
- **Mini-player 跨 chunk 換段時 `<audio>` element 重設**：避免 unmount/remount 元素導致 buffer 重 fetch，改用同一個 `<audio>` 元素 + `src` 切到新 Range URL，並 `currentTime = 0`、`play()`；速度切換用 `audio.playbackRate`，不重新請求。
- **`text_edited_at` 加欄位 vs. 純粹 in-place**：加欄位讓 UI 可標「已編輯」icon；trade-off 是 `transcript_chunk` schema 動了一欄。風險可控（NULL default 對既有 row 安全）。
- **`localStorage` schema migration**：未來若 `TranscriptColorPref` 結構變動（例如加 `version` 欄位），既存 pref payload 會解析失敗。`parseTranscriptColorPref` 是 fail-soft 回 default scheme，使用者最差就是 override 還原為 scheme 色——可接受；正式上線後若要破壞性改 schema 再加 `version` 並做轉換。
- **Long-press 與 contextmenu 互動**：iOS Safari 對 long-press 預設會出原生 callout；handler 必須在 `touchstart` 階段 `preventDefault()` 並監控 `touchmove` 取消（移動超過 8px 視為 scroll）；desktop 則用 `onContextMenu` preventDefault。風險是 Safari 對 `touchstart` passive default 的相容性——若無法 cancel 原生 callout，回退為僅 desktop 右鍵啟用 popover，行動裝置改在 speaker name 右側顯示一個 `Palette` icon button 開 popover。

## Migration Plan

- **DB**：Alembic `0009_add_recording_started_at` + `0010_add_transcript_chunk_text_edited_at`（兩個獨立 migration，獨立可 down）。
- **Backfill**：`UPDATE recording SET started_at = created_at WHERE started_at IS NULL`（既有資料近似可接受，誤差 < 5 秒，對 chunk-level 播放無感）。
- **Rollout**：合主 branch 跑 dual-channel + single-channel 各一場確認；mini-player rate 預設 1.0 不會嚇到使用者。
- **Rollback**：`GET /audio` 與 `PATCH /transcript_chunks/...` 由前端 feature flag `AUDIO_PLAYBACK_ENABLED` / `TRANSCRIPT_EDIT_ENABLED` 控制（`.env.example` 兩個 bool，default true）；緊急 off 時前端隱藏 ▶ / ✎，後端 404，不影響既有 meeting CRUD。

## Open Questions

- Mini-player 是否需要鍵盤 shortcut（Space / ←/→）— v1 先以滑鼠按鈕為主，等 dogfood 後再加。
- Edit 後的 chunk 是否需要在 transcript 段落側標示「已編輯」icon — design 採加 `text_edited_at` 欄位先佔位，UI 標示可在後續 polish slice 加。
- `localStorage.miniPlayerRate` 與 settings store 是否要合併（slice-19 settings shell 完整化時）— 暫不阻擋。

## Decisions (post-ingest 2026-05-15 — Apply 中後 UX 重設計)

### Mini-player 改成整段 recording 播放（不再 chunk-by-chunk 切 src）

第一輪 apply 時 `<MeetingAudioMiniPlayer>` 設計成每個 chunk 切 `<audio>.src` 跳到 `/api/.../recordings/<rid>/audio`，依賴 server 把 chunk byte range 切出來。使用者反饋這跟「我要聽整段會議」的心智不合：應該是整個 recording 的播放器，chunk-level 互動則是 seek。

**新行為**：
- Mini-player mount 時挑一個 recording（dual-channel → `me` stream；single-channel → 唯一一個 recording），把 `audio.src = /api/.../recordings/<rid>/audio` 設好就不再變動。
- Chunk row 上「播放此段」action 等於 `audio.currentTime = (chunk.started_at - recording.started_at) / 1000` + `audio.play()`，不換 src，瀏覽器本身會用 Range header 自己抓 byte 段落（backend 的 Range 支援已有）。
- Mini-player 加 seek bar（HTML5 native `<input type="range" max={audio.duration}>` 或自寫 progress bar）+ current time / total time。Prev / Next 改成 seek 到上 / 下一個 chunk 的 `started_at`（仍是 seek，不換 src）。
- `useChunkAudioSource` 改名 `pickMeetingRecording(recordings) -> Recording`：dual → 永遠回 `me` stream；single → 唯一一個 recording。沒有 chunk speaker-aware 分支。

**Alternative considered**：保留 chunk-by-chunk src 切換 + 加全段播放 mode toggle —— 被否決，兩種模式並存增加 player UI 複雜度且使用者價值低（chunk-level 聽 5 秒 vs seek 到該位置體驗近乎相同）。

### Chunk action menu 取代右鍵 popover + hover ▶/✎

第一輪 apply 把 ▶/✎ 放 hover、把「編輯顏色」綁右鍵，使用者反饋兩個問題：(a) hover 在 trackpad / mobile / 大 chunk 列表 scroll 中不直覺；(b) 右鍵跟 OS 原生 context menu 衝突，且 discoverability 差。

**新行為**：
- 每個 chunk row 末尾（`<TranscriptChunkRow>` 右側 flex shrink-0 區）固定一個 `<button data-testid="chunk-action-menu-trigger">` 渲染 ✎ icon，**永遠可見**（不 hover），不 disabled。
- 點 ✎ → 開 dropdown menu（新元件 `<ChunkActionMenu>`，用既有 `Dialog` 等 hand-rolled popover 風格），含最多 4 個 menu item：
  1. **播放此段**（▶ icon）— 永遠出現；recording 過期時 disabled + tooltip「錄音已過 30 天保留期」。Click → `miniPlayerStore.seekToChunk(chunkId)`，內部算 `audio.currentTime = (chunk.started_at - recording.started_at)`。
  2. **編輯文字**（✎ icon）— 永遠出現。Click → 設 chunk 為 inline edit mode（既有 textarea + Save / Cancel）。
  3. **編輯顏色**（🎨 icon）— **只在 `speaker_cluster_<N>`** 出現，`me` / `counterparty` / `speaker_cluster_unknown` 不渲染此 item。Click → 開 inline sub-popover（複用既有 `<SpeakerColorPopover>` 但 trigger 改 prop-driven 而非右鍵）。
  4. **重新命名講者**（rename icon）— **只在 `speaker_cluster_<N>`** 出現。Click → 進 inline rename mode：取代 speaker name 顯示為 `<input>`，提交後寫 `localStorage["meeting-playbook:speaker-labels"]`。
- `<SpeakerColorPopover>` 不再從 transcript-pane 右鍵打開；改由 `<ChunkActionMenu>` 內「編輯顏色」action 控制 open 狀態。`onContextMenu` listener 完全移除。
- `<TranscriptChunkRow>` 簡化：不再 hover 顯示 ▶/✎；改成固定 ✎ menu trigger + 內聯 edit mode（既有）+ inline rename mode（新）。

**Alternative considered**：用 shadcn `<DropdownMenu>` —— 此 repo 已有 `dropdown-menu.tsx`（slice-15 沒用，slice-17 sub-agent 沒用），可以直接重用；採此選項節省一個新元件。

### Cluster override 改存 hue 數字（不再存 full color string）

第一輪 apply 把 swatch 點擊的 `swatchColor.accent`（`oklch(0.55 0.18 150)` 之類深色）直接存進 `overrides[N]` string，resolver 把同個深色當 accent + `color-mix(in oklch, <override> calc(var(--them-tint-alpha) * 1000%), transparent)` 做 background tint。結果在預設 tint-alpha (~0.15-0.2) 下 background 變深綠 → speaker name 也深綠 → 文字被背景吞掉。

**新行為**：
- `TranscriptColorPref.overrides: Record<number, string>` 改成 `Record<number, number>`（hue 0–360）；grayscale scheme 下改存 `lightness * 1000` 編碼（e.g. `720` 代表 0.72），resolver 識別 `>= 360 || negative` 時 fallback default 處理。為避免複雜度直接記號：**grayscale 不接受 override**（popover 在 grayscale 下 swatch 點擊只能切 scheme 不能 override）。
- Resolver `_resolveClusterColor` 處理 override 改用 hue 算 `accent = oklch(scheme.accentL scheme.accentC hue)`、`background = color-mix(in oklch, oklch(scheme.bgL scheme.bgC hue) calc(var(--them-tint-alpha) * 1000%), transparent)`；跟無 override 同邏輯但 hue 來自 user 選的數字。
- Custom color input (`<input type="color">`) 移除 — 不再支援任意 hex。swatch grid 仍是 6 個（scheme.hues 對應），多一個 reset。
- `parseTranscriptColorPref` 更新：parse `overrides` 時驗 value 是 `0 <= n <= 360` 的數字；不符合 → 該 entry 整個丟掉（fail-soft）。

**Alternative considered**：保留 full color string 但 resolver 把 override 當 accent 用、background 改用 scheme 的 bgL/bgC 強制套淺色 —— 被否決，使用者選了「深綠」accent，背景卻是其他色，hue 不一致違反直覺。

### Cluster speaker rename（per-meeting localStorage override）

使用者要能把「與會者 1」改成「Alice」之類。Backend 的 `transcript_chunk.speaker` 是 capture-time fact（pyannote diarization 輸出），不應該被 UI rename 觸動；同時 rename 是「顯示偏好」性質的 client-side state，DB schema 不必膨脹。

**新行為**：
- 新 hook `useClusterSpeakerLabels(meetingId)` 包 `localStorage["meeting-playbook:speaker-labels"]`，schema：
  ```ts
  type LabelMap = Record<string /*meetingId*/, Record<number /*clusterN*/, string /*label*/>>;
  ```
  暴露 `{ labels, setLabel(clusterN, label), resetLabel(clusterN) }`。Label 為 trim 後 ≥ 1 字元、≤ 50 字元；超出範圍直接 fail-soft（不寫）。
- `_speakerLabel(chunk, meDisplayName, counterpartyDisplayName, t)` 既有函式擴 prop 接 `labelOverrides?: Record<number, string>`；當 chunk speaker 命中 `speaker_cluster_<N>` 且 `labelOverrides[N]` 存在時，回傳該 label，否則回 `t("meetings.speaker.cluster", { n })`（既有 fallback）。
- `<ChunkActionMenu>` 在 cluster speaker 上點「重新命名講者」→ 進 inline rename mode：speaker name 切換為 `<input>`（autofocus + select all），Enter 提交 / Esc 取消；提交時呼叫 `setLabel(clusterN, value)`。
- `me` / `counterparty` / `speaker_cluster_unknown` 在 action menu 不顯示 rename item（同 color customization 的保護）。
- 新 i18n keys：`transcript.chunk.actions.{play,editText,editColor,renameSpeaker}`、`transcript.chunk.rename.{save,cancel,placeholder,invalidLength}`。

**Alternative considered**：新 backend column `meeting_cluster_label` —— 被否決，scope 擴張，per-user-per-device 偏好用 localStorage 已足；未來真的要跨裝置同步，可在 settings sync slice 一併處理。**Alternative considered**：允許 rename `me` / `counterparty` —— 被否決，與 domain glossary 衝突；改名走 meeting 既有 `me_display_name` / `counterparty_display_name` 欄位（slice-15 已有 inline edit）。

### Implementation Contract (post-ingest)

- **Frontend `<MeetingAudioMiniPlayer>`** 重寫：載入 `pickMeetingRecording(recordings)` 的單一 `<audio src=...>`；加 seek bar；prev/next 改 seek 到對應 chunk start；`seekToChunk(chunkId)` 公開 API 給 chunk row 呼叫。
- **Frontend `<ChunkActionMenu>`** 新元件：dropdown menu containing 最多 4 個 action items；用 hand-rolled popover（同 `<Dialog>` 風格）或既有 `dropdown-menu.tsx`。
- **Frontend `<TranscriptChunkRow>`** 改寫：移除 hover 顯示邏輯，固定 ✎ trigger + inline edit textarea + inline rename input。
- **Frontend `useClusterSpeakerLabels` hook** + `useTranscriptColorPref` resolver 改用 hue 數字。
- **Frontend `transcript-pane.tsx`** 接入 `<TranscriptChunkRow>` + `useClusterSpeakerLabels`；移除 `onContextMenu` 開 popover 的舊路徑。
- **Acceptance**:
  - Mini-player 載入後 `<audio src>` 等於 `/api/meetings/<id>/recordings/<me-stream-rid>/audio`（dual）或唯一 recording（single）；切 chunk 時 `src` 不變、`currentTime` 變。
  - ✎ menu trigger 固定可見不靠 hover；點開含 2 個（me / counterparty）或 4 個（cluster）action items。
  - Cluster swatch click → `overrides[N]` 是 hue 數字（不是 string）；換色後 speaker name 與 chunk background 對比清晰可讀。
  - Rename input 提交 → localStorage 更新 + transcript 即時 reflect 新 label；無效輸入（空白、>50 chars）→ fail-soft 不寫。
  - 既有 chunk text edit / retention disable / color scheme switch 行為不退化。
