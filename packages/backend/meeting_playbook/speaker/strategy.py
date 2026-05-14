"""SpeakerAttributionStrategy Protocol + DualChannelStrategy / SingleChannelStrategy impls.

Selector function `select_strategy(...)` chooses between dual / single based
on the recording configuration; ASR pipeline owns selection at the session
finalize boundary so ASRProvider and DiarizationProvider stay decoupled
(per design.md decision *Strategy selection 寫在 pipeline 邊界*).

See spec `speaker-attribution-strategy/spec.md` for the normative contract.
"""

from __future__ import annotations

from dataclasses import is_dataclass, replace
from pathlib import Path
from typing import Protocol, runtime_checkable

from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.speaker.diarization import (
    DiarizationProvider,
    DiarizationSegment,
)


class InvalidSpeakerConfiguration(ValueError):
    """Raised by `select_strategy` when the recording set is neither a
    valid dual-channel pair (`{me, counterparty}`) nor a single recording.

    The session orchestrator catches this and emits the
    `session.invalid_speaker_configuration` WebSocket error frame.
    """


class UnresolvableChunkStream(ValueError):
    """Raised by `DualChannelStrategy` when a chunk's source stream cannot
    be matched against any of the provided recordings. The strategy MUST
    NOT silently default; surfacing this lets the orchestrator log and
    bail out rather than write a misleading `speaker` value.
    """


@runtime_checkable
class SpeakerAttributionStrategy(Protocol):
    """Behavioural contract for speaker attribution.

    Implementations MUST:
    - Return NEW chunk instances (or copies) — never mutate the input list
      or any input chunk in-place.
    - Preserve input order and length (one output chunk per input chunk).
    """

    def assign_speakers(
        self,
        recordings: list[Recording],
        chunks: list[TranscriptChunk],
    ) -> list[TranscriptChunk]: ...


def _copy_chunk_with_speaker(chunk: TranscriptChunk, speaker: str) -> TranscriptChunk:
    """Return a copy of `chunk` with `speaker` replaced.

    Works for both dataclass-based (frozen) TranscriptChunk and ORM-mapped
    SQLAlchemy rows by using `dataclasses.replace` for the former and a
    detached copy for the latter. The SQLAlchemy `TranscriptChunk` model is
    a declarative class, so we build a transient duplicate by copying the
    public column attributes.
    """
    if is_dataclass(chunk) and not isinstance(chunk, type):
        return replace(chunk, speaker=speaker)  # type: ignore[arg-type]
    # SQLAlchemy ORM instance: build a detached copy with overridden speaker.
    copy = TranscriptChunk(
        id=chunk.id,
        meeting_id=chunk.meeting_id,
        speaker=speaker,
        text=chunk.text,
        started_at=chunk.started_at,
        ended_at=chunk.ended_at,
        asr_provider_used=chunk.asr_provider_used,
        confidence=chunk.confidence,
        created_at=chunk.created_at,
    )
    return copy


_BINARY_SPEAKERS = frozenset({"me", "counterparty"})


class DualChannelStrategy:
    """Pass-through validator for dual-channel sessions.

    The dual-channel ASR pipeline (slice-6 / slice-7) writes `speaker = "me"`
    for microphone-sourced chunks and `speaker = "counterparty"` for
    BlackHole-sourced chunks at transcription time. This strategy assumes
    those labels are already in place and only:

    - Returns immutable copies of each chunk (per the strategy contract).
    - Surfaces any chunk whose `speaker` is outside the binary value set
      as `UnresolvableChunkStream` — preferring a loud failure over silent
      mislabeling.

    `recordings` is accepted to satisfy the Protocol signature but unused
    here; recording-set validation lives in `select_strategy`.
    """

    def assign_speakers(
        self,
        recordings: list[Recording],
        chunks: list[TranscriptChunk],
    ) -> list[TranscriptChunk]:
        _ = recordings  # see docstring — handled at select_strategy
        result: list[TranscriptChunk] = []
        for chunk in chunks:
            if chunk.speaker not in _BINARY_SPEAKERS:
                raise UnresolvableChunkStream(
                    f"chunk {chunk.id!r} has speaker={chunk.speaker!r}; "
                    f"DualChannelStrategy expects one of {sorted(_BINARY_SPEAKERS)}"
                )
            result.append(_copy_chunk_with_speaker(chunk, chunk.speaker))
        return result


_UNKNOWN_CLUSTER_LABEL = "speaker_cluster_unknown"


def _cluster_label(cluster_id: int) -> str:
    return f"speaker_cluster_{cluster_id}"


