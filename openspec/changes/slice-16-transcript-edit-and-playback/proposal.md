> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/19
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16

## Why

目前 transcript chunk 是唯讀，ASR 偶爾錯字使用者只能忍受；同時雖然 recording WAV 保留 30 天，卻沒辦法在 meeting detail 頁面把任何一段聽回去。S16 解掉兩個 UX 漏洞：讓 chunk 可內嵌編輯文字、讓每個 chunk 對應的音訊片段可單獨重播，並提供持久 mini-player 控速度與切段。

## What Changes

- 既有 `recording` 表加 `started_at TIMESTAMPTZ NOT NULL`（recording 第一個 sample 的 wall-clock）；新 Alembic migration 上線同時 backfill 既有 row 為 `created_at`
- 新 `AudioRangeServer`（deep module）：解析 16kHz mono 16-bit PCM WAV header、把 `(start_second, end_second)` 轉成檔案 byte offset、依 HTTP `Range` 回 `206 Partial Content`，並在 recording 過期（`deleted_at IS NOT NULL`）時拒絕
- 新 endpoint `GET /api/meetings/{id}/recordings/{recording_id}/audio`：支援 `Range`，Chrome / Safari `<audio>` 元素可直接餵
- 新 endpoint `PATCH /api/meetings/{id}/transcript_chunks/{chunk_id}`：僅允許更新 `text`，speaker / 時間戳 / asr_provider_used 一律 immutable
- 新 `<TranscriptChunkRow>` hover 顯示 ▶ 與 ✎ 兩按鈕；編輯模式 inline；按 ▶ 透過 mini-player 播該 chunk 對應音訊片段
- 新 `<MeetingAudioMiniPlayer>` 黏在 meeting detail 頁面底部：play / pause / 上一段 / 下一段 / 速度切換（0.5x / 0.75x / 1.0x / 1.25x / 1.5x / 2.0x）
- Speaker-aware playback：dual-channel 模式依 chunk speaker (`me` / `counterparty`) 選對應 stream WAV；single-channel 模式只有一個 recording
- Recording 過期（`deleted_at IS NOT NULL`）→ ▶ 按鈕 disabled + tooltip 顯示「錄音已過 30 天保留期」/ "Recording exceeded the 30-day retention window"
- 新環境變數 `AUDIO_RANGE_MAX_BYTES`（單次 Range request 最大 byte 數，default 2 MiB）寫入 `.env.example`
- i18n：新 `transcript.chunk.edit.*` 與 `meeting.detail.audioPlayer.*` 命名空間雙 locale 同步
- 使用者可自訂 single-channel `speaker_cluster_<N>` 的顏色：提供 5 個預定 scheme（`default` 即現有 6 hue 調色板、`vivid`、`pastel`、`high-contrast`、`grayscale`）+ per-cluster override；資料寫 `localStorage.meeting-playbook:transcript-color-pref`；`me` / `counterparty` 屬於 domain glossary 語意色，不可自訂

### Apply 中後 UX 重設計（post-ingest 2026-05-15）

第一輪 apply 完成後手測發現幾個 UX 問題與整體互動架構需要調整：

- **Mini-player 改成整段 recording 播放**：原本設計是每個 chunk 換 `<audio>` src（per-chunk slice），改成載入**整段 recording WAV**（dual-channel 預設讀 `me` stream，single-channel 讀唯一 recording）；mini-player 含 play / pause / seek bar / 速度切換；chunk-level 的「播放此段」改成 `audio.currentTime = (chunk.started_at - recording.started_at).total_seconds()` 來 seek，不再切 src。`useChunkAudioSource` 簡化為 `pickMeetingRecording(recordings) -> Recording`（只挑一次）。
- **TranscriptChunkRow 接進 transcript-pane**：apply 階段建了 component 但 `transcript-pane.tsx` 還在用 inline 結構，導致使用者看不到 hover 按鈕。本輪把 chunk body 改用 `<TranscriptChunkRow>` 渲染。
- **Chunk action menu 取代 hover ▶/✎**：使用者反饋右鍵 + hover 不直覺。改成**每個 chunk 末尾固定一個 ✎ icon**（永遠可見），點開 dropdown menu（用既有 shadcn-style `<DropdownMenu>` 或新做 popover），含四個動作：「播放此段」/「編輯文字」/「編輯顏色」（cluster 才出現）/「重新命名講者」（cluster 才出現）。原 `SpeakerColorPopover` 變成「編輯顏色」action 的內嵌 sub-popover；右鍵 trigger 移除。
- **Cluster override 改存 hue 數字**：第一輪 apply 把 override 存成完整 oklch 字串，resolver 又把同色當 accent + background tint 來源，導致換色後 chunk 背景與 speaker name 同色不可讀。改成 override = hue（0–360）；resolver 用 hue + scheme 的 `accentL/accentC/bgL/bgC` 算出對比 accent + 淺 background。Custom color input 移除（六個 swatch + reset 已足夠 cover 常見需求）；對 grayscale scheme 改存 lightness ladder index。
- **Cluster speaker rename**：新功能 — 使用者可以在 chunk action menu 「重新命名講者」改 cluster 名（例如「與會者 1」→「Alice」），值寫 `localStorage["meeting-playbook:speaker-labels"] = { [meetingId]: { 1: "Alice", 2: "Bob" } }`；`transcript-pane` render 時 lookup label override 取代預設「與會者 N」。Backend `transcript_chunk.speaker` 不動（仍是 capture-time fact）。Rename 只對 `speaker_cluster_<N>` 生效；`me` / `counterparty` / `speaker_cluster_unknown` 不允許 rename（domain glossary 保護）。

