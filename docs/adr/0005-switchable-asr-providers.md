# ADR-0005: Switchable ASR providers — Whisper and VibeVoice-ASR

- **Status**: Accepted
- **Date**: 2026-05-06
- **Decider**: Sean

## Context
Two viable local ASR options exist:

- **faster-whisper (large-v3-turbo)** — proven, fast on M3 Pro, weak Chinese-English mixed quality, no built-in diarization (irrelevant given ADR-0004 / ADR-0016).
- **microsoft/VibeVoice-ASR (9B)** — joint ASR + diarization + timestamps, 50+ languages with code-switching, custom hotwords, MIT-licensed. BF16 needs ~18GB (tight on M3 Pro 18GB); quantized variants or HuggingFace Inference are the practical paths.

The user wants both engines available so they can A/B test on real meeting audio.

## Decision
Define an `ASRProvider` interface that both engines implement. The user can switch engines per meeting (or per recording window) from the UI. Future engines (Qwen3-ASR cloud, Gemini Live, Soniox, etc.) plug into the same interface.

VibeVoice-ASR runs locally if a quantized variant works on M3 Pro MPS; otherwise falls back to HuggingFace Inference Endpoint as the cloud backend (still selectable as "VibeVoice-ASR" in the UI).

## Consequences
- A pre-implementation spike validates the VibeVoice-ASR local path (existence of GGUF / MLX quantization, MPS runtime quality).
- Engine choice is persisted per meeting so post-meeting transcript reruns can compare engines on identical audio (made possible by the 30-day recording window — ADR-0020).
- Slightly more abstraction up front, but additive engines become a one-file change.

## Alternatives considered
- **Single engine** — loses the user's ability to evaluate quality on real meetings.
- **Cloud-only ASR (Qwen3-ASR or Gemini Live)** — adds another billing line and contradicts the local-first spirit (ADR-0001).
