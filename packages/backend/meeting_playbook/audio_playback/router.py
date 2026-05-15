"""GET /api/meetings/{id}/recordings/{recording_id}/audio — slice-16 task 4.1.

Range-aware audio streaming. Owner-gated via the `X-User-Id` header that
the auth gateway injects. Retention-expired recordings (`deleted_at IS
NOT NULL`) return 410 Gone so the frontend can disable play affordances
without leaking the file URL.
"""

from __future__ import annotations

from typing import Annotated, AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