class SingleChannelStrategy:
    """Diarization-driven attribution for single-mic recordings.

    Calls `DiarizationProvider.diarize(...)` once for the single recording
    and assigns each chunk a `speaker_cluster_{N}` label based on which
    diarization segment overlaps the chunk window the most.

    Ties on equal overlap resolve to the LATER segment (matching the spec
    scenario "chunk labeled by largest-overlap diarization segment"). When
    the best overlap is below `overlap_threshold_ms`, the chunk falls back
    to `speaker_cluster_unknown` rather than guessing.

    The recording's wall-clock origin comes from `Recording.started_at`
    (added by slice-16) with `Recording.created_at` as a slice-12-era
    fallback while the column does not yet exist.
    """

    def __init__(
        self,
        provider: DiarizationProvider,
        overlap_threshold_ms: int = 250,
    ) -> None:
        self.provider = provider
        self.overlap_threshold_ms = overlap_threshold_ms

    def assign_speakers(
        self,
        recordings: list[Recording],
        chunks: list[TranscriptChunk],
    ) -> list[TranscriptChunk]:
        if len(recordings) != 1:
            raise InvalidSpeakerConfiguration(
                f"SingleChannelStrategy expects exactly one recording, got {len(recordings)}"
            )
        recording = recordings[0]
        segments = self.provider.diarize(Path(recording.file_path))

        # Recording.started_at is added in slice-16; fall back to created_at
        # in the slice-12 era so this strategy works against the current schema.
        recording_origin = getattr(recording, "started_at", None) or recording.created_at

        result: list[TranscriptChunk] = []
        for chunk in chunks:
            chunk_start_ms = int((chunk.started_at - recording_origin).total_seconds() * 1000)
            chunk_end_ms = int((chunk.ended_at - recording_origin).total_seconds() * 1000)
            label = self._best_label(segments, chunk_start_ms, chunk_end_ms)
            result.append(_copy_chunk_with_speaker(chunk, label))
        return result

    def _best_label(
        self,
        segments: list[DiarizationSegment],
        chunk_start_ms: int,
        chunk_end_ms: int,
    ) -> str:
        best_overlap_ms = -1
        best_cluster_id: int | None = None
        for seg in segments:
            overlap_start = max(seg.start_ms, chunk_start_ms)
            overlap_end = min(seg.end_ms, chunk_end_ms)
            overlap_ms = max(0, overlap_end - overlap_start)
            # `>=` so equal-overlap ties resolve to the later segment in
            # iteration order (which is `start_ms`-ascending per the provider
            # contract — i.e., later in time).
            if overlap_ms >= best_overlap_ms:
                best_overlap_ms = overlap_ms
                best_cluster_id = seg.cluster_id

        if best_cluster_id is None or best_overlap_ms < self.overlap_threshold_ms:
            return _UNKNOWN_CLUSTER_LABEL
        return _cluster_label(best_cluster_id)


_DUAL_CHANNEL_STREAMS = frozenset({"me", "counterparty"})


def _default_diarization_provider() -> DiarizationProvider:
    """Build the v1.1 default diarization provider (`PyannoteProvider`).

    Reads `PYANNOTE_AUTH_TOKEN` from `Settings`. When the token is empty,
    raises `DiarizationProviderUnavailable` rather than substituting a
    degraded fallback (Apple Speech / SoundAnalysis cannot do real
    diarization; silent single-cluster output would be worse than failing).

    Tests can avoid hitting this path by passing `single_channel_provider`
    explicitly to `select_strategy(...)`.
    """
    from meeting_playbook.config import get_settings
    from meeting_playbook.speaker.diarization import DiarizationProviderUnavailable
    from meeting_playbook.speaker.pyannote_provider import PyannoteProvider

    settings = get_settings()
    token = settings.pyannote_auth_token
    if not token:
        raise DiarizationProviderUnavailable(
            "PYANNOTE_AUTH_TOKEN is unset; single-channel speaker attribution "
            "requires a HuggingFace access token with accepted gating terms "
            "for pyannote/speaker-diarization-3.1 (see README §3.5)."
        )
    return PyannoteProvider(token=token)


def _hybrid_enabled() -> bool:
    """Read `SPEAKER_HYBRID_ENABLED` from Settings — defaults to True.

    Kept as a thin wrapper so tests can override the env via `monkeypatch`
    + cache_clear without importing config at module scope.
    """
    from meeting_playbook.config import get_settings

    return get_settings().speaker_hybrid_enabled


def select_strategy(
    recordings: list[Recording],
    *,
    single_channel_provider: DiarizationProvider | None = None,
) -> SpeakerAttributionStrategy:
    """Pick the speaker attribution strategy matching the recording configuration.

    Rules (per spec `select_strategy chooses dual or single based on
    recording configuration`):

    - Two recordings with stream values exactly `{"me", "counterparty"}` →
      `DualChannelStrategy`.
    - Exactly one recording → `SingleChannelStrategy` configured with the
      v1.1 default `PyannoteProvider` (reads `PYANNOTE_AUTH_TOKEN` from
      `Settings`); missing token raises `DiarizationProviderUnavailable`.
    - Any other shape → `InvalidSpeakerConfiguration`.

    When `SPEAKER_HYBRID_ENABLED=false` (rollback / kill switch per ADR-0029),
    single-channel configurations SHALL raise `InvalidSpeakerConfiguration`
    immediately — the dual-channel path remains the only accepted mode.

    `single_channel_provider` lets tests inject a stub `DiarizationProvider`
    so the real pyannote pipeline never has to load.
    """
    count = len(recordings)
    streams = [r.stream for r in recordings]
    if count == 2:
        if set(streams) == _DUAL_CHANNEL_STREAMS:
            return DualChannelStrategy()
        raise InvalidSpeakerConfiguration(
            f"Dual-channel expects streams {sorted(_DUAL_CHANNEL_STREAMS)}, got {sorted(streams)}"
        )
    if count == 1:
        if not _hybrid_enabled():
            raise InvalidSpeakerConfiguration(
                "SPEAKER_HYBRID_ENABLED is false; single-channel mode is "
                "disabled. Set SPEAKER_HYBRID_ENABLED=true to re-enable."
            )
        provider = single_channel_provider or _default_diarization_provider()
        return SingleChannelStrategy(provider)
    raise InvalidSpeakerConfiguration(
        f"Expected 1 (single-channel) or 2 (dual-channel) recordings, got {count}"
    )
