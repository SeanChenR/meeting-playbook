"""Offline ingest pipeline — staging → transcode → duration → recording row
→ ASR background task spawn.

Task 3.2 lands the duration enforcement helper. Task 4.1 adds the
surrounding orchestration in `run()`. Both share `_wav_duration_seconds`
and the `OfflineIngestTooLong` error.
"""

from __future__ import annotations

import logging
import secrets
import wave
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from meeting_playbook.offline_ingest import runtime
from meeting_playbook.offline_ingest.transcode import (
    OfflineIngestTranscodeError,
    transcode_to_canonical_wav,
)
from meeting_playbook.offline_ingest.tus_protocol import (
    TusSession,
    drop_session,
    set_completion_handler,
)
from meeting_playbook.sessions.models import Recording

logger = logging.getLogger(__name__)


class OfflineIngestTooLong(RuntimeError):
    """Raised when the transcoded WAV exceeds `OFFLINE_UPLOAD_MAX_DURATION_SECONDS`.

    Carries both the measured duration and the configured budget so callers
    can build a useful error message without re-reading the WAV header.
    """

    def __init__(self, *, duration_seconds: float, max_seconds: int) -> None:
        self.duration_seconds = duration_seconds
        self.max_seconds = max_seconds
        super().__init__(
            f"Transcoded audio duration {duration_seconds:.2f}s exceeds the "
            f"configured maximum of {max_seconds}s."
        )


def _wav_duration_seconds(wav_path: Path) -> float:
    """Read the WAV header and return its duration in seconds.

    Wrapped so the offline-ingest module can reuse a single duration
    primitive (vs duplicating the wave-open boilerplate across pipeline
    steps).
    """
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
    if rate <= 0:
        return 0.0
    return frames / rate


def enforce_max_duration(wav_path: Path, *, max_seconds: int) -> None:
    """Reject WAVs whose duration exceeds the configured maximum.

    Per spec `Post-transcode duration enforcement`: on rejection, unlink
    the WAV (so the disk leak does not accumulate over repeated bad
    uploads) and raise `OfflineIngestTooLong` carrying the measured
    duration.
    """
    duration = _wav_duration_seconds(wav_path)
    if duration > max_seconds:
        logger.warning(
            "offline_ingest_duration_over_budget",
            extra={
                "wav_path": str(wav_path),
                "duration_seconds": duration,
                "max_seconds": max_seconds,
            },
        )
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "offline_ingest_duration_unlink_failed",
                extra={"wav_path": str(wav_path)},
            )
        raise OfflineIngestTooLong(duration_seconds=duration, max_seconds=max_seconds)


# ─── Dependency look-ups (overridable in tests) ────────────────────────
#
# `pipeline.run` is invoked as a tus completion hook from a request scope
# the original handler has already left. We fetch the application-wide
# session factory + config lazily so the module stays import-clean for
# unit tests that only need `enforce_max_duration` (which avoids loading
# pydantic-settings / SQLAlchemy engine state).


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    from meeting_playbook.meetings.dependencies import get_session_factory_dependency

    return get_session_factory_dependency()


def _get_offline_upload_dir() -> Path:
    from meeting_playbook.config import get_settings

    return Path(get_settings().offline_upload_dir).expanduser()


def _get_max_duration_seconds() -> int:
    from meeting_playbook.config import get_settings

    return int(get_settings().offline_upload_max_duration_seconds)


