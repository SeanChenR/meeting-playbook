"""WhisperProvider — `faster-whisper` implementation of `ASRProvider`.

Per slice-06 design:
- Constructor stores config but does NOT load the model. First
  `transcribe_chunk` call instantiates `WhisperModel` (~1.5GB download on
  first run) and stores it on the instance; subsequent calls reuse it.
- `faster-whisper` is sync; `transcribe_chunk` wraps the call in
  `asyncio.to_thread` so the WS event loop stays unblocked.
- Audio bytes are interpreted as int16 PCM; we convert to float32 in
  the range [-1.0, 1.0] before handing to faster-whisper.
- Confidence is averaged across returned segments (Whisper exposes
  `avg_logprob` per segment; we expose a coarse 0..1 confidence).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone

import numpy as np
from faster_whisper import WhisperModel

from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.config import get_settings

logger = logging.getLogger(__name__)


def _logprob_to_confidence(avg_logprob: float | None) -> float | None:
    """Map Whisper's avg_logprob (typically -1.0..0) to a 0..1 confidence.

    avg_logprob is the mean log-probability of selected tokens; closer to 0
    is better. We use exp(avg_logprob) which yields a value in (0, 1].
    """
    if avg_logprob is None:
        return None
    try:
        return float(min(max(math.exp(avg_logprob), 0.0), 1.0))
    except (OverflowError, ValueError):
        return None


class WhisperProvider:
    """ASRProvider using faster-whisper. Lazy model load."""

    def __init__(
        self,
        *,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        settings = get_settings()
        self._model_size = model_size or settings.whisper_model_size
        self._device = device or settings.whisper_device
        self._compute_type = compute_type or settings.whisper_compute_type
        self._model: WhisperModel | None = None

    @property
    def name(self) -> str:
        return "whisper"

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            logger.info(
                "Loading Whisper model (size=%s, device=%s, compute_type=%s) — "
                "first run downloads ~1.5GB and may take 1–2 minutes",
                self._model_size,
                self._device,
                self._compute_type,
            )
            t0 = time.monotonic()
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info("Whisper model loaded in %.2fs", time.monotonic() - t0)
        return self._model

    async def transcribe_chunk(
        self,
        audio_bytes: bytes,
        sample_rate_hz: int,
        language_hint: str | None = None,
    ) -> TranscriptChunk:
        started_at = datetime.now(timezone.utc)

        def _sync_transcribe() -> tuple[str, float | None]:
            model = self._ensure_model()
            samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            segments_iter, _info = model.transcribe(
                samples,
                language=language_hint,
                beam_size=5,
                # VAD filter strips silence BEFORE feeding Whisper, which
                # eliminates the well-known hallucinations on silent chunks
                # ("Thank you.", "Продолжение следует...", "C'est parti.",
                # "Subtitles by..."). Keeps the language hint honest too —
                # silence has no language and otherwise drags detection astray.
                vad_filter=True,
                vad_parameters={
                    # Speech segments shorter than 250ms are usually noise.
                    "min_speech_duration_ms": 250,
                    # Min gap between speech segments — keeps utterances together.
                    "min_silence_duration_ms": 500,
                },
                # Each chunk is independent; do NOT carry text from the prior
                # call (which can amplify earlier mistakes across our 10-second
                # boundaries).
                condition_on_previous_text=False,
            )
            inf_t0 = time.monotonic()
            segments = list(segments_iter)
            inf_dt = time.monotonic() - inf_t0
            text = "".join(seg.text for seg in segments).strip()
            logprobs = [seg.avg_logprob for seg in segments if seg.avg_logprob is not None]
            mean = sum(logprobs) / len(logprobs) if logprobs else None
            audio_seconds = len(samples) / max(sample_rate_hz, 1)
            logger.info(
                "Whisper inferred chunk: audio=%.1fs, inference=%.2fs, "
                "segments=%d, text_chars=%d, lang_hint=%s",
                audio_seconds,
                inf_dt,
                len(segments),
                len(text),
                language_hint or "auto",
            )
            return text, _logprob_to_confidence(mean)

        text, confidence = await asyncio.to_thread(_sync_transcribe)
        ended_at = datetime.now(timezone.utc)

        return TranscriptChunk(
            text=text,
            started_at=started_at,
            ended_at=ended_at,
            asr_provider_used=self.name,
            confidence=confidence,
        )


__all__ = ["WhisperProvider"]
