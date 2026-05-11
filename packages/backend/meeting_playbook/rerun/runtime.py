"""In-flight registry for ASR re-run tasks (slice-11 task 5.1).

Process-scoped `dict[str, asyncio.Task]` mapping meeting_id to the in-flight
re-run task. Concurrent spawn calls race-protect via `asyncio.Lock`. Mirrors
the slice-10 summary runtime pattern; the only structural addition is the
parallel `_progress` map so the polling endpoint can report
`(chunks_processed, chunks_total)`.

Per slice-11 design Decision 3:
  * Background task loads each recording's wav, chunks it into 10-second
    windows, transcribes each chunk via the meeting's chosen ASR provider,
    collects results in memory.
  * On success: atomic single-transaction `DELETE FROM transcript_chunk
    WHERE meeting_id = ?` + `INSERT` of the new chunks. Failure: log + bail
    + leave existing transcript_chunk rows untouched (no partial state).
  * Idempotency: a second spawn while the first is in-flight returns False
    so the POST endpoint can map to HTTP 409 `rerun.busy`.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import wave
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.meetings.models import Meeting
from meeting_playbook.sessions.models import Recording, TranscriptChunk

logger = logging.getLogger(__name__)

# 10-second window is the same cadence the live capture service uses
# (slice-7); keeping it identical means re-run output aligns with the
# user's mental model of "transcript chunk = ~10s of audio".
_CHUNK_SECONDS = 10


@dataclass
class ChunksProgress:
    """Counters tracked while a re-run task is running.

    `total` starts at 0 and is set to the estimated chunk count once both
    recordings have been opened (the polling endpoint surfaces "(...)" while
    `total == 0` so the UI can render a placeholder during the brief gap).
    """

    processed: int = 0
    total: int = 0


# Process-scoped registries. Two parallel maps keyed by meeting_id so a
# polling GET only needs the meeting_id (no task handle).
_inflight: dict[str, asyncio.Task[None]] = {}
_progress: dict[str, ChunksProgress] = {}
_lock = asyncio.Lock()


def is_pending(meeting_id: str) -> bool:
    """True iff a re-run task is currently running for the meeting."""
    task = _inflight.get(meeting_id)
    return task is not None and not task.done()


def get_status(meeting_id: str) -> dict:
    """Polling-friendly snapshot for GET /rerun_asr_status.

    Shape matches the spec recording-retention requirement
    "GET /api/meetings/{id}/rerun_asr_status returns polling-friendly
    progress shape": always returns `{status, chunks_processed, chunks_total}`.
    """
    task = _inflight.get(meeting_id)
    if task is None or task.done():
        return {"status": "idle", "chunks_processed": 0, "chunks_total": 0}
    progress = _progress.get(meeting_id, ChunksProgress())
    return {
        "status": "pending",
        "chunks_processed": progress.processed,
        "chunks_total": progress.total,
    }


# ─── Wav loading + chunking ─────────────────────────────────────────


@dataclass(frozen=True)
class _AudioChunk:
    audio_bytes: bytes
    sample_rate_hz: int
    started_at: datetime
    ended_at: datetime
    speaker: str  # "me" | "counterparty"


def _load_wav_chunks(
    *,
    file_path: Path,
    speaker: str,
    base_started_at: datetime,
) -> Iterable[_AudioChunk]:
    """Yield successive _CHUNK_SECONDS-sized chunks of int16 PCM from a wav.

    Wav timestamps are reconstructed from `base_started_at` (the recording's
    `created_at`) plus the chunk's offset within the file. This is good
    enough for the re-run case: the original capture-service timestamps are
    irrecoverable and the user just needs sensible relative ordering.
    """
    with wave.open(str(file_path), "rb") as wf:
        sample_rate = wf.getframerate()
        sample_width = wf.getsampwidth()
        channels = wf.getnchannels()
        frames_per_chunk = sample_rate * _CHUNK_SECONDS
        bytes_per_frame = sample_width * channels

        chunk_idx = 0
        while True:
            audio_bytes = wf.readframes(frames_per_chunk)
            if not audio_bytes:
                return
            actual_frames = len(audio_bytes) // bytes_per_frame
            duration = timedelta(seconds=actual_frames / sample_rate)
            offset = timedelta(seconds=chunk_idx * _CHUNK_SECONDS)
            yield _AudioChunk(
                audio_bytes=audio_bytes,
                sample_rate_hz=sample_rate,
                started_at=base_started_at + offset,
                ended_at=base_started_at + offset + duration,
                speaker=speaker,
            )
            chunk_idx += 1


def _estimate_total_chunks(file_path: Path) -> int:
    """Cheap pre-pass: count chunks without loading audio frames."""
    with wave.open(str(file_path), "rb") as wf:
        total_frames = wf.getnframes()
        sample_rate = wf.getframerate()
    seconds = total_frames / sample_rate
    if seconds <= 0:
        return 0
    chunks, remainder = divmod(seconds, _CHUNK_SECONDS)
    return int(chunks) + (1 if remainder > 0 else 0)


# ─── Background task ─────────────────────────────────────────────────


async def _run(
    meeting_id: str,
    *,
    providers: dict[str, ASRProvider],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Re-run background coroutine.

    Steps:
      1. Open a fresh AsyncSession (the WS / HTTP request that triggered us
         is long gone; we don't share its session).
      2. Load meeting + recording rows.
      3. For each recording: estimate chunks + accumulate to `_progress.total`.
      4. For each recording: chunk + transcribe + accumulate results in memory.
      5. On full success: single transaction `DELETE FROM transcript_chunk
         WHERE meeting_id = ?` + ORM-add the new chunks + commit.
      6. On any inference failure: log + bail. Existing rows untouched, no
         partial state.
      7. `finally`: pop both registries.
    """
    progress = _progress[meeting_id]
    try:
        async with session_factory() as session:
            meeting = await session.get(Meeting, meeting_id)
            if meeting is None:
                logger.warning("rerun meeting=%s vanished mid-task", meeting_id)
                return

            recordings = await _list_recordings(session, meeting_id)
            available = [
                r for r in recordings if r.deleted_at is None and Path(r.file_path).exists()
            ]
            if not available:
                logger.warning("rerun meeting=%s has no on-disk recordings; aborting", meeting_id)
                return

            # Pre-pass: total chunk count (UI polling can stop showing "(...)" once we set it).
            progress.total = sum(_estimate_total_chunks(Path(r.file_path)) for r in available)

            # Inference pass: build ORM rows in memory; swap in one tx.
            now = datetime.now(UTC)
            new_rows: list[TranscriptChunk] = []
            for rec in available:
                speaker = rec.stream  # "me" / "counterparty" — slice-7 binary speaker label
                provider = providers[speaker]
                for audio in _load_wav_chunks(
                    file_path=Path(rec.file_path),
                    speaker=speaker,
                    base_started_at=rec.created_at,
                ):
                    result = await provider.transcribe_chunk(
                        audio_bytes=audio.audio_bytes,
                        sample_rate_hz=audio.sample_rate_hz,
                    )
                    progress.processed += 1
                    # Skip silent / no-speech chunks. Whisper has VAD
                    # filtering inside the model so its "transcribe a wav
                    # at chunk boundaries" path naturally returns empty
                    # for silence, but we'd still write a placeholder
                    # row — the live capture service avoids this by
                    # never sending silence to ASR in the first place.
                    # Re-run can't be that smart (we slice the whole wav
                    # at fixed 10s windows), so we filter here instead.
                    if not (result.text or "").strip():
                        continue
                    new_rows.append(
                        TranscriptChunk(
                            id=f"tc_{secrets.token_urlsafe(16)}",
                            meeting_id=meeting_id,
                            speaker=speaker,
                            text=result.text,
                            started_at=audio.started_at,
                            ended_at=audio.ended_at,
                            asr_provider_used=result.asr_provider_used,
                            confidence=result.confidence,
                            created_at=now,
                        )
                    )

            # Atomic swap: DELETE + INSERT in one transaction. The earlier
            # session.get(Meeting) opened a transaction implicitly; both
            # statements ride it and the `async with` exit commits.
            await session.execute(
                sql_text("DELETE FROM transcript_chunk WHERE meeting_id = :mid"),
                {"mid": meeting_id},
            )
            session.add_all(new_rows)
            await session.commit()
        logger.info("rerun meeting=%s replaced %d transcript_chunk rows", meeting_id, len(new_rows))
    except asyncio.CancelledError:
        logger.info("rerun meeting=%s cancelled", meeting_id)
        raise
    except Exception as exc:
        logger.exception(
            "rerun meeting=%s FAILED (existing rows preserved): %s: %s",
            meeting_id,
            type(exc).__name__,
            exc,
        )
    finally:
        _inflight.pop(meeting_id, None)
        _progress.pop(meeting_id, None)


async def _list_recordings(session: AsyncSession, meeting_id: str) -> list[Recording]:
    rows = await session.execute(
        select(Recording).where(Recording.meeting_id == meeting_id).order_by(Recording.stream.asc())
    )
    return list(rows.scalars().all())


# ─── Public spawn ────────────────────────────────────────────────────


async def spawn_rerun_task(
    meeting_id: str,
    *,
    providers: dict[str, ASRProvider],
    session_factory: async_sessionmaker[AsyncSession],
) -> bool:
    """Spawn a background re-run task for the meeting.

    Returns True iff a new task was actually created. Returns False when a
    task is already in-flight (POST endpoint maps False → HTTP 409
    `rerun.busy`).
    """
    async with _lock:
        existing = _inflight.get(meeting_id)
        if existing is not None and not existing.done():
            return False
        progress = ChunksProgress()
        task = asyncio.create_task(
            _run(meeting_id, providers=providers, session_factory=session_factory),
            name=f"rerun-{meeting_id}",
        )
        _inflight[meeting_id] = task
        _progress[meeting_id] = progress
    return True


__all__ = [
    "ChunksProgress",
    "_inflight",
    "_progress",
    "get_status",
    "is_pending",
    "spawn_rerun_task",
]
