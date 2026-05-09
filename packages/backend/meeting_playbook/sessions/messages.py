"""Pydantic discriminated-union models for the WS message contract (slice-06).

Per spec meeting-session ADDED requirement "WebSocket message contract for
the meeting session". The frontend's TypeScript types in
`packages/web/src/lib/session-ws.ts` MUST mirror these shapes.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


# ─── Server → client ────────────────────────────────────────────────────────


class MeetingStartedMessage(BaseModel):
    type: Literal["meeting_started"] = "meeting_started"
    meeting_id: str


class TranscriptChunkMessage(BaseModel):
    type: Literal["transcript_chunk"] = "transcript_chunk"
    meeting_id: str
    speaker: str
    text: str
    started_at: str
    ended_at: str
    asr_provider_used: str
    confidence: float | None = None


class SilenceWarningMessage(BaseModel):
    type: Literal["silence_warning"] = "silence_warning"
    meeting_id: str
    since: str


class MeetingEndedMessage(BaseModel):
    type: Literal["meeting_ended"] = "meeting_ended"
    meeting_id: str


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    error_code: str
    message: str


ServerMessage = Annotated[
    Union[
        MeetingStartedMessage,
        TranscriptChunkMessage,
        SilenceWarningMessage,
        MeetingEndedMessage,
        ErrorMessage,
    ],
    Field(discriminator="type"),
]
_ServerAdapter = TypeAdapter(ServerMessage)


# ─── Client → server ────────────────────────────────────────────────────────


class StartMeetingMessage(BaseModel):
    type: Literal["start_meeting"] = "start_meeting"
    meeting_id: str

    model_config = {"extra": "forbid"}


class EndMeetingMessage(BaseModel):
    type: Literal["end_meeting"] = "end_meeting"
    meeting_id: str

    model_config = {"extra": "forbid"}


ClientMessage = Annotated[
    Union[StartMeetingMessage, EndMeetingMessage],
    Field(discriminator="type"),
]
_ClientAdapter = TypeAdapter(ClientMessage)


def parse_server_message(raw: str | bytes) -> ServerMessage:
    return _ServerAdapter.validate_json(raw)


def parse_client_message(raw: str | bytes) -> ClientMessage:
    """Parse and validate a client → server frame; raises ValidationError on bad input."""
    try:
        return _ClientAdapter.validate_json(raw)
    except ValidationError:
        raise


__all__ = [
    "ClientMessage",
    "EndMeetingMessage",
    "ErrorMessage",
    "MeetingEndedMessage",
    "MeetingStartedMessage",
    "ServerMessage",
    "SilenceWarningMessage",
    "StartMeetingMessage",
    "TranscriptChunkMessage",
    "parse_client_message",
    "parse_server_message",
]
