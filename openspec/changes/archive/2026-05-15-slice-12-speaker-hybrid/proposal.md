> GitHub Issue: https://github.com/SeanChenR/meeting-playbook/issues/17
> Parent PRD: https://github.com/SeanChenR/meeting-playbook/issues/16

## Why

面對面會議只有單一 mic 來源，沒有 Dual-channel capture，現有的「BlackHole=counterparty / mic=me」二元 attribution 無法成立，整個逐字稿失去 speaker tag。需要在不破壞既有線上會議路徑的前提下，補上單聲道的 attribution 能力。

## What Changes

- 新增 `SpeakerAttributionStrategy` interface 與兩個 impl：`DualChannelStrategy`（既有邏輯抽出）、`SingleChannelStrategy`（單一 Recording 跑 diarization → `speaker_cluster_N` 標籤）
- 新增 `DiarizationProvider` interface（鏡像 ASRProvider 模式），含 pyannote 與 Apple Speech 兩個 impl
- ASR pipeline 自動依該 meeting 的 Recording 數量切換 strategy；既有 Dual-channel 行為不變
- 新 ADR amend ADR-0016（不 supersede），更新 CONTEXT.md glossary 與 non-goal 描述
- 新環境變數 `PYANNOTE_AUTH_TOKEN` 寫入 `.env.example`

## Non-Goals

- 聲紋登錄 + 自動匹配「Me」（slice 13）
- Speaker rename UI（slice 13）
- 雲端 diarization provider（Google Speech / AssemblyAI 列未來 ADR）
- Dual-channel 內二人以上的 diarization（仍維持 ADR-0016 的單側 binary）
- Offline audio ingest（slice 14）

## Capabilities

### New Capabilities

- `speaker-attribution-strategy`: `SpeakerAttributionStrategy` 與 `DiarizationProvider` interface，含 dual / single 雙模式與兩個 diarization impl 的契約。

### Modified Capabilities

- `meeting-session`: 逐字稿 pipeline 現在依該 meeting 的 Recording 數量選用 strategy；單一 Recording → single-channel mode。

## Impact

- Affected specs:
  - New: `openspec/specs/speaker-attribution-strategy/spec.md`
  - Modified: `openspec/specs/meeting-session/spec.md`
- Affected code:
  - New: `packages/backend/meeting_playbook/speaker/strategy.py`, `packages/backend/meeting_playbook/speaker/diarization.py`, `packages/backend/meeting_playbook/speaker/pyannote_provider.py`, `packages/backend/meeting_playbook/speaker/apple_speech_provider.py`, `docs/adr/0029-hybrid-speaker-attribution.md`
  - Modified: `packages/backend/meeting_playbook/sessions/runtime.py`, `CONTEXT.md`, `.env.example`, `README.md`
  - Removed: (none)