def _build_asr_runner() -> Callable[[str], Awaitable[None]]:
    """Build the production ASR coroutine.

    Steps when invoked (`_runner(meeting_id)`):
      1. Open a fresh AsyncSession.
      2. Load the meeting + its single offline recording.
      3. Chunk the WAV into 10-second windows (mirroring rerun runtime).
      4. Transcribe each chunk with the meeting's ASR provider (qwen3 default);
         write `transcript_chunk` rows with provisional `speaker = "me"`.
      5. Call `apply_speaker_attribution` — single-channel finalize swaps
         `me` for `speaker_cluster_<N>` per pyannote diarization.
      6. Transition the meeting `in_progress → completed`.

    Tests can substitute the entire runner via
    `monkeypatch.setattr(pipeline, "_build_asr_runner", lambda: stub)`.
    """
    from sqlalchemy import select as _select

    from meeting_playbook.asr.factory import get_asr_providers_for_meeting
    from meeting_playbook.meetings.models import Meeting
    from meeting_playbook.meetings.repository import MeetingRepository
    from meeting_playbook.rerun.runtime import _load_wav_chunks
    from meeting_playbook.sessions.models import TranscriptChunk
    from meeting_playbook.sessions.repository import SessionRepository
    from meeting_playbook.speaker.finalize import apply_speaker_attribution

    async def _runner(meeting_id: str) -> None:
        session_factory = _get_session_factory()
        async with session_factory() as db:
            meeting = await db.get(Meeting, meeting_id)
            if meeting is None:
                raise RuntimeError(f"meeting {meeting_id!r} disappeared during ingest")
            recording = (
                await db.execute(_select(Recording).where(Recording.meeting_id == meeting_id))
            ).scalar_one()

            # `get_asr_providers_for_meeting` returns a `(me_provider,
            # counterparty_provider)` tuple. Single-channel ingest uses just
            # the me-side instance — both elements share the same model so
            # picking [0] is fine.
            providers = get_asr_providers_for_meeting(meeting.asr_provider)
            provider = providers[0]

            base_started_at = recording.started_at or recording.created_at
            now = datetime.now(UTC)

            progress = runtime.get_progress(meeting_id)
            # Pre-pass: estimate chunk count for the polling UI.
            from meeting_playbook.rerun.runtime import _estimate_total_chunks

            progress.total = _estimate_total_chunks(Path(recording.file_path))

            for audio in _load_wav_chunks(
                file_path=Path(recording.file_path),
                speaker="me",
                base_started_at=base_started_at,
            ):
                result = await provider.transcribe_chunk(
                    audio_bytes=audio.audio_bytes,
                    sample_rate_hz=audio.sample_rate_hz,
                )
                progress.processed += 1
                if not (result.text or "").strip():
                    continue
                db.add(
                    TranscriptChunk(
                        id=f"tc_{secrets.token_urlsafe(16)}",
                        meeting_id=meeting_id,
                        speaker="me",  # provisional; overwritten by SingleChannelStrategy
                        text=result.text,
                        started_at=audio.started_at,
                        ended_at=audio.ended_at,
                        asr_provider_used=result.asr_provider_used,
                        confidence=result.confidence,
                        created_at=now,
                    )
                )
            await db.flush()

            # Run speaker attribution — single-channel → SingleChannelStrategy
            # rewrites each chunk's speaker as `speaker_cluster_<N>`.
            await apply_speaker_attribution(meeting_id=meeting_id, repo=SessionRepository(db))

            await MeetingRepository(db).transition_status(
                meeting_id=meeting_id, expected_from="in_progress", target="completed"
            )
            await db.commit()

    return _runner


# ─── Main orchestration ────────────────────────────────────────────────


