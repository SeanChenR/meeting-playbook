# ADR-0028: Qwen3-ASR-1.7B replaces VibeVoice as the secondary ASR provider

- **Status**: Accepted
- **Date**: 2026-05-10
- **Decider**: Sean

## Context

ADR-0005 chose the pluggable `ASRProvider` Protocol so a second engine can drop
in alongside `WhisperProvider`. The original plan (Issue #3 spike → Issue #13
implementation) was VibeVoice as that second provider — partly because it lived
in the same family as the planned Vertex Gemini stack and partly for multimodal
optionality.

Two things changed before that path was started:

1. **Slice 6 + 7 production use** showed Whisper `large-v3-turbo` zh-TW accuracy
   is OK but not great in B2B meeting audio (typos on names, slang). The
   bar to beat is Whisper itself, not "anything that works".
2. **Will Huang (台灣社群保哥) published MLX-packaged variants** of several
   Mandarin-friendly ASR models on HuggingFace under `doggy8088/`, including
   `Qwen3-ASR-1.7B-MLX-{4bit,8bit,bf16,fp16}`. Apple Silicon native (MLX)
   means the runtime path is shorter than `faster-whisper`'s
   CTranslate2-on-Metal hybrid.

A short evaluation against the published benchmarks settled it:

| Benchmark | Whisper Large v3 | Qwen3-ASR-1.7B |
| --- | --- | --- |
| Mandarin WenetSpeech `meeting` (the actual use case) | 19.11 WER | **5.88 WER** (3.2× better) |
| Mandarin AISHELL-2 | 5.06 | **2.71** (1.9× better) |
| Cantonese CV-yue | 16.23 | **7.57** |
| English Librispeech `other` | 3.97 | 3.38 |
| Traditional Chinese (zh-TW) explicit support | ✓ | ✓ (listed among 30 languages) |

The `meeting` benchmark — the one where Whisper currently lands at 19.11 WER —
is the dataset closest to what we actually run through this app.

VibeVoice was rejected because (a) it is primarily a TTS / voice-cloning model
with an unproven ASR pathway and no published Mandarin meeting WER, and
(b) Qwen3-ASR-1.7B's published numbers and MLX packaging remove the need for
a spike at all.

## Decision

Adopt **Qwen3-ASR-1.7B (MLX-8bit by default)** as the second `ASRProvider`
implementation, replacing the VibeVoice plan. The runtime path is the
`mlx-lm` / `mlx-whisper` style toolchain on macOS (the only target per
ADR-0003); model is downloaded from HuggingFace on first use.

The existing `meeting.asr_provider` column (Slice 3) keeps its shape; allowed
values become `"whisper" | "qwen3"` going forward. The per-meeting selector UI
arrives with the integration slice (former Issue #13).

## Consequences

- **Issue #3** (VibeVoice runtime spike on M3 Pro): closed without delivery.
  The MLX 8bit model is ~2.5 GB on disk; two parallel instances ≈ 5 GB which
  fits comfortably on the M3 Pro 18 GB target machine.
- **Issue #13** (originally "VibeVoice ASR provider + per-meeting selector"):
  retitled to "Qwen3-ASR provider + per-meeting ASR selector". The work shape
  is the same — implement an `ASRProvider`, wire a per-meeting toggle, default
  remains Whisper for backward compatibility on existing meetings.
- New runtime dependency on the MLX toolchain (`mlx`, `mlx-lm` or
  `mlx-whisper`, depending on the loader script that ships in the
  `doggy8088/Qwen3-ASR-1.7B-MLX-8bit` repo). Backend `pyproject.toml` adds
  these when Issue #13 lands.
- Documentation: this ADR supersedes the VibeVoice mentions in PRD comments
  and Issue #1 (PRD). Update Issue #1's "ASR providers" section in a
  follow-up edit.

## Alternatives considered

- **Keep VibeVoice**: rejected — no published Mandarin meeting WER, and the
  family has shifted toward TTS/voice-cloning, not ASR.
- **Use Breeze-ASR-26 (also from doggy8088)**: rejected — that model is
  fine-tuned for Taiwanese Hokkien (台語) speech with Mandarin character
  output. Sean's B2B meetings are in 國語 Mandarin, so the specialisation is
  the wrong direction.
- **Stay on Whisper as the only provider**: rejected — Sean already flagged
  that zh-TW accuracy is the weak link, and the 3.2× WER gap on the meeting
  benchmark is decisive.
