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

from meeting_playbook.sessions.models import Recording
from meeting_playbook.sessions.repository import SessionRepository
from meeting_playbook.speaker.diarization import DiarizationProvider
from meeting_playbook.speaker.strategy import (
    SingleChannelStrategy,
    select_strategy,
)


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
) -> AttributionResult:
    """Run speaker attribution for one meeting's persisted chunks.

    `single_channel_provider` is for tests; production omits it and inherits
    the module-level default (PyannoteProvider gated on PYANNOTE_AUTH_TOKEN).
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
    reassigned = strategy.assign_speakers(recordings, chunks)
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