async def run(session: TusSession) -> None:
    """Orchestrate the post-upload offline-ingest pipeline.

    Steps:
      1. If a task is already in-flight for this meeting, mark the runtime
         state as `failed` with `error_code = "offline_ingest.busy"` and
         return without writing anything (avoid duplicate work / row).
      2. Transition runtime state to `transcoding`.
      3. Run ffmpeg → canonical 16kHz mono WAV under
         `{OFFLINE_UPLOAD_DIR}/{meeting_id}/source.wav`.
      4. Enforce the post-transcode duration budget.
      5. Insert a single `recording` row (source=offline, stream=me) and
         transition the meeting status `scheduled → in_progress`.
      6. Spawn the ASR background task via `runtime.spawn_ingest_task`.
      7. Drop the tus session (it is consumed once successful).

    Any failure between steps 3-5 surfaces as `runtime.set_error` with the
    appropriate `offline_ingest.*` code so the progress endpoint can
    report it to the frontend. The staging file is always removed,
    successfully or otherwise.
    """
    meeting_id = session.meeting_id

    if runtime.is_pending(meeting_id):
        logger.warning(
            "offline_ingest_busy meeting=%s upload_id=%s",
            meeting_id,
            session.upload_id,
        )
        runtime.set_error(meeting_id, "offline_ingest.busy")
        # Drop staging + session — second upload's bytes are not useful.
        session.staging_path.unlink(missing_ok=True)
        drop_session(session.upload_id)
        return

    runtime.set_state(meeting_id, runtime.STATE_TRANSCODING)

    upload_dir = _get_offline_upload_dir()
    output_path = upload_dir / meeting_id / "source.wav"

    try:
        await transcode_to_canonical_wav(staging_path=session.staging_path, output_path=output_path)
    except OfflineIngestTranscodeError:
        logger.exception("offline_ingest_transcode_failed meeting=%s", meeting_id)
        runtime.set_error(meeting_id, "offline_ingest.transcode_failed")
        drop_session(session.upload_id)
        return
    except Exception:
        logger.exception("offline_ingest_unexpected_transcode_error meeting=%s", meeting_id)
        runtime.set_error(meeting_id, "offline_ingest.transcode_failed")
        drop_session(session.upload_id)
        return

    try:
        enforce_max_duration(output_path, max_seconds=_get_max_duration_seconds())
    except OfflineIngestTooLong:
        logger.warning("offline_ingest_too_long meeting=%s", meeting_id)
        runtime.set_error(meeting_id, "offline_ingest.too_long")
        drop_session(session.upload_id)
        return

    bytes_on_disk = output_path.stat().st_size
    session_factory = _get_session_factory()

    try:
        async with session_factory() as db:
            rec = Recording(
                id=f"rec_{secrets.token_urlsafe(12)}",
                meeting_id=meeting_id,
                stream="me",
                file_path=str(output_path),
                bytes=bytes_on_disk,
                created_at=datetime.now(UTC),
                source="offline",
                started_at=session.actual_started_at,
            )
            db.add(rec)
            from meeting_playbook.meetings.repository import (
                MeetingRepository,
                MeetingStatusConflict,
            )

            try:
                await MeetingRepository(db).transition_status(
                    meeting_id=meeting_id,
                    expected_from="scheduled",
                    target="in_progress",
                )
            except MeetingStatusConflict:
                logger.warning(
                    "offline_ingest_status_conflict meeting=%s already past scheduled",
                    meeting_id,
                )
                runtime.set_error(meeting_id, "offline_ingest.conditions_not_met")
                drop_session(session.upload_id)
                return
            await db.commit()
    except Exception:
        logger.exception("offline_ingest_db_write_failed meeting=%s", meeting_id)
        runtime.set_error(meeting_id, "offline_ingest.db_write_failed")
        drop_session(session.upload_id)
        return

    runner = _build_asr_runner()
    spawned = await runtime.spawn_ingest_task(
        meeting_id,
        runner=runner,
        error_code_on_failure="offline_ingest.asr_failed",
    )
    if not spawned:
        # Lost a race against another simultaneously-completing upload.
        runtime.set_error(meeting_id, "offline_ingest.busy")
    drop_session(session.upload_id)


def install_completion_handler() -> None:
    """Wire `run()` as the tus completion hook. Called once at server
    startup so PATCH endpoints automatically kick off the pipeline when
    the final byte lands.
    """
    set_completion_handler(run)


# Auto-install at module import. Server.py imports the offline_ingest
# router which in turn imports this module via `pipeline`-typed callers,
# so this fires before any HTTP traffic.
install_completion_handler()
