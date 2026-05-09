"""WebSocket router — /api/meetings/{id}/session.

Per slice-06 design ("WebSocket endpoint design"):
- Auth + ownership gate BEFORE the WebSocket accept handshake
- First client message MUST be `start_meeting` with matching id
- Atomic status transition scheduled → in_progress before capture starts
- One serial pipeline (SessionService) drives capture → ASR → persist → emit
- Client `end_meeting` OR client disconnect both finalize: capture closed,
  WAV file persisted to recording row, status → completed, meeting_ended sent
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_user_id_dependency,
)
from meeting_playbook.meetings.repository import (
    MeetingRepository,
    MeetingStatusConflict,
)
from meeting_playbook.sessions.dependencies import (
    CaptureFactory,
    get_asr_provider_dependency,
    get_capture_factory_dependency,
)
from meeting_playbook.sessions.messages import (
    EndMeetingMessage,
    ErrorMessage,
    MeetingEndedMessage,
    MeetingStartedMessage,
    StartMeetingMessage,
    parse_client_message,
)
from meeting_playbook.sessions.repository import SessionRepository
from meeting_playbook.sessions.service import SessionService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["sessions"])

# Custom WebSocket close codes (4000-4999 reserved for application use).
_CLOSE_AUTH_BYPASS = 4401
_CLOSE_NOT_FOUND = 4404


@router.get("/api/meetings/{meeting_id}/transcript_chunks")
async def list_transcript_chunks(
    meeting_id: str,
    user_id: Annotated[str, Depends(get_user_id_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> list[dict]:
    """Historical transcript chunks for a meeting (used after session ends)."""
    meeting = await MeetingRepository(session).get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail={"error_code": "meeting.not_found", "message": "Meeting not found"},
        )
    chunks = await SessionRepository(session).list_chunks_for_meeting(meeting_id)
    return [
        {
            "id": c.id,
            "meeting_id": c.meeting_id,
            "speaker": c.speaker,
            "text": c.text,
            "started_at": c.started_at.isoformat(),
            "ended_at": c.ended_at.isoformat(),
            "asr_provider_used": c.asr_provider_used,
            "confidence": c.confidence,
        }
        for c in chunks
    ]


@router.websocket("/api/meetings/{meeting_id}/session")
async def meeting_session_endpoint(
    websocket: WebSocket,
    meeting_id: str,
    asr_provider: Annotated[ASRProvider, Depends(get_asr_provider_dependency)],
    capture_factory: Annotated[CaptureFactory, Depends(get_capture_factory_dependency)],
    session: Annotated[AsyncSession, Depends(get_session_dependency)],
) -> None:
    user_id = websocket.headers.get("x-user-id")
    if not user_id:
        await websocket.close(code=_CLOSE_AUTH_BYPASS, reason="auth.gateway_bypass")
        return

    meeting_repo = MeetingRepository(session)
    meeting = await meeting_repo.get_for_user(user_id=user_id, meeting_id=meeting_id)
    if meeting is None:
        await websocket.close(code=_CLOSE_NOT_FOUND, reason="meeting.not_found")
        return

    await websocket.accept()

    # Helper: send a Pydantic message as JSON.
    async def _send(model_or_dict) -> None:
        if hasattr(model_or_dict, "model_dump_json"):
            await websocket.send_text(model_or_dict.model_dump_json())
        else:
            import json

            await websocket.send_text(json.dumps(model_or_dict))

    async def _send_error(code: str, message: str) -> None:
        await _send(ErrorMessage(error_code=code, message=message))

    # ─── Wait for the first client message: must be start_meeting ──────────
    try:
        raw = await websocket.receive_text()
        client_msg = parse_client_message(raw)
    except (ValidationError, ValueError) as exc:
        await _send_error("session.unknown_message", f"Invalid first message: {exc}")
        await websocket.close()
        return

    if not isinstance(client_msg, StartMeetingMessage):
        await _send_error("session.unknown_message", "Expected start_meeting first.")
        await websocket.close()
        return
    if client_msg.meeting_id != meeting_id:
        await _send_error(
            "session.bad_start",
            f"start_meeting id ({client_msg.meeting_id}) does not match path id ({meeting_id}).",
        )
        await websocket.close()
        return

    # ─── Transition status scheduled → in_progress ─────────────────────────
    try:
        await meeting_repo.transition_status(
            meeting_id=meeting_id, expected_from="scheduled", target="in_progress"
        )
        await session.commit()
    except MeetingStatusConflict:
        await _send_error(
            "session.bad_status",
            "Meeting is not in 'scheduled' status; cannot start a new session.",
        )
        await websocket.close()
        return

    await _send(MeetingStartedMessage(meeting_id=meeting_id))

    # ─── Run the orchestration loop until end_meeting OR client disconnect ─
    capture = capture_factory(meeting_id)
    session_repo = SessionRepository(session)
    service = SessionService(
        meeting_id=meeting_id,
        asr_provider=asr_provider,
        session_repo=session_repo,
        send=_send,
    )

    async def _client_listener() -> None:
        """Listen for the client's end_meeting (or disconnect); request stop."""
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = parse_client_message(raw)
                except (ValidationError, ValueError):
                    await _send_error(
                        "session.unknown_message",
                        "Unrecognized client message during session.",
                    )
                    return
                if isinstance(msg, EndMeetingMessage):
                    return
        finally:
            # Either end_meeting was received OR the client disconnected.
            # Request graceful stop on the capture; service.run will then
            # drain the queued chunks (including the final partial buffer)
            # and exit naturally instead of being cancelled mid-transcribe.
            await capture.stop()

    async def _capture_runner() -> None:
        async with capture:
            await service.run(capture)

    listener_task = asyncio.create_task(_client_listener())
    runner_task = asyncio.create_task(_capture_runner())

    # Wait for the runner to finish naturally — that guarantees all queued
    # chunks (including the final partial flush triggered by capture.stop())
    # are transcribed and emitted before we close the WS. If capture itself
    # crashes the task raises and we proceed to finalize.
    try:
        await runner_task
    except Exception as exc:
        logger.exception("capture/service runner failed: %s", exc)

    if not listener_task.done():
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await listener_task

    # ─── Finalize: persist recording row, status → completed, send meeting_ended ─
    try:
        wav_path = capture.wav_path
        wav_bytes = wav_path.stat().st_size if wav_path.exists() else 0
        await session_repo.insert_recording(
            meeting_id=meeting_id,
            stream="me",
            file_path=str(wav_path),
            bytes_size=wav_bytes,
        )
        with contextlib.suppress(MeetingStatusConflict):
            await meeting_repo.transition_status(
                meeting_id=meeting_id,
                expected_from="in_progress",
                target="completed",
            )
        await session.commit()
    except Exception as exc:
        logger.exception("Failed to finalize session for %s: %s", meeting_id, exc)

    with contextlib.suppress(Exception):
        await _send(MeetingEndedMessage(meeting_id=meeting_id))
        await websocket.close()
