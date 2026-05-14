"""Behavioural tests for `SingleChannelStrategy`.

Verifies the two spec scenarios from
"SingleChannelStrategy assigns speaker_cluster_N labels via DiarizationProvider":
- Chunk labeled by largest-overlap diarization segment (ties → later segment).
- Chunk with no overlapping segment falls back to `speaker_cluster_unknown`.

Plus protocol-level immutability + cardinality already covered by the
strategy_protocol test file, reproduced here with the concrete impl.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.speaker.diarization import DiarizationSegment
from meeting_playbook.speaker.strategy import (
    InvalidSpeakerConfiguration,
    SingleChannelStrategy,
)


_RECORDING_START = datetime(2026, 5, 14, 10, 0, 0, tzinfo=timezone.utc)


def _recording_at(*, file_path: str = "/tmp/single.wav") -> Recording:
    rec = Recording(
        id="rec_single",
        meeting_id="m_test",
        stream="me",
        file_path=file_path,
        bytes=0,
        created_at=_RECORDING_START,
    )
    # Slice-16 will add Recording.started_at formally; the strategy
    # falls back to created_at for slice-12, so this assignment is for
    # forward-compatibility documentation only.
    rec.started_at = _RECORDING_START  # type: ignore[attr-defined]
    return rec


def _chunk(start_offset_ms: int, end_offset_ms: int, *, idx: int = 1) -> TranscriptChunk:
    start = _RECORDING_START + timedelta(milliseconds=start_offset_ms)
    end = _RECORDING_START + timedelta(milliseconds=end_offset_ms)
    return TranscriptChunk(
        id=f"chunk_{idx}",
        meeting_id="m_test",
        speaker="pending",
        text=f"text_{idx}",
        started_at=start,
        ended_at=end,
        asr_provider_used="whisper",
        confidence=None,
        created_at=_RECORDING_START,
    )


class _StubProvider:
    def __init__(self, segments: list[DiarizationSegment]) -> None:
        self._segments = segments
        self.calls: list[Path] = []

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        self.calls.append(wav_path)
        return list(self._segments)


def test_chunk_labeled_by_largest_overlap_segment_with_tie_to_later_segment() -> None:
    """Spec scenario: segments [(0,5000,1),(5000,10000,2)], chunk 4500-5500ms.

    Both segments overlap by 500ms; tie resolves to the LATER segment → cluster 2.
    """
    provider = _StubProvider(
        [
            DiarizationSegment(start_ms=0, end_ms=5000, cluster_id=1),
            DiarizationSegment(start_ms=5000, end_ms=10000, cluster_id=2),
        ]
    )
    strategy = SingleChannelStrategy(provider)
    chunk = _chunk(4500, 5500)

    [result] = strategy.assign_speakers([_recording_at()], [chunk])

    assert result.speaker == "speaker_cluster_2"
    assert result is not chunk
    assert chunk.speaker == "pending", "input must remain untouched"


def test_chunk_with_no_overlapping_segment_falls_back_to_unknown() -> None:
    """Spec scenario: segment [(0,5000,1)], chunk 10000-11000ms → unknown."""
    provider = _StubProvider([DiarizationSegment(start_ms=0, end_ms=5000, cluster_id=1)])
    strategy = SingleChannelStrategy(provider)
    chunk = _chunk(10000, 11000)

    [result] = strategy.assign_speakers([_recording_at()], [chunk])

    assert result.speaker == "speaker_cluster_unknown"


def test_overlap_below_threshold_falls_back_to_unknown() -> None:
    """Overlap of 200ms is below default threshold 250ms → unknown."""
    provider = _StubProvider([DiarizationSegment(start_ms=0, end_ms=5000, cluster_id=1)])
    strategy = SingleChannelStrategy(provider, overlap_threshold_ms=250)
    # chunk 4800-6000ms; overlap with [0,5000] is 200ms (5000-4800)
    chunk = _chunk(4800, 6000)

    [result] = strategy.assign_speakers([_recording_at()], [chunk])

    assert result.speaker == "speaker_cluster_unknown"


def test_diarize_called_once_per_assign_speakers_call() -> None:
    """The provider is invoked once for the single recording, regardless of
    how many chunks are processed.
    """
    provider = _StubProvider([DiarizationSegment(start_ms=0, end_ms=10000, cluster_id=1)])
    strategy = SingleChannelStrategy(provider)
    chunks = [_chunk(0, 1000, idx=i) for i in range(1, 6)]

    strategy.assign_speakers([_recording_at(file_path="/tmp/single.wav")], chunks)

    assert provider.calls == [Path("/tmp/single.wav")]


def test_multiple_recordings_raise_invalid_speaker_configuration() -> None:
    """SingleChannelStrategy strictly expects one recording — multiple is
    caller error, not silently picking the first.
    """
    provider = _StubProvider([])
    strategy = SingleChannelStrategy(provider)

    with pytest.raises(InvalidSpeakerConfiguration):
        strategy.assign_speakers(
            [_recording_at(), _recording_at(file_path="/tmp/extra.wav")],
            [_chunk(0, 1000)],
        )


def test_preserves_chunk_order_and_count() -> None:
    provider = _StubProvider([DiarizationSegment(start_ms=0, end_ms=10000, cluster_id=1)])
    strategy = SingleChannelStrategy(provider)
    chunks = [_chunk(i * 100, i * 100 + 50, idx=i) for i in range(1, 4)]

    result = strategy.assign_speakers([_recording_at()], chunks)

    assert [c.id for c in result] == ["chunk_1", "chunk_2", "chunk_3"]
