"""Wire-format schemas for the ASR runtime.

Both the HTTP route (`POST /v1/transcribe/chunk`) and the WebSocket route
(`/v1/transcribe/stream`) speak base64-encoded int16 PCM. Centralise the
encoder / decoder + the request / response pydantic models here so the two
transports stay aligned with `RemoteAsrRuntimeClient` on the backend side.
"""

from __future__ import annotations

import base64
from datetime import datetime

from pydantic import BaseModel, Field


class ChunkRequest(BaseModel):
    """Inbound HTTP / WebSocket audio chunk."""

    audio_bytes_b64: str = Field(..., description="base64-encoded int16 PCM bytes")
    sample_rate_hz: int = Field(16000, gt=0, le=48000)
    language_hint: str | None = Field(default=None, description="BCP-47 ish; e.g. zh, en")


class ChunkResponse(BaseModel):
    """Transcript chunk emitted back to the caller."""

    text: str
    started_at: datetime
    ended_at: datetime


class RuntimeError(BaseModel):
    """Structured error envelope. The backend's RemoteAsrRuntimeClient
    re-raises any frame matching this shape as AsrRuntimeUnavailableError."""

    error_code: str = "asr.runtime_unavailable"
    message: str
    retriable: bool = False


def encode_pcm_bytes(pcm_bytes: bytes) -> str:
    """Encode raw int16 PCM bytes for transport.

    Standard base64 (no URL-safe variants) so curl / browser dev tools can
    inspect frames without surprises.
    """
    return base64.standard_b64encode(pcm_bytes).decode("ascii")


def decode_pcm_bytes(audio_bytes_b64: str) -> bytes:
    """Decode a wire-format base64 string back to raw PCM bytes.

    Raises ValueError on malformed payloads — callers (the HTTP / WebSocket
    routes) translate that into a structured `asr.runtime_unavailable` error.
    """
    import binascii

    try:
        return binascii.a2b_base64(audio_bytes_b64, strict_mode=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"invalid base64 audio payload: {exc}") from exc
