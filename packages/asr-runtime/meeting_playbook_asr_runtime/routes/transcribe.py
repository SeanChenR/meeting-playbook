"""Transcribe routes — HTTP + WebSocket (tasks 3.2 / 4.2).

Both transports go through the same Qwen3Runner singleton (resolved via
`server._get_runner()` so tests can monkeypatch a stub). Any inference
failure is translated to the structured `asr.runtime_unavailable` error
envelope defined in `schemas.py`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from meeting_playbook_asr_runtime.errors import RuntimeUnavailableError
from meeting_playbook_asr_runtime.schemas import (
    ChunkRequest,
    ChunkResponse,
    decode_pcm_bytes,
)

if TYPE_CHECKING:
    from meeting_playbook_asr_runtime.qwen3_runner import Qwen3Runner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/transcribe", tags=["transcribe"])


@router.post("/chunk", response_model=ChunkResponse)
async def transcribe_chunk(payload: ChunkRequest) -> ChunkResponse:
    """Synchronous single-chunk transcription. Used by offline ingest."""
    runner = _resolve_runner()
    try:
        pcm = decode_pcm_bytes(payload.audio_bytes_b64)
    except ValueError as exc:
        raise RuntimeUnavailableError(f"invalid audio payload: {exc}") from exc

    try:
        chunk = await runner.transcribe(
            pcm,
            sample_rate_hz=payload.sample_rate_hz,
            language_hint=payload.language_hint,
        )
    except RuntimeUnavailableError:
        raise
    except Exception as exc:  # model crash, MPS OOM, etc.
        logger.exception("transcribe_chunk failed")
        raise RuntimeUnavailableError(str(exc)) from exc

    return ChunkResponse(text=chunk.text, started_at=chunk.started_at, ended_at=chunk.ended_at)


@router.websocket("/stream")
async def transcribe_stream(websocket: WebSocket) -> None:
    """Realtime per-session streaming. One config frame, then a loop of
    audio_chunk → transcript_chunk frames. Any error closes the socket
    after a final error frame."""
    await websocket.accept()

    sample_rate_hz = 16000
    language_hint: str | None = None
    runner: "Qwen3Runner | None" = None

    try:
        # Handshake — single config frame.
        first = await websocket.receive_json()
        if first.get("type") != "config":
            await _send_error_and_close(websocket, "expected first frame type=config")
            return
        sample_rate_hz = int(first.get("sample_rate_hz", 16000))
        language_hint = first.get("language_hint")

        runner = _resolve_runner()
        await runner.load()
        await websocket.send_json({"type": "ready"})

        while True:
            frame = await websocket.receive_json()
            if frame.get("type") != "audio_chunk":
                # Unknown frame types are ignored to keep the protocol
                # forward-compatible. Logging only.
                logger.debug("ignoring unknown ws frame type=%s", frame.get("type"))
                continue
            sequence = frame.get("sequence")
            try:
                pcm = decode_pcm_bytes(frame["audio_bytes_b64"])
                chunk = await runner.transcribe(
                    pcm,
                    sample_rate_hz=sample_rate_hz,
                    language_hint=language_hint,
                )
            except Exception as exc:
                logger.exception("transcribe_stream chunk failed")
                await _send_error_and_close(websocket, str(exc))
                return
            await websocket.send_json(
                {
                    "type": "transcript_chunk",
                    "sequence": sequence,
                    "text": chunk.text,
                    "started_at": chunk.started_at.isoformat(),
                    "ended_at": chunk.ended_at.isoformat(),
                }
            )
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.exception("transcribe_stream fatal")
        await _send_error_and_close(websocket, str(exc))


async def _send_error_and_close(websocket: WebSocket, message: str) -> None:
    """Emit the structured error envelope, then close the socket cleanly."""
    try:
        await websocket.send_json(
            {
                "type": "error",
                "error_code": "asr.runtime_unavailable",
                "message": message,
                "retriable": False,
            }
        )
    except Exception:
        # Socket may already be closing; nothing more we can do.
        pass
    try:
        await websocket.close(code=1000)
    except Exception:
        pass


def _resolve_runner() -> "Qwen3Runner":
    """Late-bound runner accessor — avoids a circular import at module load
    and lets tests monkeypatch `server._get_runner`."""
    from meeting_playbook_asr_runtime import server  # noqa: PLC0415

    return server._get_runner()