## Non-Goals

- 編輯 speaker / 時間戳 / asr_provider_used / confidence — 只開放 `text`，speaker 等屬於 capture-time fact，editor 不該動
- 跨 chunk 合併或拆分（merge / split） — 留未來 slice，本 slice 維持 chunk 1:1 對應 ASR 輸出
- Transcript edit history / 還原版本 — chunk text 直接覆寫，DB 不存舊版；如需 audit log 留未來 ADR
- 整段會議連續播放跨 chunk auto-advance — mini-player 「下一段」是 explicit click；不做 jukebox 連播（避免使用者誤觸後背景播完整 30 分鐘）
- 音訊波形視覺化 / waveform scrubber — Phase 2 backlog
- 編輯 chunk 後重跑 LLM summary / advisor — text 更新只動 `transcript_chunk.text`，不觸發下游再生成
- 修改 ASR Provider 或 transcript pipeline — chunk 是事後編輯，不影響 capture / ASR 路徑
- Offline ingest recording 的 playback 行為調整 — 走同一個 `GET /audio` endpoint，無特例
- Recording 過期後仍可播（重新拉雲端 / re-upload） — 過期就是過期，UI 純粹 disabled
- 使用者自編 scheme / 從 palette 編輯器調色 — schemes 全部 hard-coded constant，使用者只能挑 scheme 或對個別 cluster 套覆寫色
- 把 `me` / `counterparty` 開放自訂顏色 — 兩者屬於專案 glossary 語意色（紫羅蘭 = me、暖灰 = counterparty），任意換色會破壞 domain meaning
- Color preference 持久化至後端 DB / 跨裝置同步 — `localStorage` 已足夠，跨裝置同步留未來 settings slice
- 為 colorblind safe 自動偵測 / 自動切到 high-contrast — 使用者自行選擇 scheme，不做自動偵測

## Capabilities

### New Capabilities

- `transcript-edit`: chunk text 後編輯 API、UI、validation 規則（speaker / 時間戳 immutable）；同時涵蓋 transcript 顯示層的 cluster color customisation（scheme picker + per-cluster override + `localStorage` 持久化）
- `audio-playback`: AudioRangeServer 邏輯、`GET /audio` endpoint、`<MeetingAudioMiniPlayer>` UI、speaker-aware stream selection、retention-aware disable

### Modified Capabilities

- `meeting-session`: `recording` 表加 `started_at TIMESTAMPTZ NOT NULL` 欄位 + backfill 規則；既有 `recording` row 結構增補一欄、其他欄位不動
- `recording-retention`: 過期 recording（`deleted_at IS NOT NULL`）SHALL 在 `GET /audio` 回 `410 Gone`；retention job 行為本身不變
- `meeting-detail-layout`: meeting detail 頁面底部 SHALL 渲染 `<MeetingAudioMiniPlayer>`；既有三欄 / 三 tab 切換不受影響

## Impact

- Affected specs:
  - New: `openspec/specs/transcript-edit/spec.md`, `openspec/specs/audio-playback/spec.md`
  - Modified: `openspec/specs/meeting-session/spec.md`, `openspec/specs/recording-retention/spec.md`, `openspec/specs/meeting-detail-layout/spec.md`
- Affected code:
  - New: `packages/backend/meeting_playbook/audio_playback/__init__.py`, `packages/backend/meeting_playbook/audio_playback/range_server.py`, `packages/backend/meeting_playbook/audio_playback/wav_header.py`, `packages/backend/meeting_playbook/audio_playback/router.py`, `packages/backend/meeting_playbook/transcript_edit/__init__.py`, `packages/backend/meeting_playbook/transcript_edit/router.py`, `packages/backend/alembic/versions/0009_add_recording_started_at.py`, `packages/backend/tests/audio_playback/test_wav_header.py`, `packages/backend/tests/audio_playback/test_range_server.py`, `packages/backend/tests/audio_playback/test_router.py`, `packages/backend/tests/transcript_edit/test_router.py`, `packages/backend/tests/test_alembic_recording_started_at.py`, `packages/web/src/components/meeting-audio-mini-player.tsx`, `packages/web/src/components/meeting-audio-mini-player.test.tsx`, `packages/web/src/components/transcript-chunk-row.tsx`, `packages/web/src/components/transcript-chunk-row.test.tsx`, `packages/web/src/components/speaker-color-popover.tsx`, `packages/web/src/components/speaker-color-popover.test.tsx`, `packages/web/src/hooks/use-mini-player.ts`, `packages/web/src/hooks/use-mini-player.test.tsx`, `packages/web/src/hooks/use-transcript-color-pref.ts`, `packages/web/src/hooks/use-transcript-color-pref.test.tsx`, `packages/web/src/lib/transcript-color-schemes.ts`, `packages/web/src/lib/transcript-color-schemes.test.ts`, `packages/web/src/lib/transcript-edit-api.ts`
  - Modified: `packages/backend/meeting_playbook/meetings/models.py`, `packages/backend/meeting_playbook/sessions/router.py`, `packages/backend/meeting_playbook/server.py`, `packages/backend/meeting_playbook/config.py`, `packages/web/src/components/transcript-pane.tsx`, `packages/web/src/routes/meetings/detail.tsx`, `packages/web/src/lib/meetings-api.ts`, `packages/web/src/locales/zh-TW.json`, `packages/web/src/locales/en.json`, `.env.example`, `CONTEXT.md`
  - Removed: (none)
