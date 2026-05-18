"""Pydantic discriminated-union models for the WS message contract (slice-06).

Per spec meeting-session ADDED requirement "WebSocket message contract for
the meeting session". The frontend's TypeScript types in
`packages/web/src/lib/session-ws.ts` MUST mirror these shapes.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator

# Slice-12 (ADR-0029): transcript_chunk.speaker may be "me", "counterparty",
# or a single-channel cluster label `speaker_cluster_<N>` / `speaker_cluster_unknown`.
_SPEAKER_CLUSTER_RE = re.compile(r"^speaker_cluster_(\d+|unknown)$")
_BINARY_SPEAKERS: frozenset[str] = frozenset({"me", "counterparty"})

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

    @field_validator("speaker")
    @classmethod
    def _validate_speaker(cls, value: str) -> str:
        """Per slice-12 ADR-0029 / meeting-session spec: `speaker` SHALL be one
        of `me`, `counterparty`, `speaker_cluster_<N>` (N is 1+ digits), or
        `speaker_cluster_unknown`. Anything else is a contract violation —
        rejected here so the bug surfaces at frame construction time rather
        than reaching the wire.
        """
        if value in _BINARY_SPEAKERS:
            return value
        if _SPEAKER_CLUSTER_RE.match(value):
            return value
        raise ValueError(
            f"speaker={value!r} is not a valid attribution; expected "
            f"'me', 'counterparty', 'speaker_cluster_<N>', or 'speaker_cluster_unknown'"
        )


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


RecordingMode = Literal["dual", "single"]


class StartMeetingMessage(BaseModel):
    """Slice-27 (single-channel-recording-entry): `mode` chooses the recording
    pipeline. Missing field falls back to `"dual"` for backwards compatibility
    with older clients (Pydantic default). `"single"` triggers the mic-only
    path that skips the BlackHole pre-flight check. Anything else (incl.
    `null`, empty string, unknown literal) raises `ValidationError` and the
    router maps to `error_code: session.unknown_message`.

    Per design.md D2 — Mode 欄位的 wire contract; spec ADDED requirement
    "Pre-flight recording mode selector chooses dual-channel or
    single-channel capture".
    """

    type: Literal["start_meeting"] = "start_meeting"
    meeting_id: str
    mode: RecordingMode = "dual"

    model_config = {"extra": "forbid"}


class EndMeetingMessage(BaseModel):
    type: Literal["end_meeting"] = "end_meeting"
    meeting_id: str

    model_config = {"extra": "forbid"}


# ─── Slice 8: TacticalAdvisor client frames ──────────────────────────────


class RequestAdviceMessage(BaseModel):
    """Slice-08: client → server request for tactical advice (button path).

    Slice 9 keeps this frame for the `Get Advice` button. The chatbox path
    uses the new `ChatMessageRequestMessage` frame instead. `user_question`
    remains optional and defaults to None; the router fills the user_content
    with a locale-default prompt string before persisting.
    """

    type: Literal["request_advice"] = "request_advice"
    request_id: str
    locale: Literal["zh-TW", "en"]
    user_question: str | None = None

    model_config = {"extra": "forbid"}


class ChatMessageRequestMessage(BaseModel):
    """Slice-09: client → server chatbox follow-up.

    Distinct frame (not reusing `request_advice`) so the button vs chatbox
    paths stay traceable in logs + future analytics, per Issue #11
    acceptance criteria. `content` is the user's typed question and SHALL
    be non-empty; the router cancels any in-flight advice and spawns a new
    advise task with `user_question=content` plus the meeting's prior
    chat_history fetched from the DB.
    """

    type: Literal["chat_message"] = "chat_message"
    request_id: str
    content: str = Field(min_length=1)
    locale: Literal["zh-TW", "en"]

    model_config = {"extra": "forbid"}


ClientMessage = Annotated[
    StartMeetingMessage | EndMeetingMessage | RequestAdviceMessage | ChatMessageRequestMessage,
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
    "ChatMessageRequestMessage",
    "ClientMessage",
    "EndMeetingMessage",
    "ErrorMessage",
    "MeetingEndedMessage",
    "MeetingStartedMessage",
    "RecordingMode",
    "RequestAdviceMessage",
    "ServerMessage",
    "SilenceWarningMessage",
    "StartMeetingMessage",
    "StreamStoppedMessage",
    "TranscriptChunkMessage",
    "parse_client_message",
    "parse_server_message",
]
