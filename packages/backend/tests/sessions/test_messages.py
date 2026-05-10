"""WS message contract — Pydantic discriminated-union models for slice-06.

Per spec meeting-session ADDED requirement scenario "Example: minimum
required keys per server-side message type" — parametrized across all 5
server message types and 2 client message types.
"""

from __future__ import annotations

import pytest

from meeting_playbook.sessions.messages import (
    EndMeetingMessage,
    ErrorMessage,
    MeetingEndedMessage,
    MeetingStartedMessage,
    SilenceWarningMessage,
    StartMeetingMessage,
    TranscriptChunkMessage,
    parse_client_message,
    parse_server_message,
)


@pytest.mark.parametrize(
    "model_cls,kwargs,expected_type",
    [
        (
            MeetingStartedMessage,
            {"meeting_id": "m_t"},
            "meeting_started",
        ),
        (
            TranscriptChunkMessage,
            {
                "meeting_id": "m_t",
                "speaker": "me",
                "text": "hello",
                "started_at": "2026-05-09T10:00:00+00:00",
                "ended_at": "2026-05-09T10:00:10+00:00",
                "asr_provider_used": "whisper",
                "confidence": 0.9,
            },
            "transcript_chunk",
        ),
        (
            SilenceWarningMessage,
            {"meeting_id": "m_t", "stream": "me", "since": "2026-05-09T10:00:00+00:00"},
            "silence_warning",
        ),
        (
            MeetingEndedMessage,
            {"meeting_id": "m_t"},
            "meeting_ended",
        ),
        (
            ErrorMessage,
            {"error_code": "session.bad_start", "message": "bad start"},
            "error",
        ),
    ],
)
def test_server_message_round_trips_through_discriminated_union(model_cls, kwargs, expected_type):
    msg = model_cls(**kwargs)
    raw = msg.model_dump_json()
    reparsed = parse_server_message(raw)
    assert reparsed.type == expected_type
    assert isinstance(reparsed, model_cls)


@pytest.mark.parametrize(
    "model_cls,kwargs,expected_type",
    [
        (StartMeetingMessage, {"meeting_id": "m_t"}, "start_meeting"),
        (EndMeetingMessage, {"meeting_id": "m_t"}, "end_meeting"),
    ],
)
def test_client_message_round_trips_through_discriminated_union(model_cls, kwargs, expected_type):
    msg = model_cls(**kwargs)
    raw = msg.model_dump_json()
    reparsed = parse_client_message(raw)
    assert reparsed.type == expected_type
    assert isinstance(reparsed, model_cls)


def test_unknown_client_message_type_is_rejected():
    raw = '{"type": "noop", "meeting_id": "m_t"}'
    with pytest.raises(Exception):  # ValidationError or ValueError
        parse_client_message(raw)


def test_transcript_chunk_message_carries_all_required_keys():
    """Per spec example matrix row for transcript_chunk."""
    required = {
        "type",
        "meeting_id",
        "speaker",
        "text",
        "started_at",
        "ended_at",
        "asr_provider_used",
        "confidence",
    }
    msg = TranscriptChunkMessage(
        meeting_id="m_t",
        speaker="me",
        text="hi",
        started_at="2026-05-09T10:00:00+00:00",
        ended_at="2026-05-09T10:00:10+00:00",
        asr_provider_used="whisper",
        confidence=None,
    )
    actual = set(msg.model_dump().keys())
    assert required <= actual, f"missing keys: {required - actual}"


# ─── Slice 7 ──────────────────────────────────────────────────────


def test_stream_stopped_serialization():
    """Slice-07: StreamStopped accepts valid stream values, rejects invalid."""
    from meeting_playbook.sessions.messages import StreamStoppedMessage

    msg = StreamStoppedMessage(
        meeting_id="m_t",
        stream="counterparty",
        reason="BlackHole device disconnected",
    )
    raw = msg.model_dump_json()
    reparsed = parse_server_message(raw)
    assert reparsed.type == "stream_stopped"
    assert isinstance(reparsed, StreamStoppedMessage)
    assert reparsed.stream == "counterparty"
    assert reparsed.reason == "BlackHole device disconnected"


def test_stream_stopped_rejects_invalid_stream_value():
    """Slice-07: stream is Literal['me','counterparty'] — anything else fails."""
    from meeting_playbook.sessions.messages import StreamStoppedMessage

    with pytest.raises(Exception):  # ValidationError
        StreamStoppedMessage(meeting_id="m_t", stream="other", reason="x")


def test_silence_warning_includes_stream():
    """Slice-07: SilenceWarning now requires `stream` field; legacy payload (no stream) fails."""
    # New shape works.
    msg = SilenceWarningMessage(
        meeting_id="m_t",
        stream="me",
        since="2026-05-10T10:00:00+00:00",
    )
    raw = msg.model_dump_json()
    reparsed = parse_server_message(raw)
    assert reparsed.type == "silence_warning"
    assert isinstance(reparsed, SilenceWarningMessage)
    assert reparsed.stream == "me"

    # Old shape (no stream) MUST be rejected — backwards-incompatible by design.
    legacy = (
        '{"type": "silence_warning", "meeting_id": "m_t", "since": "2026-05-10T10:00:00+00:00"}'
    )
    with pytest.raises(Exception):  # ValidationError
        parse_server_message(legacy)
