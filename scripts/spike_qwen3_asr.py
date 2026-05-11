"""Standalone smoke test for the qwen-asr loader path used by Qwen3ASRProvider.

Slice-11 spike conclusion (kept as a runnable reference):
  * Five rounds of MLX-based loaders (mlx-lm / mlx-whisper / mlx-vlm with
    custom helper) all failed to make doggy8088/Qwen3-ASR-1.7B-MLX-8bit
    transcribe a wav.
  * Switching to upstream Qwen/Qwen3-ASR-1.7B + the official `qwen-asr`
    PyPI package + `device_map="mps"` worked first try. ~5 GB FP16 model
    per instance; 10 GB for two streams on M3 Pro 18 GB stays in budget.
  * Production code lives in
    `packages/backend/meeting_playbook/asr/qwen3_provider.py` and uses the
    same `Qwen3ASRModel.from_pretrained(...).transcribe(audio=...)` shape
    this script exercises.

Use this script when:
  * Validating qwen-asr after a `uv sync` on a fresh machine.
  * Reproducing the model-load path outside pytest for hand-debugging.
  * Confirming MPS availability before running the opt-in real-fixture
    test (`MEETING_PLAYBOOK_QWEN3_AVAILABLE=1 pytest tests/asr/...`).

Run from the repo root:
  uv run --project packages/backend python scripts/spike_qwen3_asr.py \
      packages/backend/tests/asr/fixtures/short_speech_zh.wav
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav_path", type=Path)
    args = parser.parse_args()
    if not args.wav_path.exists():
        print(f"ERROR: wav not found: {args.wav_path}", file=sys.stderr)
        return 2

    import torch

    if not torch.backends.mps.is_available():
        print("ERROR: MPS backend not available", file=sys.stderr)
        return 1
    print(f"  torch={torch.__version__}, MPS available={torch.backends.mps.is_available()}")

    from qwen_asr import Qwen3ASRModel

    print("Loading Qwen/Qwen3-ASR-1.7B on MPS (~5GB upstream FP16, first run downloads)...")
    model = Qwen3ASRModel.from_pretrained(
        "Qwen/Qwen3-ASR-1.7B",
        dtype=torch.bfloat16,
        device_map="mps",
        max_inference_batch_size=1,
        max_new_tokens=256,
    )

    print(f"Transcribing {args.wav_path} ...")
    results = model.transcribe(audio=str(args.wav_path), language="Chinese")
    r = results[0]

    print("\n========================================")
    print(f"SUMMARY: LOADER=qwen-asr (MPS, FP16)")
    print(f"SUMMARY: LANGUAGE={r.language}")
    print(f"SUMMARY: TRANSCRIPT={r.text!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
