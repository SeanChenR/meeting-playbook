"""Protocol-level tests for SpeakerAttributionStrategy.

Verifies spec requirement "SpeakerAttributionStrategy interface assigns
speaker labels to transcript chunks": output preserves count and order,
inputs are NOT mutated.
"""

from __future__ import annotations

from datetime import datetime, timezone

from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.speaker.strategy import SpeakerAttributionStrategy


class _NoopStrategy:
    """Minimal protocol-satisfying impl: returns shallow copies untouched
    except for `speaker = 'noop'` so we can assert no in-place mutation.
    """

    def assign_speakers(
        self,
        recordings: list[Recording],
        chunks: list[TranscriptChunk],
    ) -> list[TranscriptChunk]:
        return [
            TranscriptChunk(
                id=c.id,
                meeting_id=c.meeting_id,
                speaker="noop",
                text=c.text,
                started_at=c.started_at,
                ended_at=c.ended_at,
                asr_provider_used=c.asr_provider_used,
                confidence=c.confidence,
                created_at=c.created_at,
            )
            for c in chunks
        ]


def _make_chunk(idx: int, *, speaker: str = "unassigned") -> TranscriptChunk:
    base = datetime(2026, 5, 14, 10, 0, idx, tzinfo=timezone.utc)
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


def test_noop_strategy_satisfies_protocol() -> None:
    assert isinstance(_NoopStrategy(), SpeakerAttributionStrategy)


def test_assign_speakers_preserves_count_and_order() -> None:
    chunks = [_make_chunk(i) for i in range(1, 4)]
    result = _NoopStrategy().assign_speakers([], chunks)

    assert len(result) == 3
    assert [c.id for c in result] == ["chunk_1", "chunk_2", "chunk_3"]


def test_assign_speakers_does_not_mutate_input_chunks() -> None:
    chunks = [_make_chunk(i, speaker="unassigned") for i in range(1, 4)]

    _NoopStrategy().assign_speakers([], chunks)

    for c in chunks:
        assert c.speaker == "unassigned", "input chunk speaker must remain unchanged"
