## Context

v1.0 MVP 的 in-meeting capture 走 Dual-channel：BlackHole 收對方音、mic 收我方音，**speaker identity 由 stream source 決定**（ADR-0016）。這條路徑在面對面會議崩潰——使用者只開 mic 一個 Recording，整段逐字稿無從區分誰是誰。本 slice 在不破壞既有 Dual-channel 路徑的前提下，加入單聲道的 speaker attribution 能力，並把 attribution 邏輯從 pipeline inline 抽成可替換的 strategy。

既有 `transcript_chunk.speaker` 是 TEXT 欄位、`recording.stream` 也是 TEXT，schema 不需要動。

## Goals / Non-Goals

**Goals**

- 單一 Recording 的會議能產出帶 `speaker_cluster_N` 標籤的逐字稿。
- 既有 Dual-channel 會議行為 100% regression-safe。
- Diarization 走 `DiarizationProvider` interface，鏡像 `ASRProvider`，未來可插入雲端 provider。
- 本機優先：pyannote.audio（HF pretrained）vs Apple Speech Framework 兩個 impl 並存，TDD 用 fixture 比品質與 latency。

**Non-Goals**

- 聲紋登錄與 Me 自動命名（slice 13）。
- Speaker rename UI（slice 13）。
- 雲端 diarization provider（Google Speech / AssemblyAI，列未來 ADR）。
- Dual-channel 內 N 人 diarization——仍維持 ADR-0016 的單側 binary。
- Offline ingest（slice 14）。

## Decisions

### Strategy interface 抽象層

引入 `SpeakerAttributionStrategy` interface（method `assign_speakers(recordings, transcript_chunks) -> list[chunk]`），既有「BlackHole=counterparty / mic=me」邏輯改寫成 `DualChannelStrategy` impl。新 `SingleChannelStrategy` impl 走 `DiarizationProvider`。Pipeline 透過 selector 函式擇一，selector 規則：當 meeting 的 active Recording 只有 1 筆 → SingleChannelStrategy；2 筆（且 stream 為 `blackhole` + `mic`）→ DualChannelStrategy；其他狀況視為 invalid，raise `InvalidSpeakerConfiguration`。**Alternative considered**：在 `runtime.py` 直接 if/else——被否決，因為新 cloud diarization provider 進來時整個 pipeline 又要再改一次。

### v1.1 唯一 diarization provider 為 pyannote

`DiarizationProvider.diarize(wav_path) -> list[DiarizationSegment(start_ms, end_ms, cluster_label)]`。v1.1 唯一 impl 是 `PyannoteProvider`，使用 HuggingFace `pyannote/speaker-diarization-3.1`（需 `PYANNOTE_AUTH_TOKEN`、首次下載 ~300MB）。TDD 用 3 人 ~3 分鐘 fixture 驗收。**Alternative considered**：原本規劃 AppleSpeechProvider 為 offline fallback——被否決，因為 Apple Speech Framework 是 ASR API（語音轉文字），不做 speaker diarization；`SoundAnalysis` 只能做 speech/non-speech 切片，硬上會 silently 回傳單一 cluster，假裝 attribution 但實際沒分人，比拋錯更糟糕。**Alternative considered**：用 `simple-diarizer` / `pyAudioAnalysis` 等第三方 fallback——defer 到未來 ADR，先讓沒 token 走 fail-loud 路徑，避免增加 dep 與品質未知數。雲端 diarization（Google Speech / AssemblyAI）同樣推到未來 ADR。

### Speaker label 命名 `speaker_cluster_N`

`speaker` 欄位在 single-channel 模式下寫成 `speaker_cluster_1`、`speaker_cluster_2`、...（N 由 diarization 輸出的 cluster id 對應，1-based）。Front-end 顯示用「與會者一 / 二 / 三」（i18n 字串 + cluster index → 中文數字）。**Alternative considered**：寫 `Speaker 1` / `與會者一`——被否決，因為 schema 該是 stable identifier、locale-free，UI 才做翻譯。

### Strategy selection 寫在 pipeline 邊界

`SingleChannelStrategy` 在 transcript chunk 寫入前統一 mutate `speaker` 欄位，不在 ASRProvider 內部。**Alternative considered**：ASRProvider 直接吐 cluster——被否決，會把 ASR 與 diarization 兩個關注點耦合在一起，違反 ADR-0005（switchable ASR providers）的純度。

### Diarization latency 預算

