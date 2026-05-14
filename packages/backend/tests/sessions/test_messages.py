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


# ─── Slice 8: TacticalAdvisor frames ──────────────────────────────────────


def test_request_advice_serialization():
    """Slice-08: client → server `request_advice` round-trips through the
    discriminated union; `user_question` defaults to None (button path)."""
    from meeting_playbook.sessions.messages import RequestAdviceMessage

    msg = RequestAdviceMessage(request_id="req_abc", locale="zh-TW")
    assert msg.user_question is None  # default
    raw = msg.model_dump_json()
    reparsed = parse_client_message(raw)
    assert reparsed.type == "request_advice"
    assert isinstance(reparsed, RequestAdviceMessage)
    assert reparsed.request_id == "req_abc"
    assert reparsed.locale == "zh-TW"
    assert reparsed.user_question is None

    # With explicit user_question (slice-9 chatbox path).
    msg2 = RequestAdviceMessage(
        request_id="req_xyz", locale="en", user_question="What should I say next?"
    )
    raw2 = msg2.model_dump_json()
    reparsed2 = parse_client_message(raw2)
    assert isinstance(reparsed2, RequestAdviceMessage)
    assert reparsed2.user_question == "What should I say next?"


def test_request_advice_rejects_invalid_locale():
    """Slice-08: locale is Literal['zh-TW','en']; anything else is a 400."""
    from meeting_playbook.sessions.messages import RequestAdviceMessage

    with pytest.raises(Exception):  # ValidationError
        RequestAdviceMessage(request_id="req_a", locale="ja-JP")


def test_chat_message_frame_validates():
    """Slice-09: ChatMessageRequestMessage round-trips; empty content rejected."""
    from meeting_playbook.sessions.messages import ChatMessageRequestMessage

    msg = ChatMessageRequestMessage(request_id="r1", content="hi", locale="zh-TW")
    raw = msg.model_dump_json()
    reparsed = parse_client_message(raw)
    assert reparsed.type == "chat_message"
    assert isinstance(reparsed, ChatMessageRequestMessage)
    assert reparsed.content == "hi"
    assert reparsed.locale == "zh-TW"

    # Empty content MUST fail validation.
    with pytest.raises(Exception):  # ValidationError
        parse_client_message(
            '{"type": "chat_message", "request_id": "r1", "content": "", "locale": "zh-TW"}'
        )


def test_advice_chunk_done_failed_serialization():
    """Slice-08: server → client `advice_chunk` / `advice_done` /
    `advisor_failed` all round-trip through the server discriminated union."""
    from meeting_playbook.sessions.messages import (
        AdviceChunkMessage,
        AdviceDoneMessage,
        AdvisorFailedMessage,
    )

    chunk = AdviceChunkMessage(request_id="req_a", token="hello")
    raw = chunk.model_dump_json()
    reparsed = parse_server_message(raw)
    assert reparsed.type == "advice_chunk"
    assert isinstance(reparsed, AdviceChunkMessage)
    assert reparsed.request_id == "req_a"
    assert reparsed.token == "hello"

    done = AdviceDoneMessage(request_id="req_a")
    reparsed_done = parse_server_message(done.model_dump_json())
    assert reparsed_done.type == "advice_done"
    assert isinstance(reparsed_done, AdviceDoneMessage)

    failed = AdvisorFailedMessage(
        request_id="req_a",
        error_code="advisor.timeout",
        message="Vertex stream timed out after 15s",
    )
    reparsed_failed = parse_server_message(failed.model_dump_json())
    assert reparsed_failed.type == "advisor_failed"
    assert isinstance(reparsed_failed, AdvisorFailedMessage)
    assert reparsed_failed.error_code == "advisor.timeout"


# ─── Slice 12 (ADR-0029): transcript_chunk speaker value space ─────────


@pytest.mark.parametrize("speaker", ["me", "counterparty"])
def test_transcript_chunk_accepts_binary_speaker_values(speaker: str) -> None:
    """Existing dual-channel behaviour (ADR-0016) — `me` / `counterparty`
    SHALL still validate after slice 12 widens the value space.
    """
    msg = TranscriptChunkMessage(
        meeting_id="m_t",
        speaker=speaker,
        text="hi",
        started_at="2026-05-14T10:00:00+00:00",
        ended_at="2026-05-14T10:00:10+00:00",
        asr_provider_used="whisper",
    )
    assert msg.speaker == speaker


@pytest.mark.parametrize(
    "speaker", ["speaker_cluster_1", "speaker_cluster_42", "speaker_cluster_unknown"]
)
def test_transcript_chunk_accepts_single_channel_cluster_labels(speaker: str) -> None:
    """Slice-12 ADR-0029: single-channel sessions emit `speaker_cluster_<N>`
    or `speaker_cluster_unknown` labels.
    """
    msg = TranscriptChunkMessage(
        meeting_id="m_t",
        speaker=speaker,
        text="hi",
        started_at="2026-05-14T10:00:00+00:00",
        ended_at="2026-05-14T10:00:10+00:00",
        asr_provider_used="whisper",
    )
    assert msg.speaker == speaker


@pytest.mark.parametrize(
    "speaker",
    [
        "",
        "host",
        "speaker_cluster_",  # missing N
        "speaker_cluster_abc",  # non-numeric, non-unknown
        "Speaker_cluster_1",  # wrong case
        "speaker_cluster_-1",  # negative
        "me ",  # trailing whitespace
    ],
)
def test_transcript_chunk_rejects_invalid_speaker_values(speaker: str) -> None:
    """Per slice-12 spec, speaker values outside the agreed set are a
    contract violation rejected at construction time.
    """
    with pytest.raises(Exception):  # pydantic ValidationError
        TranscriptChunkMessage(
            meeting_id="m_t",
            speaker=speaker,
            text="hi",
            started_at="2026-05-14T10:00:00+00:00",
            ended_at="2026-05-14T10:00:10+00:00",
            asr_provider_used="whisper",
        )


def test_transcript_chunk_round_trips_cluster_label_through_parse() -> None:
    msg = TranscriptChunkMessage(
        meeting_id="m_t",
        speaker="speaker_cluster_2",
        text="hi",
        started_at="2026-05-14T10:00:00+00:00",
        ended_at="2026-05-14T10:00:10+00:00",
        asr_provider_used="whisper",
    )
    reparsed = parse_server_message(msg.model_dump_json())
    assert isinstance(reparsed, TranscriptChunkMessage)
    assert reparsed.speaker == "speaker_cluster_2"
