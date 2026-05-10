"""Pydantic discriminated-union models for the WS message contract (slice-06).

Per spec meeting-session ADDED requirement "WebSocket message contract for
the meeting session". The frontend's TypeScript types in
`packages/web/src/lib/session-ws.ts` MUST mirror these shapes.
"""

from __future__ import annotations

from typing import Annotated, Literal

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
    stream: Literal["me", "counterparty"]
    since: str


class StreamStoppedMessage(BaseModel):
    """Slice-07: emitted when one capture stream fails mid-session.

    The other stream continues; the WebSocket stays open. Per design.md
    `Failure isolation: partial fault tolerance during in_progress`.
    """

    type: Literal["stream_stopped"] = "stream_stopped"
    meeting_id: str
    stream: Literal["me", "counterparty"]
    reason: str


class MeetingEndedMessage(BaseModel):
    type: Literal["meeting_ended"] = "meeting_ended"
    meeting_id: str


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    error_code: str
    message: str


# ─── Slice 8: TacticalAdvisor server frames ──────────────────────────────


class AdviceChunkMessage(BaseModel):
    """Slice-08: one Vertex Flash streaming token.

    Per ADR-0017 + ADR-0018; correlated with `RequestAdviceMessage.request_id`
    so multiple in-flight advice requests stay disambiguated on the wire.
    """

    type: Literal["advice_chunk"] = "advice_chunk"
    request_id: str
    token: str


class AdviceDoneMessage(BaseModel):
    """Slice-08: terminal frame for a successful advice stream."""

    type: Literal["advice_done"] = "advice_done"
    request_id: str


class AdvisorFailedMessage(BaseModel):
    """Slice-08: terminal frame for a failed advice stream.

    `error_code` is one of `advisor.{timeout,quota,auth,unknown}`; the UI
    looks the message up via `localizedErrorMessage(error_code, t)`.
    """

    type: Literal["advisor_failed"] = "advisor_failed"
    request_id: str
    error_code: str
    message: str


ServerMessage = Annotated[
    MeetingStartedMessage
    | TranscriptChunkMessage
    | SilenceWarningMessage
    | StreamStoppedMessage
    | MeetingEndedMessage
    | ErrorMessage
    | AdviceChunkMessage
    | AdviceDoneMessage
    | AdvisorFailedMessage,
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


# ─── Slice 8: TacticalAdvisor client frames ──────────────────────────────


class RequestAdviceMessage(BaseModel):
    """Slice-08: client → server request for tactical advice.

    Slice 8 ships a button-only path so `user_question` defaults to None.
    Slice 9 (chatbox) populates `user_question` with the user's typed prompt;
    the backend already reads it via `tactical_advisor.advise(...)`.
    """

    type: Literal["request_advice"] = "request_advice"
    request_id: str
    locale: Literal["zh-TW", "en"]
    user_question: str | None = None

    model_config = {"extra": "forbid"}


ClientMessage = Annotated[
    StartMeetingMessage | EndMeetingMessage | RequestAdviceMessage,
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
    "AdviceChunkMessage",
    "AdviceDoneMessage",
    "AdvisorFailedMessage",
    "ClientMessage",
    "EndMeetingMessage",
    "ErrorMessage",
    "MeetingEndedMessage",
    "MeetingStartedMessage",
    "RequestAdviceMessage",
    "ServerMessage",
    "SilenceWarningMessage",
    "StartMeetingMessage",
    "StreamStoppedMessage",
    "TranscriptChunkMessage",
    "parse_client_message",
    "parse_server_message",
]
