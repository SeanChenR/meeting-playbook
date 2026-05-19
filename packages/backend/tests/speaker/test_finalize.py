"""Tests for `apply_speaker_attribution(...)`.

Verifies the session-finalize integration entry point:
- Dual-channel pass-through performs zero DB updates (regression-safe).
- Single-channel reassigns chunks to `speaker_cluster_*` and bulk-updates.
- Latency exceeding the wav-duration × 0.3 budget triggers the
  `diarization_slow` warning (slice-12 design "Diarization latency 預算").
- `select_strategy` errors propagate so the router can translate them
  into the WS `session.invalid_speaker_configuration` frame.

The repository is faked in-memory so these tests run without a DB.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.speaker.diarization import DiarizationSegment
from meeting_playbook.speaker.finalize import (
    AttributionResult,
    apply_speaker_attribution,
)
from meeting_playbook.speaker.strategy import InvalidSpeakerConfiguration

_BASE_TS = datetime(2026, 5, 14, 10, 0, 0, tzinfo=UTC)


# ───── Fakes ───────────────────────────────────────────────────────────


class _FakeRepo:
    """In-memory stand-in for SessionRepository — records all writes."""

    def __init__(
        self,
        *,
        recordings: list[Recording],
        chunks: list[TranscriptChunk],
    ) -> None:
        self._recordings = recordings
        self._chunks = chunks
        self.updates: list[tuple[str, str]] = []

    async def list_recordings_for_meeting(self, meeting_id: str) -> list[Recording]:
        return list(self._recordings)

    async def list_chunks_for_meeting(self, meeting_id: str) -> list[TranscriptChunk]:
        return list(self._chunks)

    async def update_chunk_speakers(self, updates: list[tuple[str, str]]) -> int:
        self.updates.extend(updates)
        # Apply mutations so subsequent reads in the same test reflect them.
        by_id = {c.id: c for c in self._chunks}
        for chunk_id, new_speaker in updates:
            if chunk_id in by_id:
                by_id[chunk_id].speaker = new_speaker
        return len(updates)


class _StubDiarization:
    def __init__(self, segments: list[DiarizationSegment]) -> None:
        self._segments = segments

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        return list(self._segments)


class _SlowDiarization:
    """DiarizationProvider that sleeps to simulate slow diarization."""

    def __init__(
        self,
        *,
        segments: list[DiarizationSegment],
        sleep_seconds: float,
    ) -> None:
        self._segments = segments
        self._sleep = sleep_seconds

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        time.sleep(self._sleep)
        return list(self._segments)


def _recording(stream: str, *, bytes_size: int = 0) -> Recording:
    rec = Recording(
        id=f"rec_{stream}",
        meeting_id="m_t",
        stream=stream,
        file_path=f"/tmp/{stream}.wav",
        bytes=bytes_size,
        created_at=_BASE_TS,
    )
    rec.started_at = _BASE_TS  # type: ignore[attr-defined]
    return rec


def _chunk(idx: int, *, speaker: str, offset_ms: int = 0) -> TranscriptChunk:
    started = _BASE_TS + timedelta(milliseconds=offset_ms)
    ended = started + timedelta(milliseconds=500)
    return TranscriptChunk(
        id=f"chunk_{idx}",
        meeting_id="m_t",
        speaker=speaker,
        text=f"text {idx}",
        started_at=started,
        ended_at=ended,
        asr_provider_used="whisper",
        confidence=None,
        created_at=_BASE_TS,
    )


# ───── Tests ──────────────────────────────────────────────────────────


async def test_empty_chunks_returns_zero_no_strategy_invoked() -> None:
    repo = _FakeRepo(
        recordings=[_recording("me"), _recording("counterparty")],
        chunks=[],
    )

    result = await apply_speaker_attribution(meeting_id="m_t", repo=repo)

    assert result == AttributionResult(
        chunks_updated=0, chunks_total=0, strategy_name="none", elapsed_ms=0
    )
    assert repo.updates == []


async def test_dual_channel_pass_through_performs_zero_updates() -> None:
    """Regression-safe path: dual-channel chunks already have correct speakers
    from the ASR pipeline; strategy returns identical values; repo SHALL
    NOT receive any update requests.
    """
    chunks = [
        _chunk(1, speaker="me", offset_ms=0),
        _chunk(2, speaker="counterparty", offset_ms=1000),
        _chunk(3, speaker="me", offset_ms=2000),
    ]
    repo = _FakeRepo(
        recordings=[_recording("me"), _recording("counterparty")],
        chunks=chunks,
    )

    result = await apply_speaker_attribution(meeting_id="m_t", repo=repo)

    assert repo.updates == []
    assert result.chunks_updated == 0
    assert result.chunks_total == 3
    assert result.strategy_name == "DualChannelStrategy"


async def test_single_channel_assigns_speaker_cluster_labels_and_updates_db() -> None:
    """SingleChannelStrategy reassigns `me`-placeholder chunks to
    `speaker_cluster_<N>` based on diarization output; repo update is called.
    """
    chunks = [
        _chunk(1, speaker="me", offset_ms=0),
        _chunk(2, speaker="me", offset_ms=1000),
        _chunk(3, speaker="me", offset_ms=2000),
    ]
    repo = _FakeRepo(
        recordings=[_recording("me", bytes_size=192_000)],  # ~6s
        chunks=chunks,
    )
    provider = _StubDiarization(
        [
            DiarizationSegment(start_ms=0, end_ms=500, cluster_id=1),
            DiarizationSegment(start_ms=1000, end_ms=1500, cluster_id=2),
            DiarizationSegment(start_ms=2000, end_ms=2500, cluster_id=1),
        ]
    )

    result = await apply_speaker_attribution(
        meeting_id="m_t",
        repo=repo,
        single_channel_provider=provider,
    )

    by_id = dict(repo.updates)
    assert by_id["chunk_1"] == "speaker_cluster_1"
    assert by_id["chunk_2"] == "speaker_cluster_2"
    assert by_id["chunk_3"] == "speaker_cluster_1"
    assert result.chunks_updated == 3
    assert result.strategy_name == "SingleChannelStrategy"


async def test_invalid_speaker_configuration_propagates_for_router_to_catch() -> None:
    """Three recordings is invalid; the error propagates so the router can
    emit `session.invalid_speaker_configuration` (slice-12 Task 6.2).
    """
    repo = _FakeRepo(
        recordings=[
            _recording("me"),
            _recording("counterparty"),
            _recording("extra"),
        ],
        chunks=[_chunk(1, speaker="me")],
    )

    with pytest.raises(InvalidSpeakerConfiguration):
        await apply_speaker_attribution(meeting_id="m_t", repo=repo)

    assert repo.updates == [], "no partial writes on configuration failure"


async def test_diarization_slow_flag_set_when_over_budget() -> None:
    """A SlowDiarization that takes longer than wav-duration × 0.3 SHALL
    flag `is_diarization_slow=True` on the result; chunks still get updated.
    """
    chunks = [_chunk(1, speaker="me", offset_ms=0)]
    # 1 second of audio = 32_000 bytes; budget = 300ms; provider sleeps 500ms
    repo = _FakeRepo(
        recordings=[_recording("me", bytes_size=32_000)],
        chunks=chunks,
    )
    provider = _SlowDiarization(
        segments=[DiarizationSegment(start_ms=0, end_ms=500, cluster_id=1)],
        sleep_seconds=0.5,
    )

    result = await apply_speaker_attribution(
        meeting_id="m_t",
        repo=repo,
        single_channel_provider=provider,
    )

    assert result.is_diarization_slow is True
    assert result.elapsed_ms >= 500
    assert result.latency_budget_ms == 300
    assert result.chunks_updated == 1


async def test_diarization_within_budget_does_not_flag() -> None:
    """Fast provider stays under wav-duration × 0.3 → no slow flag."""
    chunks = [_chunk(1, speaker="me", offset_ms=0)]
    # 10 seconds of audio = 320_000 bytes; budget = 3000ms; stub is ~instant
    repo = _FakeRepo(
        recordings=[_recording("me", bytes_size=320_000)],
        chunks=chunks,
    )
    provider = _StubDiarization([DiarizationSegment(start_ms=0, end_ms=500, cluster_id=1)])

    result = await apply_speaker_attribution(
        meeting_id="m_t",
        repo=repo,
        single_channel_provider=provider,
    )

    assert result.is_diarization_slow is False
    assert result.latency_budget_ms == 3000


async def test_dual_channel_result_has_no_latency_budget() -> None:
    """Latency budget only applies to SingleChannelStrategy."""
    chunks = [_chunk(1, speaker="me", offset_ms=0)]
    repo = _FakeRepo(
        recordings=[_recording("me"), _recording("counterparty")],
        chunks=chunks,
    )

    result = await apply_speaker_attribution(meeting_id="m_t", repo=repo)

    assert result.is_diarization_slow is False
    assert result.latency_budget_ms == 0


# ───── Slice 13: voice enrollment auto-me rename ────────────────────────


import numpy as np  # noqa: E402

from meeting_playbook.voice_enrollment.matcher import _ENROLLMENT_DTYPE  # noqa: E402


class _EmbeddingsStubProvider:
    """Diarization stub that also exposes `cluster_embeddings()` so the
    SingleChannelStrategy can pass embeddings to the voice-enrollment matcher.
    """

    def __init__(
        self,
        *,
        segments: list[DiarizationSegment],
        cluster_to_embedding: dict[int, np.ndarray] | None,
    ) -> None:
        self._segments = segments
        self._cluster_to_embedding = cluster_to_embedding
        self.last_diarize_output = object()  # opaque sentinel — non-None

    def diarize(self, wav_path: Path) -> list[DiarizationSegment]:
        return list(self._segments)

    def cluster_embeddings(self) -> dict[int, np.ndarray] | None:
        return self._cluster_to_embedding


class _FakeEnrollmentRepo:
    def __init__(self, *, embedding_for_user: dict[str, bytes]) -> None:
        self._by_user = embedding_for_user

    async def get_for_user(self, user_id: str):  # type: ignore[no-untyped-def]
        if user_id not in self._by_user:
            return None
        return type(
            "_FakeEnrollment",
            (),
            {
                "user_id": user_id,
                "sample_wav_path": f"/tmp/{user_id}.wav",
                "embedding": self._by_user[user_id],
                "created_at": _BASE_TS,
            },
        )()


def _enrolled_bytes(values: list[float]) -> bytes:
    return np.asarray(values, dtype=_ENROLLMENT_DTYPE).tobytes()


def _cluster_vec(values: list[float]) -> np.ndarray:
    return np.asarray(values, dtype=np.float32)


async def test_voice_enrollment_renames_matched_cluster_to_me() -> None:
    """Spec scenario (a): user has enrollment, cluster 2 matches above
    threshold → chunk 2's speaker rewritten to `me`; clusters 1 and 3 keep
    their `speaker_cluster_*` labels.
    """
    chunks = [
        _chunk(1, speaker="speaker_cluster_1", offset_ms=0),
        _chunk(2, speaker="speaker_cluster_2", offset_ms=1000),
        _chunk(3, speaker="speaker_cluster_3", offset_ms=2000),
    ]
    repo = _FakeRepo(recordings=[_recording("me")], chunks=chunks)
    # cluster 2 matches the enrolled vector; 1 and 3 are orthogonal.
    provider = _EmbeddingsStubProvider(
        segments=[
            DiarizationSegment(start_ms=0, end_ms=500, cluster_id=1),
            DiarizationSegment(start_ms=1000, end_ms=1500, cluster_id=2),
            DiarizationSegment(start_ms=2000, end_ms=2500, cluster_id=3),
        ],
        cluster_to_embedding={
            1: _cluster_vec([0.0, 1.0, 0.0]),
            2: _cluster_vec([1.0, 0.0, 0.0]),  # ≈ enrolled
            3: _cluster_vec([0.0, 0.0, 1.0]),
        },
    )
    enroll_repo = _FakeEnrollmentRepo(embedding_for_user={"u_a": _enrolled_bytes([1.0, 0.0, 0.0])})

    await apply_speaker_attribution(
        meeting_id="m_t",
        repo=repo,
        single_channel_provider=provider,
        voice_enrollment_repo=enroll_repo,  # type: ignore[arg-type]
        current_user_id="u_a",
    )

    # The initial chunks already carried `speaker_cluster_1/2/3` (test setup
    # mimics chunks freshly written by the strategy and then revisited at
    # rename time). The strategy re-computes the same cluster labels, so
    # only the cluster-2 → `me` rename is an actual DB update.
    by_id = dict(repo.updates)
    assert by_id == {"chunk_2": "me"}


async def test_no_enrollment_keeps_cluster_labels_untouched() -> None:
    """Spec scenario (b): user has no `voice_enrollment` row → cluster
    labels remain as `speaker_cluster_*`."""
    chunks = [
        _chunk(1, speaker="speaker_cluster_1", offset_ms=0),
        _chunk(2, speaker="speaker_cluster_2", offset_ms=1000),
    ]
    repo = _FakeRepo(recordings=[_recording("me")], chunks=chunks)
    provider = _EmbeddingsStubProvider(
        segments=[
            DiarizationSegment(start_ms=0, end_ms=500, cluster_id=1),
            DiarizationSegment(start_ms=1000, end_ms=1500, cluster_id=2),
        ],
        cluster_to_embedding={
            1: _cluster_vec([1.0, 0.0, 0.0]),
            2: _cluster_vec([0.0, 1.0, 0.0]),
        },
    )
    enroll_repo = _FakeEnrollmentRepo(embedding_for_user={})  # u_b has no row

    await apply_speaker_attribution(
        meeting_id="m_t",
        repo=repo,
        single_channel_provider=provider,
        voice_enrollment_repo=enroll_repo,  # type: ignore[arg-type]
        current_user_id="u_b",
    )

    # No rename to `me` should have happened — only the strategy's initial
    # `speaker_cluster_*` assignments are present.
    me_renames = [(cid, sp) for cid, sp in repo.updates if sp == "me"]
    assert me_renames == []


async def test_enrollment_exists_but_no_cluster_passes_threshold() -> None:
    """Spec scenario (c): enrollment exists but every cluster's similarity
    falls below the match threshold → no rename."""
    chunks = [
        _chunk(1, speaker="speaker_cluster_1", offset_ms=0),
        _chunk(2, speaker="speaker_cluster_2", offset_ms=1000),
    ]
    repo = _FakeRepo(recordings=[_recording("me")], chunks=chunks)
    provider = _EmbeddingsStubProvider(
        segments=[
            DiarizationSegment(start_ms=0, end_ms=500, cluster_id=1),
            DiarizationSegment(start_ms=1000, end_ms=1500, cluster_id=2),
        ],
        cluster_to_embedding={
            # Both orthogonal to the enrolled vector — cosine 0.0 each.
            1: _cluster_vec([0.0, 1.0, 0.0]),
            2: _cluster_vec([0.0, 0.0, 1.0]),
        },
    )
    enroll_repo = _FakeEnrollmentRepo(embedding_for_user={"u_a": _enrolled_bytes([1.0, 0.0, 0.0])})

    await apply_speaker_attribution(
        meeting_id="m_t",
        repo=repo,
        single_channel_provider=provider,
        voice_enrollment_repo=enroll_repo,  # type: ignore[arg-type]
        current_user_id="u_a",
        match_threshold=0.5,
    )

    me_renames = [(cid, sp) for cid, sp in repo.updates if sp == "me"]
    assert me_renames == []


async def test_dual_channel_session_ignores_enrollment_completely() -> None:
    """Spec scenario (d): dual-channel session does NOT consult voice
    enrollment even when a row exists for the user."""
    chunks = [
        _chunk(1, speaker="me", offset_ms=0),
        _chunk(2, speaker="counterparty", offset_ms=1000),
    ]
    repo = _FakeRepo(
        recordings=[_recording("me"), _recording("counterparty")],
        chunks=chunks,
    )
    enroll_repo = _FakeEnrollmentRepo(embedding_for_user={"u_a": _enrolled_bytes([1.0, 0.0, 0.0])})

    result = await apply_speaker_attribution(
        meeting_id="m_t",
        repo=repo,
        voice_enrollment_repo=enroll_repo,  # type: ignore[arg-type]
        current_user_id="u_a",
    )

    assert result.chunks_updated == 0
    assert result.strategy_name == "DualChannelStrategy"
    assert repo.updates == []
