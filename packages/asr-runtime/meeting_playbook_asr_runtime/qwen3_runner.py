"""Qwen3-ASR runtime — singleton lazy-loaded model + serialised inference.

The runner wraps qwen-asr's `Qwen3ASRModel` behind a tiny async surface so
the HTTP / WebSocket routes don't need to care about model internals:

  * `load()` runs once, off the event loop (asyncio.to_thread). Loads weights
    to CPU first, then `.to(device)` — `device_map=...` triggers
    accelerate's meta-tensor dispatch which fails with
    `NotImplementedError: Cannot copy out of meta tensor` on MPS (verified
    while running the in-process provider before the runtime split).
    See Decision 6 in design.md.
  * `transcribe(...)` serialises inference via an internal `asyncio.Lock`
    so two concurrent backend streams can call it safely without racing
    on shared model state.

The `_load_qwen3_model` module-level function is the only thing tests
monkeypatch — keeping the seam stable means we never need the 5 GB weights
in CI.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Qwen3Config:
    """Runtime config — populated from env vars in `server.py`."""

    model_repo: str = "Qwen/Qwen3-ASR-1.7B"
    device: str = "mps"


@dataclass(frozen=True)
class TranscriptChunk:
    """Transcribed audio chunk emitted by the runner."""

    text: str
    started_at: datetime
    ended_at: datetime


def _load_qwen3_model(config: Qwen3Config) -> Any:
    """Sync model loader. Imports qwen-asr + torch lazily so test mocks can
    patch this seam without needing the 5GB weights on disk."""

    import torch  # noqa: PLC0415  (lazy import is intentional)
    from qwen_asr import Qwen3ASRModel  # noqa: PLC0415

    if config.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS backend not available on this machine")

    # CRITICAL: do NOT pass `device_map=...` here. That triggers
    # accelerate's meta-tensor dispatch which fails on MPS with
    # `NotImplementedError: Cannot copy out of meta tensor`. Load to CPU,
    # then move with `.to(device)` after weights are materialised.
    # See ADR-0027 + design Decision 6.
    model = Qwen3ASRModel.from_pretrained(
        config.model_repo,
        dtype=torch.bfloat16,
    )
    if config.device and config.device != "cpu":
        model = model.to(config.device)
    return model


class Qwen3Runner:
    """Async wrapper around `Qwen3ASRModel`.

    Constructor is cheap (no model load); `load()` actually pulls weights
    and is safe to call concurrently — the internal lock makes the load
    happen at most once per instance.
    """

    def __init__(self, config: Qwen3Config | None = None) -> None:
        self._config = config or _config_from_env()
        self._model: Any | None = None
        self._lock = asyncio.Lock()

    @property
    def model_repo(self) -> str:
        return self._config.model_repo

    @property
    def device(self) -> str:
        return self._config.device

    async def load(self) -> None:
        """Idempotent model load. Safe under concurrent callers."""
        async with self._lock:
            if self._model is not None:
                return
            t0 = time.monotonic()
            logger.info(
                "loading Qwen3-ASR (repo=%s, device=%s) — first run downloads ~5GB",
                self._config.model_repo,
                self._config.device,
            )
            self._model = await asyncio.to_thread(_load_qwen3_model, self._config)
            logger.info("Qwen3-ASR ready in %.2fs", time.monotonic() - t0)

    async def transcribe(
        self,
        audio_bytes: bytes,
        sample_rate_hz: int,
        language_hint: str | None = None,  # noqa: ARG002 (reserved for upstream API)
    ) -> TranscriptChunk:
        """Transcribe one chunk of int16 PCM audio.

        Serialised through the shared `_lock` so concurrent callers don't
        race on the model's internal state. The model itself may still
        chunk-batch internally; this lock is the outermost gate.
        """
        await self.load()
        started_at = datetime.now(UTC)
        async with self._lock:
            assert self._model is not None  # `load()` populated it
            # `transcribe` is upstream qwen-asr's blocking call — push it
            # off the event loop so other tasks can keep running.
            result = await asyncio.to_thread(self._model.transcribe, audio_bytes, sample_rate_hz)
        ended_at = datetime.now(UTC)
        text = ""
        if isinstance(result, dict):
            text = str(result.get("text", "") or "")
        elif isinstance(result, str):
            text = result
        return TranscriptChunk(text=text, started_at=started_at, ended_at=ended_at)


def _config_from_env() -> Qwen3Config:
    """Read runtime config from env vars (see .env.example)."""
    return Qwen3Config(
        model_repo=os.environ.get("ASR_RUNTIME_MODEL_REPO", "Qwen/Qwen3-ASR-1.7B"),
        device=os.environ.get("ASR_RUNTIME_DEVICE", "mps"),
    )


__all__ = ["Qwen3Config", "Qwen3Runner", "TranscriptChunk"]
