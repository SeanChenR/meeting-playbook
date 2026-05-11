"""Qwen3ASRProvider — `qwen-asr` (Qwen/Qwen3-ASR-1.7B) implementation of `ASRProvider`.

Spike conclusion (slice-11 task 1.1):
  * MLX 8-bit conversion (doggy8088/Qwen3-ASR-1.7B-MLX-8bit) was abandoned —
    the model card's custom `qwen3_asr_mlx.py` helper is incompatible with
    every installable mlx loader (mlx-lm / mlx-whisper / mlx-vlm) without
    deep, fragile shimming. Five spike rounds failed.
  * Upstream `qwen-asr` PyPI package ships `Qwen3ASRModel.from_pretrained`
    with a clean `model.transcribe(audio=...)` API. Despite no MPS docs,
    it runs cleanly on Apple Silicon via `device_map="mps"`.
  * Trade-off: ~5 GB FP16 model per instance instead of ~2.5 GB 8-bit MLX
    (10 GB for two streams on M3 Pro 18 GB — still inside budget).
  * Speed: MPS is slower than MLX 8-bit but acceptable for the meeting use
    case (chunks are 10s; inference budget is the chunk cadence).

Design parallels `WhisperProvider`:
  * Constructor stores config; does NOT touch the model.
  * `warmup()` is idempotent + lock-protected so concurrent callers don't
    double-load the ~5 GB model.
  * `transcribe_chunk()` wraps the sync `model.transcribe()` call in
    `asyncio.to_thread` so the WS event loop stays unblocked.
  * Audio bytes are interpreted as int16 PCM (Slice 7 capture format),
    converted to a float32 numpy buffer in [-1, 1] before handoff.

Confidence: `qwen-asr` does not expose token logprobs — `confidence` stays None.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from meeting_playbook.asr.base import TranscriptChunk

logger = logging.getLogger(__name__)

MODEL_REPO = "Qwen/Qwen3-ASR-1.7B"
DEFAULT_DEVICE = "mps"
DEFAULT_LANGUAGE = "Chinese"  # advisory; provider passes None when language_hint is None


@dataclass(frozen=True)
class Qwen3Config:
    """Construction config for Qwen3ASRProvider.

    Frozen so two providers (me-stream + counterparty-stream) can share an
    identical config without surprise mutation.
    """

    model_repo: str = MODEL_REPO
    device: str = DEFAULT_DEVICE
    max_inference_batch_size: int = 1
    max_new_tokens: int = 256


class Qwen3UnavailableError(RuntimeError):
    """Raised when qwen-asr or torch is missing, or MPS/CUDA is unavailable."""


def _load_qwen3_model(config: Qwen3Config) -> Any:
    """Sync model loader. Imports qwen_asr lazily so test mocks can patch it."""
    try:
        import torch
        from qwen_asr import Qwen3ASRModel
    except ImportError as exc:
        raise Qwen3UnavailableError(
            f"qwen-asr or torch missing: {exc}; run `uv sync` in packages/backend"
        ) from exc

    if config.device == "mps" and not torch.backends.mps.is_available():
        raise Qwen3UnavailableError("MPS backend not available on this machine")

    return Qwen3ASRModel.from_pretrained(
        config.model_repo,
        dtype=torch.bfloat16,
        device_map=config.device,
        max_inference_batch_size=config.max_inference_batch_size,
        max_new_tokens=config.max_new_tokens,
    )


class Qwen3ASRProvider:
    """ASRProvider using upstream qwen-asr on Apple Silicon (MPS). Lazy model load."""

    def __init__(self, config: Qwen3Config | None = None) -> None:
        self._config = config or Qwen3Config()
        self._model: Any | None = None
        self._warmup_lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "qwen3"

    async def warmup(self) -> None:
        """Idempotent: load the qwen-asr model if not already loaded.

        Safe to call concurrently — an internal lock serialises racing callers
        so the (slow, blocking) loader runs at most once. Slice-07
        SessionService awaits two providers' warmup() in parallel via
        `asyncio.gather` so the cold-start cost (one ~10-25s model load) does
        not double when both streams are running.
        """
        async with self._warmup_lock:
            if self._model is not None:
                return
            await asyncio.to_thread(self._ensure_model)

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        t0 = time.monotonic()
        logger.info(
            "Loading Qwen3-ASR-1.7B (repo=%s, device=%s) — first run downloads ~5GB",
            self._config.model_repo,
            self._config.device,
        )
        self._model = _load_qwen3_model(self._config)
        logger.info("Qwen3-ASR ready in %.2fs", time.monotonic() - t0)
        return self._model

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        sample_rate_hz: int,
        language_hint: str | None = None,
    ) -> TranscriptChunk:
        started_at = datetime.now(UTC)

        def _sync_transcribe() -> str:
            model = self._ensure_model()
            samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            inf_t0 = time.monotonic()
            results = model.transcribe(
                audio=(samples, sample_rate_hz),
                language=language_hint,
            )
            inf_dt = time.monotonic() - inf_t0
            text = (results[0].text or "").strip() if results else ""
            audio_seconds = len(samples) / max(sample_rate_hz, 1)
            logger.info(
                "Qwen3 inferred chunk: audio=%.1fs, inference=%.2fs, text_chars=%d, lang_hint=%s",
                audio_seconds,
                inf_dt,
                len(text),
                language_hint or "auto",
            )
            return text

        text = await asyncio.to_thread(_sync_transcribe)
        ended_at = datetime.now(UTC)

        return TranscriptChunk(
            text=text,
            started_at=started_at,
            ended_at=ended_at,
            asr_provider_used=self.name,
            confidence=None,
        )


__all__ = [
    "MODEL_REPO",
    "Qwen3ASRProvider",
    "Qwen3Config",
    "Qwen3UnavailableError",
]
