"""WebSocket router — /api/meetings/{id}/session.

Slice-07 evolution: opens TWO capture streams (me + counterparty) via the
dual-stream capture factory. Pre-flight rejects the session with
`session.no_blackhole_device` when BlackHole is missing. Two ASRProviders
are warmed up in parallel before the first chunk arrives. Per-stream
failures during the session are handled inside SessionService and surface
as `stream_stopped` frames.

Per design.md (`Pre-flight check: device-exists only (relaxed)`,
`Failure isolation: partial fault tolerance during in_progress`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import AsyncExitStack
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from meeting_playbook.asr.base import ASRProvider
from meeting_playbook.audio.devices import MicDeviceNotFound, NoBlackholeDevice
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
    Stream,
    get_asr_providers_dependency,
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
    providers: Annotated[dict[Stream, ASRProvider], Depends(get_asr_providers_dependency)],
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

    async def _send(model_or_dict) -> None:
        if hasattr(model_or_dict, "model_dump_json"):
            await websocket.send_text(model_or_dict.model_dump_json())
        else:
            import json

            await websocket.send_text(json.dumps(model_or_dict))

    async def _send_error(code: str, message: str) -> None:
        await _send(ErrorMessage(error_code=code, message=message))

    # ─── First client message: must be start_meeting matching path id ─────
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

    # ─── Pre-flight: build the two captures (BlackHole + mic) ─────────────
    # The factory raises NoBlackholeDevice / MicDeviceNotFound on failure;
    # we map both to typed error frames before any status transition or
    # WebSocket teardown. Status remains `scheduled` so the user can retry
    # after fixing their audio config.
    try:
        captures = capture_factory(meeting_id)
    except NoBlackholeDevice as exc:
        await _send_error("session.no_blackhole_device", str(exc))
        await websocket.close()
        return
    except MicDeviceNotFound as exc:
        await _send_error("session.no_audio_device", str(exc))
        await websocket.close()
        return

    # ─── Transition status scheduled → in_progress ────────────────────────
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

    # ─── Warm up both providers in parallel — model load is the slowest
    # cold-start step (~10–25s on first ever run); running both providers
    # via asyncio.gather keeps the wall-clock cost equivalent to one. ────
    try:
        await asyncio.gather(*(p.warmup() for p in providers.values()))
    except Exception as exc:
        logger.exception("ASR warmup failed: %s", exc)
        await _send_error("session.stream_failed_at_start", f"ASR warmup failed: {exc}")
        # Roll status back so the user can retry.
        with contextlib.suppress(MeetingStatusConflict):
            await meeting_repo.transition_status(
                meeting_id=meeting_id,
                expected_from="in_progress",
                target="completed",
            )
            await session.commit()
        await websocket.close()
        return

    await _send(MeetingStartedMessage(meeting_id=meeting_id))

    session_repo = SessionRepository(session)
    service = SessionService(
        meeting_id=meeting_id,
        captures=captures,
        providers=providers,
        session_repo=session_repo,
        send=_send,
    )

    async def _client_listener() -> None:
        """Listen for end_meeting (or disconnect); request graceful capture stop."""
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
            # Gracefully stop both captures so service.run drains queued
            # chunks (including each capture's final partial buffer) before
            # the WebSocket finalizes.
            for cap in captures.values():
                with contextlib.suppress(Exception):
                    await cap.stop()

    async def _capture_runner() -> None:
        # AsyncExitStack atomically enters BOTH capture contexts. If either
        # fails to enter (e.g. RawInputStream couldn't open the device),
        # the stack closes anything that was already entered and re-raises.
        async with AsyncExitStack() as stack:
            try:
                for cap in captures.values():
                    await stack.enter_async_context(cap)
            except Exception as exc:
                logger.exception("Capture stream failed at start: %s", exc)
                with contextlib.suppress(Exception):
                    await _send_error("session.stream_failed_at_start", str(exc))
                return
            await service.run()

    listener_task = asyncio.create_task(_client_listener())
    runner_task = asyncio.create_task(_capture_runner())

    try:
        await runner_task
    except Exception as exc:
        logger.exception("capture/service runner failed: %s", exc)

    if not listener_task.done():
        listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await listener_task

    # ─── Finalize: persist per-stream recording rows, status → completed ──
    try:
        for stream_label, cap in captures.items():
            wav_path = cap.wav_path
            if wav_path.exists():
                wav_bytes = wav_path.stat().st_size
                # Skip zero-byte WAVs — per spec, a stream that produced no
                # audio MUST NOT cause a recording row to be written.
                if wav_bytes > 0:
                    await session_repo.insert_recording(
                        meeting_id=meeting_id,
                        stream=stream_label,
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
