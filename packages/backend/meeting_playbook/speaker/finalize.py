"""Session-finalize integration for the speaker attribution layer.

`apply_speaker_attribution(...)` is the single entry point called by the
session router after all recordings are persisted but before the meeting
status transitions to `completed`. It:

1. Loads recordings + chunks for the meeting.
2. Picks the appropriate `SpeakerAttributionStrategy` via `select_strategy`.
3. Reassigns chunk `speaker` values; bulk-updates only the rows that changed.
4. Times the strategy call and emits a `diarization_slow` warning when
   `SingleChannelStrategy` exceeds the wav-duration × 0.3 latency budget
   (slice-12 design "Diarization latency 預算").

`InvalidSpeakerConfiguration` and `DiarizationProviderUnavailable` raised by
`select_strategy` propagate to the caller (the router translates them into
the appropriate WebSocket error frames per slice-12 Task 6.2).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from meeting_playbook.sessions.models import Recording, TranscriptChunk
from meeting_playbook.sessions.repository import SessionRepository
from meeting_playbook.speaker.diarization import DiarizationProvider
from meeting_playbook.speaker.strategy import (
    SingleChannelStrategy,
    select_strategy,
)
from meeting_playbook.voice_enrollment.matcher import VoiceEnrollmentMatcher
from meeting_playbook.voice_enrollment.repository import VoiceEnrollmentRepository


logger = logging.getLogger(__name__)

# A 16kHz mono 16-bit WAV stores 32_000 bytes per second of audio. Recordings
# are normalized to this format upstream (slice 6 / 7 + slice 14), so we can
# convert `Recording.bytes` to a duration estimate cheaply without reading
# the WAV header.
_BYTES_PER_SECOND_16KHZ_MONO_16BIT = 16_000 * 2
_LATENCY_BUDGET_RATIO = 0.3


@dataclass(frozen=True)
class AttributionResult:
    chunks_updated: int
    chunks_total: int
    strategy_name: str
    elapsed_ms: int
    is_diarization_slow: bool = False
    latency_budget_ms: int = 0


async def apply_speaker_attribution(
    *,
    meeting_id: str,
    repo: SessionRepository,
    single_channel_provider: DiarizationProvider | None = None,
    voice_enrollment_repo: VoiceEnrollmentRepository | None = None,
    current_user_id: str | None = None,
    match_threshold: float = 0.5,
) -> AttributionResult:
    """Run speaker attribution for one meeting's persisted chunks.

    `single_channel_provider` is for tests; production omits it and inherits
    the module-level default (PyannoteProvider gated on PYANNOTE_AUTH_TOKEN).

    `voice_enrollment_repo` + `current_user_id` enable the slice-13
    auto-me-rename pass: when both are supplied AND a `voice_enrollment` row
    exists for the user AND the strategy is `SingleChannelStrategy`, the
    matching cluster's chunks are rewritten from `speaker_cluster_<N>` to
    `me` (per ADR-0029 + slice-13 spec
    `apply_speaker_attribution renames the matched single-channel cluster
    to me when an enrollment exists`).
    """
    recordings = await repo.list_recordings_for_meeting(meeting_id)
    chunks = await repo.list_chunks_for_meeting(meeting_id)

    if not chunks:
        logger.info(
            "speaker_attribution_skipped_no_chunks",
            extra={"meeting_id": meeting_id, "recording_count": len(recordings)},
        )
        return AttributionResult(
            chunks_updated=0,
            chunks_total=0,
            strategy_name="none",
            elapsed_ms=0,
        )

    strategy = select_strategy(recordings, single_channel_provider=single_channel_provider)

    start_ns = time.monotonic_ns()
    # `strategy.assign_speakers` is synchronous and, for SingleChannelStrategy,
    # calls into pyannote.audio — a CPU/GPU-bound ML pipeline that takes
    # ~30-60s on the slice-12 multi-speaker fixture. Running it directly on
    # the asyncio event loop blocks every concurrent HTTP request (incl. the
    # progress-polling endpoint), so we offload to a worker thread.
    import anyio  # local import keeps finalize import-light

    reassigned = await anyio.to_thread.run_sync(strategy.assign_speakers, recordings, chunks)
    elapsed_ms = (time.monotonic_ns() - start_ns) // 1_000_000

    budget_ms = 0
    is_slow = False
    if isinstance(strategy, SingleChannelStrategy):
        budget_ms = _latency_budget_ms(recordings)
        is_slow = bool(budget_ms) and elapsed_ms > budget_ms
        if is_slow:
            logger.warning(
                "diarization_slow",
                extra={
                    "meeting_id": meeting_id,
                    "elapsed_ms": elapsed_ms,
                    "budget_ms": budget_ms,
                    "wav_duration_estimate_ms": int(budget_ms / _LATENCY_BUDGET_RATIO),
                },
            )

        # Slice-13 voice enrollment post-processing — applies only to the
        # single-channel path with both an enrollment repo and a user id.
        # Dual-channel path skips this entirely (chunks are already correctly
        # labelled me / counterparty by the ASR pipeline).
        reassigned = await _maybe_rename_enrolled_cluster(
            meeting_id=meeting_id,
            strategy=strategy,
            chunks=reassigned,
            voice_enrollment_repo=voice_enrollment_repo,
            current_user_id=current_user_id,
            match_threshold=match_threshold,
        )

    updates: list[tuple[str, str]] = [
        (new.id, new.speaker)
        for original, new in zip(chunks, reassigned)
        if original.speaker != new.speaker
    ]
    rows_changed = await repo.update_chunk_speakers(updates)

    logger.info(
        "speaker_attribution_applied",
        extra={
            "meeting_id": meeting_id,
            "strategy": type(strategy).__name__,
            "chunks_total": len(chunks),
            "chunks_updated": rows_changed,
            "elapsed_ms": elapsed_ms,
        },
    )
    return AttributionResult(
        chunks_updated=rows_changed,
        chunks_total=len(chunks),
        strategy_name=type(strategy).__name__,
        elapsed_ms=elapsed_ms,
        is_diarization_slow=is_slow,
        latency_budget_ms=budget_ms,
    )


async def _maybe_rename_enrolled_cluster(
    *,
    meeting_id: str,
    strategy: SingleChannelStrategy,
    chunks: list[TranscriptChunk],
    voice_enrollment_repo: VoiceEnrollmentRepository | None,
    current_user_id: str | None,
    match_threshold: float,
) -> list[TranscriptChunk]:
    """When the user has a voice enrollment, rewrite the matching cluster's
    chunks to `speaker = "me"`. Skipped cleanly (no DB write, no error) for
    any of the no-rename branches in the spec:
    - voice_enrollment_repo is None
    - current_user_id is None
    - no enrollment row for the user
    - strategy did not expose cluster embeddings (test stub or older provider)
    - matcher returns None (no cluster above threshold)
    """
    if voice_enrollment_repo is None or current_user_id is None:
        return chunks

    enrollment = await voice_enrollment_repo.get_for_user(current_user_id)
    if enrollment is None:
        return chunks

    cluster_embeddings = strategy.cluster_embeddings()
    if not cluster_embeddings:
        logger.info(
            "voice_enrollment_skipped_no_embeddings",
            extra={"meeting_id": meeting_id, "user_id": current_user_id},
        )
        return chunks

    matched_cluster_id = VoiceEnrollmentMatcher().find_me_cluster(
        enrolled_embedding=enrollment.embedding,
        cluster_embeddings=cluster_embeddings,
        threshold=match_threshold,
    )
    if matched_cluster_id is None:
        logger.info(
            "voice_enrollment_no_match",
            extra={
                "meeting_id": meeting_id,
                "user_id": current_user_id,
                "cluster_count": len(cluster_embeddings),
                "threshold": match_threshold,
            },
        )
        return chunks

    matched_label = f"speaker_cluster_{matched_cluster_id}"
    renamed: list[TranscriptChunk] = []
    for chunk in chunks:
        if chunk.speaker == matched_label:
            renamed.append(_copy_chunk_with_me(chunk))
        else:
            renamed.append(chunk)

    logger.info(
        "voice_enrollment_renamed_cluster",
        extra={
            "meeting_id": meeting_id,
            "user_id": current_user_id,
            "matched_cluster_id": matched_cluster_id,
        },
    )
    return renamed


def _copy_chunk_with_me(chunk: TranscriptChunk) -> TranscriptChunk:
    """Return a detached copy of `chunk` with `speaker = 'me'`.

    Mirrors the immutability contract from `_copy_chunk_with_speaker` in
    the speaker module but is kept inline here so finalize doesn't depend
    on a private helper crossing module boundaries.
    """
    copy = TranscriptChunk(
        id=chunk.id,
        meeting_id=chunk.meeting_id,
        speaker="me",
        text=chunk.text,
        started_at=chunk.started_at,
        ended_at=chunk.ended_at,
        asr_provider_used=chunk.asr_provider_used,
        confidence=chunk.confidence,
        created_at=chunk.created_at,
    )
    return copy


def _latency_budget_ms(recordings: list[Recording]) -> int:
    """Estimate the wav-duration-based latency budget for diarization.

    Returns 0 when no usable bytes are available (caller treats 0 as "no
    budget; skip the slow warning") rather than dividing by zero.
    """
    total_bytes = sum(max(0, r.bytes) for r in recordings)
    if total_bytes <= 0:
        return 0
    duration_ms = (total_bytes * 1000) // _BYTES_PER_SECOND_16KHZ_MONO_16BIT
    return int(duration_ms * _LATENCY_BUDGET_RATIO)
