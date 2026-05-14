"""Tests for `compute_enrollment_embedding`.

Verifies the three spec scenarios under "compute_enrollment_embedding rejects
samples that do not produce a single-speaker embedding":
- Multi-speaker sample → InvalidEnrollmentSample.
- Silent sample (zero-vector embedding) → InvalidEnrollmentSample.
- Valid single-speaker sample → non-empty bytes whose length is divisible
  by 4 (float32) and whose first 4 bytes are NOT all zero.

The pyannote pipeline is never actually loaded — a stub `PyannoteProvider`
returns canned segments + embeddings so these tests run in milliseconds
without network access or the 300MB model download.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from meeting_playbook.speaker.diarization import DiarizationSegment
from meeting_playbook.voice_enrollment.embedding import (
    InvalidEnrollmentSample,
    compute_enrollment_embedding,
)


class _StubProvider:
    """Mimics PyannoteProvider's two-method surface used by
    `compute_enrollment_embedding`: `diarize(wav_path)` returns segments and
    `cluster_embeddings()` returns a `{cluster_id: ndarray}` mapping.
    """

    def __init__(
        self,
        *,
        segments: list[DiarizationSegment],
        embeddings: dict[int, np.ndarray] | None,
    ) -> None:
        self._segments = segments
        self._embeddings = embeddings

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        return list(self._segments)

    def cluster_embeddings(self) -> dict[int, np.ndarray] | None:
        return self._embeddings


def _vec(values: list[float]) -> np.ndarray:
    return np.asarray(values, dtype=np.float32)


def test_single_speaker_sample_returns_float32_bytes() -> None:
    """Valid path: one speaker, non-zero embedding, returns float32 bytes."""
    provider = _StubProvider(
        segments=[
            DiarizationSegment(start_ms=0, end_ms=10_000, cluster_id=1),
            DiarizationSegment(start_ms=10_000, end_ms=20_000, cluster_id=1),
        ],
        embeddings={1: _vec([0.1, 0.2, 0.3, 0.4])},
    )

    result = compute_enrollment_embedding(Path("/tmp/sample.wav"), provider=provider)

    assert isinstance(result, bytes)
    assert len(result) == 16  # 4 float32 values * 4 bytes
    assert len(result) % 4 == 0
    # First 4 bytes correspond to 0.1 (float32), which is NOT zero
    assert result[:4] != b"\x00\x00\x00\x00"


def test_multi_speaker_sample_raises_invalid_enrollment_sample() -> None:
    """Spec scenario: 2+ speakers detected → reject."""
    provider = _StubProvider(
        segments=[
            DiarizationSegment(start_ms=0, end_ms=5_000, cluster_id=1),
            DiarizationSegment(start_ms=5_000, end_ms=10_000, cluster_id=2),
        ],
        embeddings={
            1: _vec([0.1, 0.2, 0.3]),
            2: _vec([0.4, 0.5, 0.6]),
        },
    )

    with pytest.raises(InvalidEnrollmentSample) as excinfo:
        compute_enrollment_embedding(Path("/tmp/sample.wav"), provider=provider)

    assert "2 speakers" in str(excinfo.value) or "speakers" in str(excinfo.value)


def test_silent_sample_raises_invalid_enrollment_sample() -> None:
    """Spec scenario: zero-vector embedding → reject as silent / dropped."""
    provider = _StubProvider(
        segments=[DiarizationSegment(start_ms=0, end_ms=10_000, cluster_id=1)],
        embeddings={1: _vec([0.0, 0.0, 0.0, 0.0])},
    )

    with pytest.raises(InvalidEnrollmentSample) as excinfo:
        compute_enrollment_embedding(Path("/tmp/sample.wav"), provider=provider)

    msg = str(excinfo.value).lower()
    assert "zero" in msg or "silent" in msg


def test_no_speech_sample_raises_invalid_enrollment_sample() -> None:
    """Spec scenario partial: no clusters at all → reject."""
    provider = _StubProvider(
        segments=[],
        embeddings=None,
    )

    with pytest.raises(InvalidEnrollmentSample) as excinfo:
        compute_enrollment_embedding(Path("/tmp/sample.wav"), provider=provider)

    msg = str(excinfo.value).lower()
    assert "no speech" in msg or "silent" in msg or "30-second" in msg


def test_pipeline_without_embeddings_raises_invalid_enrollment_sample() -> None:
    """Defensive: pipeline returned segments but no embeddings → reject."""
    provider = _StubProvider(
        segments=[DiarizationSegment(start_ms=0, end_ms=10_000, cluster_id=1)],
        embeddings=None,
    )

    with pytest.raises(InvalidEnrollmentSample) as excinfo:
        compute_enrollment_embedding(Path("/tmp/sample.wav"), provider=provider)

    assert "embedding" in str(excinfo.value).lower()


def test_embedding_can_round_trip_through_bytes() -> None:
    """The bytes returned MUST decode back into the original float32 vector
    so `VoiceEnrollmentMatcher._decode_enrolled` can recover it at match time.
    """
    original = _vec([1.0, -2.5, 3.14, 0.001, -0.5])
    provider = _StubProvider(
        segments=[DiarizationSegment(start_ms=0, end_ms=10_000, cluster_id=1)],
        embeddings={1: original},
    )

    blob = compute_enrollment_embedding(Path("/tmp/sample.wav"), provider=provider)
    decoded = np.frombuffer(blob, dtype=np.float32)

    assert np.allclose(decoded, original)
