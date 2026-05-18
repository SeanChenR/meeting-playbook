"""GET /api/meetings/{id}/recordings/{recording_id}/audio + mixed endpoint.

Range-aware audio streaming. Owner-gated via the `X-User-Id` header that
the auth gateway injects. Retention-expired recordings (`deleted_at IS
NOT NULL`) return 410 Gone so the frontend can disable play affordances
without leaking the file URL.

The mixed endpoint (slice-25) is registered BEFORE the parameterized
per-recording endpoint so `/recordings/mixed/audio` does not get caught
by the `{recording_id}=mixed` route.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.audio_playback.mixer import (
    MixerError,
    MixerInputMissing,
    ensure_mixed_wav,
)
from meeting_playbook.audio_playback.range_server import (
    AudioRangeServer,
    MalformedRange,
    RangeNotSatisfiable,
)
from meeting_playbook.audio_playback.wav_header import UnsupportedWavFormat
from meeting_playbook.config import get_settings
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.models import Meeting
from meeting_playbook.sessions.models import Recording

router = APIRouter(tags=["audio_playback"])


def _detail(code: str, message: str) -> dict[str, str]:
    return {"error_code": code, "message": message}


# IMPORTANT: register `/recordings/mixed/audio` BEFORE the parameterized
# `/recordings/{recording_id}/audio` route. FastAPI matches routes in
# registration order, so a request to `/recordings/mixed/audio` would
# otherwise match the parameterized route with `recording_id="mixed"`
# and return 404 `audio_playback.recording_not_found`.
@router.get("/api/meetings/{meeting_id}/recordings/mixed/audio")
async def get_recording_mixed_audio(
    meeting_id: str,
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    """Stream the dual-stream mix as Range-aware mono PCM WAV — slice-25 D1+D4.

    Lazy-mixes ``me.wav`` + ``counterparty.wav`` into ``mixed.wav`` on first
    request (idempotent — subsequent calls read the cached file). Single-channel
    meetings get 404 ``recording.mixed_not_applicable``; mix failures get 500
    ``recording.mix_failed`` (per design D7 / D9).
    """
    meeting = (
        await session.execute(select(Meeting).where(Meeting.id == meeting_id))
    ).scalar_one_or_none()
    if meeting is None or meeting.user_id != user_id:
        # Don't distinguish missing-vs-not-owned (no information leak).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_detail(
                "audio_playback.recording_not_found",
                f"Meeting {meeting_id} not found",
            ),
        )

    # Need a recording row for `started_at` to feed AudioRangeServer. Prefer
    # the me-stream row; fall back to counterparty.
    started_recording = (
        (
            await session.execute(
                select(Recording)
                .where(Recording.meeting_id == meeting_id)
                .order_by(Recording.stream.asc())
            )
        )
        .scalars()
        .first()
    )

    settings = get_settings()
    recordings_dir = Path(settings.recordings_dir).expanduser()
    try:
        mixed_path = ensure_mixed_wav(meeting_id, recordings_dir)
    except MixerInputMissing as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_detail("recording.mixed_not_applicable", str(e)),
        ) from e
    except (MixerError, OSError, ValueError) as e:
        # Mixer's except already removes its tmp; guard against future paths.
        tmp = recordings_dir / meeting_id / "mixed.wav.tmp"
        tmp.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_detail("recording.mix_failed", str(e)),
        ) from e

    now = datetime.now(UTC)
    started_at = started_recording.started_at if started_recording else now
    try:
        result = AudioRangeServer.serve(
            file_path=mixed_path,
            recording_started_at=started_at,
            chunk_start=started_at,
            chunk_end=now,
            range_header=range_header,
            max_bytes=settings.audio_range_max_bytes,
        )
    except MalformedRange as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail("audio_playback.malformed_range", str(e)),
        ) from e
    except RangeNotSatisfiable as e:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=_detail("audio_playback.range_not_satisfiable", str(e)),
        ) from e
    except UnsupportedWavFormat as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_detail("audio_playback.unsupported_format", str(e)),
        ) from e

    async def _async_body() -> AsyncIterator[bytes]:
        for chunk in result.body:
            yield chunk

    return StreamingResponse(
        _async_body(),
        status_code=result.status_code,
        headers=result.headers,
        media_type="audio/wav",
    )


@router.get("/api/meetings/{meeting_id}/recordings/{recording_id}/audio")
async def get_recording_audio(
    meeting_id: str,
    recording_id: str,
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> StreamingResponse:
    """Stream a 16 kHz mono PCM WAV recording, honoring HTTP Range."""
    recording = (
        await session.execute(select(Recording).where(Recording.id == recording_id))
    ).scalar_one_or_none()
    if recording is None or recording.meeting_id != meeting_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_detail(
                "audio_playback.recording_not_found",
                f"Recording {recording_id} not found for meeting {meeting_id}",
            ),
        )

    meeting = (
        await session.execute(select(Meeting).where(Meeting.id == meeting_id))
    ).scalar_one_or_none()
    if meeting is None or meeting.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_detail(
                "audio_playback.forbidden",
                "You do not own this recording's meeting",
            ),
        )

    if recording.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=_detail(
                "audio_playback.expired",
                "Recording exceeded the 30-day retention window",
            ),
        )

    file_path = Path(recording.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=_detail(
                "audio_playback.expired",
                "Recording file is no longer on disk",
            ),
        )

    settings = get_settings()
    now = datetime.now(UTC)
    try:
        result = AudioRangeServer.serve(
            file_path=file_path,
            recording_started_at=recording.started_at,
            chunk_start=recording.started_at,
            chunk_end=now,
            range_header=range_header,
            max_bytes=settings.audio_range_max_bytes,
        )
    except MalformedRange as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_detail("audio_playback.malformed_range", str(e)),
        ) from e
    except RangeNotSatisfiable as e:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail=_detail("audio_playback.range_not_satisfiable", str(e)),
        ) from e
    except UnsupportedWavFormat as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_detail("audio_playback.unsupported_format", str(e)),
        ) from e

    async def _async_body() -> AsyncIterator[bytes]:
        for chunk in result.body:
            yield chunk

    return StreamingResponse(
        _async_body(),
        status_code=result.status_code,
        headers=result.headers,
        media_type="audio/wav",
    )
