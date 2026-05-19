"""Protocol-level tests for DiarizationProvider — verifies the contract
described in `speaker-attribution-strategy/spec.md` requirement
"DiarizationProvider interface exposes diarize for single-channel audio".

These tests intentionally use a fake in-memory provider so the contract
can be exercised without any ML runtime; concrete providers (pyannote,
Apple Speech) get their own test files with real fixtures.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest

from meeting_playbook.speaker.diarization import (
    DiarizationProvider,
    DiarizationSegment,
)


class _FakeDiarizationProvider:
    """Minimal protocol-satisfying impl that returns a canned segment list."""

    def __init__(self, segments: list[DiarizationSegment]) -> None:
        self._segments = segments

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        return list(self._segments)


def test_fake_provider_satisfies_protocol() -> None:
    provider = _FakeDiarizationProvider([])
    assert isinstance(provider, DiarizationProvider)


def test_segment_is_frozen() -> None:
    segment = DiarizationSegment(start_ms=0, end_ms=1000, cluster_id=1)
    with pytest.raises(AttributeError):
        segment.start_ms = 100  # type: ignore[misc]


def test_segments_returned_sorted_and_non_overlapping() -> None:
    """A well-behaved impl returns segments sorted ascending with no overlap.

    This test does NOT exercise pyannote / Apple Speech — it codifies the
    contract every real impl must satisfy at the boundary; concrete-provider
    test files reuse this assertion helper.
    """
    segments = [
        DiarizationSegment(start_ms=0, end_ms=1000, cluster_id=1),
        DiarizationSegment(start_ms=1000, end_ms=2500, cluster_id=2),
        DiarizationSegment(start_ms=2500, end_ms=3000, cluster_id=1),
    ]
    provider = _FakeDiarizationProvider(segments)

    result = provider.diarize(Path("/dev/null"))

    assert result, "non-empty"
    for current, next_segment in pairwise(result):
        assert current.start_ms < current.end_ms
        assert current.end_ms <= next_segment.start_ms
        assert current.start_ms <= next_segment.start_ms


def test_segments_can_skip_silence_gaps() -> None:
    """Non-overlap rule is `<=`, gaps between segments are allowed."""
    segments = [
        DiarizationSegment(start_ms=0, end_ms=1000, cluster_id=1),
        DiarizationSegment(start_ms=5000, end_ms=6000, cluster_id=2),  # 4s gap
    ]
    provider = _FakeDiarizationProvider(segments)

    result = provider.diarize(Path("/dev/null"))

    assert result[0].end_ms <= result[1].start_ms
