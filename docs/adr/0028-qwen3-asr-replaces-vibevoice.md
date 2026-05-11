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

Adopt **Qwen3-ASR-1.7B** as the second `ASRProvider` implementation,
replacing the VibeVoice plan. The runtime path is the upstream
`Qwen/Qwen3-ASR-1.7B` (FP16) loaded via the official `qwen-asr` PyPI
package on Apple Silicon MPS; model is downloaded from HuggingFace on
first use.

The existing `meeting.asr_provider` column (Slice 3) keeps its shape; allowed
values become `"whisper" | "qwen3"` going forward. The per-meeting selector UI
arrives with the integration slice (former Issue #13).

### Loader spike result (Slice 11, 2026-05-11)

The original plan above ("MLX-8bit by default via `mlx-lm` / `mlx-whisper`")
did not survive contact with reality. Slice 11 ran five spike rounds against
`doggy8088/Qwen3-ASR-1.7B-MLX-8bit`:

1. `mlx-lm` — `ModuleNotFoundError: mlx_lm.models.qwen3_asr`
2. `mlx-whisper` — `TypeError: ModelDimensions.__init__() got an unexpected keyword argument 'architectures'`
3. `transformers` (with `trust_remote_code=True`) — `KeyError: 'qwen3_asr'`
4. `mlx-vlm` + sys.modules-injected custom helper — processor falls back to
   `Qwen2Tokenizer` (no audio support); manual `Qwen3ASRProcessor`
   instantiation works but mlx-vlm's `chat_template`, `stopping_criteria`,
   and `make_streaming_detokenizer` plumbing all reject the custom path.

The MLX 8-bit conversion ships a custom `qwen3_asr_mlx.py` helper that
defines `Model` + `Qwen3ASRProcessor` but no usage example, no glue to
existing MLX loaders, and no end-to-end transcribe entry point.

The spike pivoted to upstream `Qwen/Qwen3-ASR-1.7B` + `qwen-asr` PyPI package
(version 0.0.6) with `device_map="mps"`. This worked first attempt —
`Qwen3ASRModel.from_pretrained(...).transcribe(audio=...)` returns a
structured result with `.text` and `.language` ready to consume.

### Revised runtime plan

- **Loader**: `qwen-asr>=0.0.6` (transitively pulls `transformers==4.57.6`,
  `torch>=2.11`).
- **Model**: `Qwen/Qwen3-ASR-1.7B` (FP16/BF16, ~5 GB per instance).
- **Device**: MPS on Apple Silicon. `qwen-asr` does not document MPS
  support but does not assume CUDA internally.
- **Memory budget**: 5 GB × 2 streams = 10 GB on M3 Pro 18 GB — comfortable.
- **Speed**: MPS is slower than the (unreached) MLX 8-bit path, but
  acceptable: chunks are 10s, inference fits in budget.

If a future MLX loader gains native `qwen3_asr` support — or doggy8088
publishes a working entry point — the swap stays inside `Qwen3ASRProvider`
and `pyproject.toml` (the `ASRProvider` Protocol does not change).

## Consequences

- **Issue #3** (VibeVoice runtime spike on M3 Pro): closed without delivery.
- **Issue #13** (originally "VibeVoice ASR provider + per-meeting selector"):
  retitled to "Qwen3-ASR provider + per-meeting ASR selector". The work shape
  is the same — implement an `ASRProvider`, wire a per-meeting toggle, default
  remains Whisper for backward compatibility on existing meetings.
- New runtime dependency: `qwen-asr` on the backend. Backend `pyproject.toml`
  drops any earlier MLX experiment deps (`mlx-lm`, `mlx-whisper`, `mlx-vlm`,
  standalone `transformers`) — `qwen-asr` brings the right pinned
  `transformers==4.57.6` itself.
- The `doggy8088/Qwen3-ASR-1.7B-MLX-8bit` HF cache (~2.5 GB) downloaded
  during the spike can be deleted; production uses `Qwen/Qwen3-ASR-1.7B`.
- Memory budget shifts from ~5 GB (MLX 8-bit ×2) to ~10 GB (FP16 ×2). Still
  fits on the M3 Pro 18 GB target machine; revisit if a third concurrent
  consumer is ever added.
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
- **MLX 8-bit conversion via `mlx-lm` / `mlx-whisper` / `mlx-vlm`**:
  rejected after Slice-11 spike — see the loader spike result section above.
  No installable MLX loader recognises the `qwen3_asr` `model_type` and the
  custom helper shipped with `doggy8088/Qwen3-ASR-1.7B-MLX-8bit` has no
  working entry point. Revisit if the upstream MLX ecosystem catches up.
