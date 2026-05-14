"""PyannoteProvider — `DiarizationProvider` impl backed by pyannote.audio.

Loads `pyannote/speaker-diarization-3.1` lazily from HuggingFace Hub on the
first `diarize(...)` call (requires `PYANNOTE_AUTH_TOKEN` + accepted gating
terms; see README §3.5). Subsequent calls reuse the cached pipeline.

This is the single `DiarizationProvider` impl in v1.1 (per ADR-0029);
future cloud providers (Google Speech / AssemblyAI) are out of scope until
a future change proposal.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from meeting_playbook.speaker.diarization import (
    DiarizationProvider,
    DiarizationProviderUnavailable,
    DiarizationSegment,
)


logger = logging.getLogger(__name__)


_PYANNOTE_CHECKPOINT = "pyannote/speaker-diarization-3.1"

# Pipeline loader factory — injectable for tests. The real implementation
# defers the heavy `pyannote.audio` import until the first call so importing
# this module never pays the load cost.
PipelineLoader = Callable[[str, str], Any]


def _default_pipeline_loader(checkpoint: str, token: str) -> Any:
    """Load a pyannote diarization pipeline from HuggingFace Hub.

    Returns the `Pipeline` instance; raises on download / auth errors.
    Import is deferred so importing this module is cheap.
    """
    from pyannote.audio import Pipeline  # local import keeps module load light

    pipeline = Pipeline.from_pretrained(checkpoint, token=token)
    if pipeline is None:
        raise DiarizationProviderUnavailable(
            f"pyannote returned None when loading {checkpoint!r}; "
            "verify the HuggingFace token has access and the model "
            "gating terms have been accepted."
        )
    return pipeline


class PyannoteProvider:
    """`DiarizationProvider` implementation using pyannote.audio.

    Construction is cheap — the actual pipeline is loaded on the first
    `diarize(...)` call (slice-12 design "Diarization latency 預算" applies
    to the per-meeting diarize cost; one-time load is amortized over the
    process lifetime).
    """

    def __init__(
        self,
        token: str,
        *,
        checkpoint: str = _PYANNOTE_CHECKPOINT,
        loader: PipelineLoader = _default_pipeline_loader,
    ) -> None:
        if not token:
            raise DiarizationProviderUnavailable(
                "PYANNOTE_AUTH_TOKEN is empty; cannot construct PyannoteProvider"
            )
        self._token = token
        self._checkpoint = checkpoint
        self._loader = loader
        self._pipeline: Any | None = None

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        pipeline = self._ensure_pipeline()
        output = pipeline(str(wav_path))
        annotation = _extract_annotation(output)
        return _annotation_to_segments(annotation)

    def _ensure_pipeline(self) -> Any:
        if self._pipeline is None:
            logger.info(
                "pyannote_pipeline_loading",
                extra={"checkpoint": self._checkpoint},
            )
            self._pipeline = self._loader(self._checkpoint, self._token)
        return self._pipeline


def _extract_annotation(output: Any) -> Any:
    """Adapt pyannote.audio 4.x `DiarizeOutput` to the `Annotation` shape
    `_annotation_to_segments` expects.

    pyannote 4.x's diarization pipeline returns a `DiarizeOutput` dataclass
    with `.speaker_diarization` (may contain cross-talk overlap) and
    `.exclusive_speaker_diarization` (each frame assigned to one speaker).
    Older pyannote versions returned the `Annotation` directly. We accept
    both shapes so the provider stays robust to future API churn.

    Prefers the exclusive variant when available because it pre-satisfies
    the `DiarizationProvider` non-overlap contract without us needing to
    clip downstream.
    """
    if hasattr(output, "exclusive_speaker_diarization"):
        return output.exclusive_speaker_diarization
    if hasattr(output, "speaker_diarization"):
        return output.speaker_diarization
    # Older pyannote: the pipeline returns an Annotation directly.
    return output


def _annotation_to_segments(annotation: Any) -> list[DiarizationSegment]:
    """Convert a pyannote `Annotation` into the `DiarizationProvider`
    contract: list[DiarizationSegment] sorted by start_ms, 1-based cluster_id.

    pyannote emits speaker labels like `"SPEAKER_00"`, `"SPEAKER_01"`...
    We map each label to a stable 1-based int (`SPEAKER_00` → 1) by
    first-seen order within this annotation.
    """
    raw: list[tuple[int, int, str]] = []
    for segment, _, label in annotation.itertracks(yield_label=True):
        start_ms = int(segment.start * 1000)
        end_ms = int(segment.end * 1000)
        if end_ms <= start_ms:
            continue  # defensive: pyannote shouldn't emit empty segments
        raw.append((start_ms, end_ms, label))

    raw.sort(key=lambda triple: triple[0])
    label_to_cluster: dict[str, int] = {}
    result: list[DiarizationSegment] = []
    last_end_ms = 0
    for start_ms, end_ms, label in raw:
        # Enforce the non-overlap contract: if pyannote returns overlapping
        # speech (cross-talk), clip the later segment's start to the prior
        # end so the protocol guarantee holds. This is a deliberately lossy
        # boundary fix — the spec requires monotonically non-overlapping
        # segments for downstream chunk-overlap math to make sense.
        adjusted_start = max(start_ms, last_end_ms)
        if adjusted_start >= end_ms:
            continue
        if label not in label_to_cluster:
            label_to_cluster[label] = len(label_to_cluster) + 1
        result.append(
            DiarizationSegment(
                start_ms=adjusted_start,
                end_ms=end_ms,
                cluster_id=label_to_cluster[label],
            )
        )
        last_end_ms = end_ms
    return result
