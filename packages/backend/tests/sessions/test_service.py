"""SessionService — orchestration loop with mock ASR + mock capture.

Per spec meeting-session ADDED requirement scenarios:
- "Database write precedes client emission"
- "Failed insert prevents client emission"
- "Continuing silence does not flood the client"
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.audio.capture import AudioChunk, SilenceWarning
from meeting_playbook.sessions.service import SessionService, Stream

# ─── Mocks ─────────────────────────────────────────────────────────────────


class _MockASRProvider:
    name = "mock_asr"

    def __init__(self):
        self.calls: list[bytes] = []

    async def transcribe_chunk(
        self, audio_bytes: bytes, sample_rate_hz: int, language_hint: str | None = None
    ):
        self.calls.append(audio_bytes)
        return TranscriptChunk(
            text=f"transcript_{len(self.calls)}",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC) + timedelta(milliseconds=100),
            asr_provider_used=self.name,
            confidence=0.8,
        )


class _ScriptedCaptureSession:
    """Yields a pre-baked sequence of capture events."""

    def __init__(self, events: list):
        self._events = events

    async def events(self) -> AsyncIterator:
        for ev in self._events:
            yield ev
            await asyncio.sleep(0)


class _MockSessionRepo:
    def __init__(self, *, fail_on_insert: bool = False):
        self.chunks: list[dict] = []
        self.recordings: list[dict] = []
        self._fail_on_insert = fail_on_insert

    async def insert_chunk(self, **kwargs):
        if self._fail_on_insert:
            raise RuntimeError("simulated DB failure")
        self.chunks.append(kwargs)

    async def insert_recording(self, **kwargs):
        self.recordings.append(kwargs)


def _audio_chunk(stream: Stream = "me") -> AudioChunk:
    now = datetime.now(UTC)
    return AudioChunk(
        audio_bytes=b"\x00\x00" * 100,
        sample_rate_hz=16000,
        started_at=now,
        ended_at=now + timedelta(seconds=10),
        stream=stream,
    )


# ─── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_each_audio_chunk_results_in_asr_then_db_then_outbound_frame():
    """Order: capture → ASR → repo.insert_chunk → outbound transcript_chunk frame."""
    sent_frames: list[dict] = []

    async def send(frame: dict) -> None:
        sent_frames.append(frame)

    asr = _MockASRProvider()
    repo = _MockSessionRepo()
    capture = _ScriptedCaptureSession([_audio_chunk(), _audio_chunk()])

    service = SessionService(
        meeting_id="m_t",
        asr_provider=asr,
        session_repo=repo,
        send=send,
    )
    await service.run(capture)

    assert len(asr.calls) == 2
    assert len(repo.chunks) == 2
    transcript_frames = [f for f in sent_frames if f["type"] == "transcript_chunk"]
    assert len(transcript_frames) == 2
    # Ordering: every transcript frame's text matches a corresponding repo insert.
    for frame, persisted in zip(transcript_frames, repo.chunks):
        assert frame["text"] == persisted["text_content"]
        assert frame["meeting_id"] == "m_t"
        assert frame["speaker"] == "me"


@pytest.mark.asyncio
async def test_silence_warning_is_forwarded_as_outbound_frame():
    sent_frames: list[dict] = []

    async def send(frame: dict) -> None:
        sent_frames.append(frame)

    capture = _ScriptedCaptureSession([SilenceWarning(since=datetime.now(UTC))])
    service = SessionService(
        meeting_id="m_t",
        asr_provider=_MockASRProvider(),
        session_repo=_MockSessionRepo(),
        send=send,
    )
    await service.run(capture)

    silence_frames = [f for f in sent_frames if f["type"] == "silence_warning"]
    assert len(silence_frames) == 1
    assert silence_frames[0]["meeting_id"] == "m_t"


@pytest.mark.asyncio
async def test_repo_failure_emits_error_frame_and_exits():
    """Per spec: 'Failed insert prevents client emission' — emit error then stop."""
    sent_frames: list[dict] = []

    async def send(frame: dict) -> None:
        sent_frames.append(frame)

    capture = _ScriptedCaptureSession([_audio_chunk(), _audio_chunk()])
    service = SessionService(
        meeting_id="m_t",
        asr_provider=_MockASRProvider(),
        session_repo=_MockSessionRepo(fail_on_insert=True),
        send=send,
    )
    await service.run(capture)

    transcript_frames = [f for f in sent_frames if f["type"] == "transcript_chunk"]
    error_frames = [f for f in sent_frames if f["type"] == "error"]
    assert len(transcript_frames) == 0, "MUST NOT send transcript_chunk after a failed insert"
    assert len(error_frames) == 1
    assert error_frames[0]["error_code"] == "session.persist_failed"


# ─── Slice 7: dual-stream orchestration ────────────────────────────


class _MockCapture:
    """Mimics AudioCaptureService for tests — yields scripted events from `events()`."""

    def __init__(self, events: list, *, raise_after: int | None = None):
        self._events = events
        self._raise_after = raise_after  # if set, raise RuntimeError after yielding N events

    async def events(self):
        for idx, ev in enumerate(self._events):
            if self._raise_after is not None and idx >= self._raise_after:
                raise RuntimeError("simulated capture failure")
            yield ev
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_dual_stream_routes_chunks_per_speaker():
    """Each provider receives ONLY chunks from its own stream; transcript frames carry the right speaker."""
    sent_frames: list[dict] = []

    async def send(frame: dict) -> None:
        sent_frames.append(frame)

    me_provider = _MockASRProvider()
    cp_provider = _MockASRProvider()
    me_capture = _MockCapture([_audio_chunk("me"), _audio_chunk("me")])
    cp_capture = _MockCapture([_audio_chunk("counterparty"), _audio_chunk("counterparty")])

    service = SessionService(
        meeting_id="m_dual",
        captures={"me": me_capture, "counterparty": cp_capture},  # type: ignore[arg-type]
        providers={"me": me_provider, "counterparty": cp_provider},
        session_repo=_MockSessionRepo(),
        send=send,
    )
    await service.run()

    # Each provider transcribed exactly its own 2 chunks.
    assert len(me_provider.calls) == 2, "me provider must see only me chunks"
    assert len(cp_provider.calls) == 2, "counterparty provider must see only counterparty chunks"

    transcript_frames = [f for f in sent_frames if f["type"] == "transcript_chunk"]
    me_frames = [f for f in transcript_frames if f["speaker"] == "me"]
    cp_frames = [f for f in transcript_frames if f["speaker"] == "counterparty"]
    assert len(me_frames) == 2
    assert len(cp_frames) == 2


@pytest.mark.asyncio
async def test_stream_stopped_keeps_session_alive():
    """One stream's capture failure emits stream_stopped; the OTHER stream keeps emitting transcripts."""
    sent_frames: list[dict] = []

    async def send(frame: dict) -> None:
        sent_frames.append(frame)

    # me capture works fine (3 events); counterparty raises after the 1st event.
    me_capture = _MockCapture([_audio_chunk("me"), _audio_chunk("me"), _audio_chunk("me")])
    cp_capture = _MockCapture(
        [_audio_chunk("counterparty"), _audio_chunk("counterparty")],
        raise_after=1,
    )

    service = SessionService(
        meeting_id="m_fail",
        captures={"me": me_capture, "counterparty": cp_capture},  # type: ignore[arg-type]
        providers={"me": _MockASRProvider(), "counterparty": _MockASRProvider()},
        session_repo=_MockSessionRepo(),
        send=send,
    )
    await service.run()

    stopped_frames = [f for f in sent_frames if f["type"] == "stream_stopped"]
    error_frames = [f for f in sent_frames if f["type"] == "error"]
    transcript_frames = [f for f in sent_frames if f["type"] == "transcript_chunk"]

    assert len(stopped_frames) == 1, "expected exactly one stream_stopped frame"
    assert stopped_frames[0]["stream"] == "counterparty"
    assert error_frames == [], "stream failure MUST NOT emit a session-fatal error frame"

    # me produced 3 transcript chunks; counterparty produced 1 before crashing.
    me_transcripts = [f for f in transcript_frames if f["speaker"] == "me"]
    cp_transcripts = [f for f in transcript_frames if f["speaker"] == "counterparty"]
    assert len(me_transcripts) == 3
    assert len(cp_transcripts) == 1


@pytest.mark.asyncio
async def test_per_stream_silence_warning():
    """Silence on counterparty triggers `silence_warning` with stream='counterparty' only."""
    sent_frames: list[dict] = []

    async def send(frame: dict) -> None:
        sent_frames.append(frame)

    # me capture pushes audio; counterparty pushes a silence warning.
    me_capture = _MockCapture([_audio_chunk("me")])
    cp_capture = _MockCapture([SilenceWarning(since=datetime.now(UTC), stream="counterparty")])

    service = SessionService(
        meeting_id="m_silence",
        captures={"me": me_capture, "counterparty": cp_capture},  # type: ignore[arg-type]
        providers={"me": _MockASRProvider(), "counterparty": _MockASRProvider()},
        session_repo=_MockSessionRepo(),
        send=send,
    )
    await service.run()

    silence_frames = [f for f in sent_frames if f["type"] == "silence_warning"]
    assert len(silence_frames) == 1
    assert silence_frames[0]["stream"] == "counterparty"
    # me transcripts unaffected.
    me_transcripts = [
        f for f in sent_frames if f["type"] == "transcript_chunk" and f["speaker"] == "me"
    ]
    assert len(me_transcripts) == 1