Diarization run 在 ASR 完成後一次性對整段 wav 跑（非串流），加在 in-meeting → completed 的轉場 path。p95 預算 **wav 長度的 0.3 倍**（30 分鐘會議 ≤ 9 分鐘 diarize），超過就 log warning，但仍寫入結果。Realtime advisor 不等 diarization、繼續吃當下的 `speaker_cluster_*` 結果。**Alternative considered**：串流 diarization——被否決，pyannote 與 Apple Speech 都不直接支援，會增加維運成本。

## Implementation Contract

- **新模組 `meeting_playbook.speaker`** 暴露：
  - `SpeakerAttributionStrategy` ABC，method `assign_speakers(recordings: list[Recording], chunks: list[TranscriptChunk]) -> list[TranscriptChunk]`，回傳值是 chunk 的 deep copy（不 mutate input）。
  - `DualChannelStrategy(...)`：把既有 `runtime.py` 中對 stream 名稱判斷的邏輯純函式化遷入。
  - `SingleChannelStrategy(provider: DiarizationProvider, threshold_ms: int = 250)`：把 diarization segment 對齊到 chunk（chunk 時段與 segment 時段 overlap 最大者 wins），cluster_label 寫成 `speaker_cluster_{N}`。
  - `DiarizationProvider` ABC，method `diarize(wav_path: Path) -> list[DiarizationSegment]`。
  - `PyannoteProvider`、`AppleSpeechProvider` 兩 impl。
  - `select_strategy(recordings) -> SpeakerAttributionStrategy`：依 recording 數量與 stream 名稱選擇；不符合 dual 也不符合 single 拋 `InvalidSpeakerConfiguration`。
- **既有 `sessions/runtime.py`** 移除 inline 的 BlackHole / mic 判斷，改呼叫 `select_strategy(...).assign_speakers(...)`，回傳結果寫入 DB。
- **新 ADR `docs/adr/0029-hybrid-speaker-attribution.md`** amend ADR-0016：明確記錄 hybrid 策略、pyannote vs Apple Speech 比較結論、ban cloud provider 進 v1.1 的 rationale。
- **`CONTEXT.md`** glossary 新增 `Single-channel mode (面對面模式)` 與 `Speaker cluster (與會者一 / 與會者二 / ...)`；non-goal 改寫為「Multi-speaker diarization 限制於 Single-channel mode；Dual-channel capture 仍為 binary」。
- **`.env.example` + `README.md`** 新增 `PYANNOTE_AUTH_TOKEN` 與首次模型下載步驟。

**Scope boundary** — In scope：`speaker` 模組程式碼、`runtime.py` 改造、ADR、CONTEXT.md、env / docs；real-audio fixture 測試（dual 三場 + single 兩場）。Out of scope：聲紋登錄 / 命名 UI / cloud provider / dual-channel 內 N 人分離 / offline ingest / pyannote 模型 fine-tune。

## Risks / Trade-offs

- **pyannote 首次下載失敗（無 token / 無網路）** → 啟動時 lazy load + 清楚錯誤訊息指向 README；測試走 mocked downloader。
- **Apple Speech Framework 在 macOS Speech 區段切粒度太粗** → ADR-0029 比較階段量化，若 cluster F1 < 0.6 就排除作為 default、保留為 fallback。
- **Strategy mis-selection（dual 會議只剩一個 stream，硬被當 single）** → `InvalidSpeakerConfiguration` exception + ASR pipeline log 與 metric，不靜默走錯路徑。
- **Diarization latency 在長會議拖垮 completed 轉場** → in_progress 期間先把帶 raw cluster id 的 chunk 顯示出來，attribution 在背景跑完才 finalize；UI 用「speaker 分析中」狀態提示。

## Migration Plan

- 無 schema 變更；既有 `transcript_chunk.speaker` 值集從 `{counterparty, me}` 擴成可包含 `speaker_cluster_*`，無 backfill 需求（既有資料皆為 dual）。
- Rollout：先合主 branch、跑 dual 一週確認 regression-safe，再實際拿一場面對面 meeting 驗 single。
- Rollback：把 `runtime.py` 切回呼叫舊邏輯即可（保留一個 feature flag `SPEAKER_HYBRID_ENABLED` default true）。

## Open Questions

- pyannote 與 Apple Speech 何者最終為 default？TDD fixture 跑完比較後在 ADR-0029 寫入；本 slice 不預設立場。
- `SingleChannelStrategy.threshold_ms` 對齊容忍值 250ms 是否足夠？視 fixture 結果再調，調整路徑：常數調 → 重跑 fixture test → 鎖值寫進 ADR-0029。
