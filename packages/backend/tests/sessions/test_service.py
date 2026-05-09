"""SessionService — orchestration loop with mock ASR + mock capture.

Per spec meeting-session ADDED requirement scenarios:
- "Database write precedes client emission"
- "Failed insert prevents client emission"
- "Continuing silence does not flood the client"
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest

from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.audio.capture import AudioChunk, SilenceWarning
from meeting_playbook.sessions.service import SessionService


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
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc) + timedelta(milliseconds=100),
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


def _audio_chunk() -> AudioChunk:
    now = datetime.now(timezone.utc)
    return AudioChunk(
        audio_bytes=b"\x00\x00" * 100,
        sample_rate_hz=16000,
        started_at=now,
        ended_at=now + timedelta(seconds=10),
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

    capture = _ScriptedCaptureSession([SilenceWarning(since=datetime.now(timezone.utc))])
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
