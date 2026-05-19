"""Behavioural tests for `DualChannelStrategy`.

Verifies the three spec scenarios from
"DualChannelStrategy validates pre-labeled binary speaker values from
the dual-channel ASR pipeline":
- me-labeled chunks pass through with a new instance returned
- counterparty-labeled chunks pass through with a new instance returned
- chunks with unexpected speaker values raise `UnresolvableChunkStream`
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.speaker.strategy import (
    DualChannelStrategy,
    UnresolvableChunkStream,
)


def _make_chunk(idx: int, *, speaker: str) -> TranscriptChunk:
    base = datetime(2026, 5, 14, 10, 0, idx, tzinfo=UTC)
    return TranscriptChunk(
        id=f"chunk_{idx}",
        meeting_id="m_test",
        speaker=speaker,
        text=f"text_{idx}",
        started_at=base,
        ended_at=base,
        asr_provider_used="whisper",
        confidence=None,
        created_at=base,
    )


def _make_recording(stream: str) -> Recording:
    return Recording(
        id=f"rec_{stream}",
        meeting_id="m_test",
        stream=stream,
        file_path=f"/tmp/{stream}.wav",
        bytes=0,
        created_at=datetime(2026, 5, 14, 10, 0, 0, tzinfo=UTC),
    )


def test_me_chunks_pass_through_with_new_instance() -> None:
    chunk = _make_chunk(1, speaker="me")
    recordings = [_make_recording("me"), _make_recording("counterparty")]

    [result] = DualChannelStrategy().assign_speakers(recordings, [chunk])

    assert result.speaker == "me"
    assert result is not chunk


def test_counterparty_chunks_pass_through_with_new_instance() -> None:
    chunk = _make_chunk(2, speaker="counterparty")
    recordings = [_make_recording("me"), _make_recording("counterparty")]

    [result] = DualChannelStrategy().assign_speakers(recordings, [chunk])

    assert result.speaker == "counterparty"
    assert result is not chunk


def test_unexpected_speaker_raises_unresolvable_chunk_stream() -> None:
    chunk = _make_chunk(3, speaker="speaker_cluster_1")
    recordings = [_make_recording("me"), _make_recording("counterparty")]

    with pytest.raises(UnresolvableChunkStream) as excinfo:
        DualChannelStrategy().assign_speakers(recordings, [chunk])

    assert "chunk_3" in str(excinfo.value)
    assert "speaker_cluster_1" in str(excinfo.value)


def test_assign_speakers_preserves_order_and_does_not_mutate_inputs() -> None:
    chunks = [
        _make_chunk(1, speaker="me"),
        _make_chunk(2, speaker="counterparty"),
        _make_chunk(3, speaker="me"),
    ]
    recordings = [_make_recording("me"), _make_recording("counterparty")]

    result = DualChannelStrategy().assign_speakers(recordings, chunks)

    assert [c.id for c in result] == ["chunk_1", "chunk_2", "chunk_3"]
    # input list untouched (identity check on each input element)
    assert [c.speaker for c in chunks] == ["me", "counterparty", "me"]
