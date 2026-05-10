"""Slice-08: WebSocket router — TacticalAdvisor integration.

Per spec tactical-advisor + meeting-session ADDED requirements:
- request_advice → advice_chunk* → advice_done sequence
- advisor failures emit `advisor_failed` and DON'T close the WS
- end_meeting cancels in-flight advice without leaking chunk frames
- advice runs in its own AsyncSession so it doesn't collide with the
  capture/transcribe write path
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect

from meeting_playbook.advisor.dependencies import get_tactical_advisor_dependency
from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.audio.capture import AudioChunk
from meeting_playbook.meetings.dependencies import (
    get_session_dependency,
    get_session_factory_dependency,
)
from meeting_playbook.server import create_app
from meeting_playbook.sessions.dependencies import (
    get_asr_providers_dependency,
    get_capture_factory_dependency,
)


# ─── Mocks ─────────────────────────────────────────────────────────────────


class _StubASRProvider:
    name = "mock_asr"

    async def warmup(self) -> None:
        return None

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        return TranscriptChunk(
            text="hello",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC) + timedelta(milliseconds=100),
            asr_provider_used=self.name,
            confidence=0.9,
        )


class _ScriptedCapture:
    def __init__(
        self,
        *,
        meeting_id: str,
        recordings_dir: Path,
        n_chunks: int = 2,
        stream_label: str = "me",
        chunk_delay_s: float = 0.0,
    ):
        self._n = n_chunks
        self.meeting_id = meeting_id
        self.recordings_dir = Path(recordings_dir)
        self.stream_label = stream_label
        self.wav_path = self.recordings_dir / meeting_id / f"{stream_label}.wav"
        self._chunk_delay_s = chunk_delay_s

    async def __aenter__(self):
        self.wav_path.parent.mkdir(parents=True, exist_ok=True)
        self.wav_path.write_bytes(b"\x00" * 100)
        return self

    async def __aexit__(self, *exc):
        return None

    async def stop(self) -> None:
        return None

    async def events(self) -> AsyncIterator[AudioChunk]:
        for _ in range(self._n):
            now = datetime.now(UTC)
            yield AudioChunk(
                audio_bytes=b"\x00\x00" * 100,
                sample_rate_hz=16000,
                started_at=now,
                ended_at=now + timedelta(seconds=1),
                stream=self.stream_label,
            )
            if self._chunk_delay_s:
                await asyncio.sleep(self._chunk_delay_s)
            else:
                await asyncio.sleep(0)


class _ScriptedAdvisor:
    """Test advisor: yields a fixed list of tokens with optional inter-token delay."""

    def __init__(self, tokens: list[str], *, per_token_delay_s: float = 0.0):
        self._tokens = tokens
        self._delay = per_token_delay_s

    async def advise(
        self,
        meeting_id,
        recent_chunks,
        playbook,
        me_display_name,
        counterparty_display_name,
        user_question,
        locale,
    ):
        for tok in self._tokens:
            if self._delay:
                await asyncio.sleep(self._delay)
            yield tok


class _RaisingAdvisor:
    """Test advisor: raises an exception with the configured class name."""

    def __init__(self, exc: BaseException):
        self._exc = exc

    async def advise(
        self,
        meeting_id,
        recent_chunks,
        playbook,
        me_display_name,
        counterparty_display_name,
        user_question,
        locale,
    ):
        raise self._exc
        yield ""  # pragma: no cover — make this an async generator


class _SlowAdvisor:
    """Test advisor: hangs forever (used to test cancellation on end_meeting)."""

    async def advise(
        self,
        meeting_id,
        recent_chunks,
        playbook,
        me_display_name,
        counterparty_display_name,
        user_question,
        locale,
    ):
        await asyncio.sleep(60)
        yield "should-never-arrive"  # pragma: no cover


# Forge ResourceExhausted-shaped exception so the router's duck-typed
# classifier maps it to advisor.quota without importing google.api_core.
class ResourceExhausted(Exception):
    pass


# ─── DB helpers ────────────────────────────────────────────────────────────


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


async def _setup_meeting(db_url: str, *, user_id: str, meeting_id: str):
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        await s.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"{user_id}@example.com"},
        )
        await s.execute(
            text(
                """
                INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name, status)
                VALUES (:mid, :uid, 'T', 'C', 'M', 'scheduled')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
        await s.commit()
    await engine.dispose()


async def _truncate(db_url: str):
    engine = create_async_engine(db_url, future=True)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "playbook" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


def _build_client(
    db_url_sync: str,
    *,
    capture_factory_override,
    advisor_override,
    providers_override=None,
) -> TestClient:
    db_url_async = _async_url(db_url_sync)
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    app.dependency_overrides[get_capture_factory_dependency] = lambda: capture_factory_override
    app.dependency_overrides[get_asr_providers_dependency] = lambda: (
        providers_override or {"me": _StubASRProvider(), "counterparty": _StubASRProvider()}
    )
    app.dependency_overrides[get_tactical_advisor_dependency] = lambda: advisor_override
    # Slice-08: the advisor opens its own AsyncSession via session_factory.
    # Point it at the test DB engine, NOT the cached application engine.
    app.dependency_overrides[get_session_factory_dependency] = lambda: Session
    return TestClient(app)


def _make_capture_factory(tmp_path: Path, n_chunks: int = 2, chunk_delay_s: float = 0.0):
    def factory(meeting_id: str):
        return {
            "me": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=n_chunks,
                stream_label="me",
                chunk_delay_s=chunk_delay_s,
            ),
            "counterparty": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=n_chunks,
                stream_label="counterparty",
                chunk_delay_s=chunk_delay_s,
            ),
        }

    return factory


# ─── Tests ─────────────────────────────────────────────────────────────────


def test_request_advice_streams_chunks_then_done(_migrated_db_url, tmp_path):
    """Slice-08: client `request_advice` → 3 `advice_chunk` frames + 1 `advice_done`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_ad", meeting_id="m_ad"))

    advisor = _ScriptedAdvisor(["alpha ", "beta ", "gamma"])
    # Long-running capture (10 chunks each at 50ms delay) so the WS stays
    # open long enough for advice frames to flow through end-to-end before
    # the session naturally finalizes.
    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=10, chunk_delay_s=0.05),
        advisor_override=advisor,
    )
    advice_chunks: list[str] = []
    advice_done_seen = False
    saw_meeting_started = False
    with client.websocket_connect(
        "/api/meetings/m_ad/session", headers={"X-User-Id": "u_ad"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_ad"}))
        # Wait for meeting_started before sending request_advice (server
        # must be past warmup so the listener is reading frames).
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    saw_meeting_started = True
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "request_advice",
                                "request_id": "req_1",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "advice_chunk":
                    assert msg["request_id"] == "req_1"
                    advice_chunks.append(msg["token"])
                elif msg["type"] == "advice_done":
                    assert msg["request_id"] == "req_1"
                    advice_done_seen = True
                    # End the meeting once we've seen the terminal frame so
                    # the test doesn't have to drain all 20 transcript chunks.
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_ad"}))
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert saw_meeting_started, "meeting_started must precede request_advice"
    assert advice_chunks == ["alpha ", "beta ", "gamma"]
    assert advice_done_seen


def test_vertex_quota_error_emits_advisor_failed_and_keeps_ws_open(_migrated_db_url, tmp_path):
    """Slice-08: ResourceExhausted from advisor → `advisor_failed` `advisor.quota`;
    WS stays open and continues to deliver transcript_chunk frames."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_q", meeting_id="m_q"))

    advisor = _RaisingAdvisor(ResourceExhausted("429 quota exceeded"))
    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=10, chunk_delay_s=0.05),
        advisor_override=advisor,
    )
    seen_advisor_failed: dict | None = None
    seen_transcript_after_failure = False
    with client.websocket_connect("/api/meetings/m_q/session", headers={"X-User-Id": "u_q"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_q"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "request_advice",
                                "request_id": "req_q",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "advisor_failed":
                    seen_advisor_failed = msg
                elif msg["type"] == "transcript_chunk" and seen_advisor_failed is not None:
                    seen_transcript_after_failure = True
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_q"}))
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert seen_advisor_failed is not None, "advisor_failed frame must be sent"
    assert seen_advisor_failed["error_code"] == "advisor.quota", f"got {seen_advisor_failed!r}"
    assert seen_advisor_failed["request_id"] == "req_q"
    assert seen_transcript_after_failure, "WS must stay open after advisor_failed"


def test_end_meeting_cancels_in_flight_advice(_migrated_db_url, tmp_path):
    """Slice-08: a slow advice stream cancelled by end_meeting MUST NOT
    leak any further `advice_chunk` frames. `meeting_ended` arrives
    normally."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_ec", meeting_id="m_ec"))

    advisor = _SlowAdvisor()
    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=2),
        advisor_override=advisor,
    )
    chunk_count = 0
    saw_meeting_ended = False
    with client.websocket_connect(
        "/api/meetings/m_ec/session", headers={"X-User-Id": "u_ec"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_ec"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "request_advice",
                                "request_id": "req_ec",
                                "locale": "zh-TW",
                            }
                        )
                    )
                    # Immediately end the meeting — advisor is still hung.
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_ec"}))
                elif msg["type"] == "advice_chunk":
                    chunk_count += 1
                elif msg["type"] == "meeting_ended":
                    saw_meeting_ended = True
                    break
        except WebSocketDisconnect:
            pass

    assert chunk_count == 0, "in-flight advice must be cancelled silently"
    assert saw_meeting_ended


def test_advice_during_active_capture_uses_separate_session(_migrated_db_url, tmp_path):
    """Slice-08: advice runs concurrent with capture+transcribe writes.
    SQLAlchemy raises InvalidRequestError if two coroutines share a session;
    the router opens a fresh session for each advice request to avoid this.
    The test asserts BOTH transcript_chunk AND advice_chunk frames flow
    over a several-chunk window with no error frame surfacing."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_cc", meeting_id="m_cc"))

    advisor = _ScriptedAdvisor(["one ", "two ", "three"], per_token_delay_s=0.05)
    # Stream of capture chunks runs throughout the test so transcript writes
    # and the advice read overlap in time.
    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=20, chunk_delay_s=0.02),
        advisor_override=advisor,
    )
    transcript_count = 0
    advice_count = 0
    error_codes: list[str] = []
    advice_done_seen = False
    with client.websocket_connect(
        "/api/meetings/m_cc/session", headers={"X-User-Id": "u_cc"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_cc"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "request_advice",
                                "request_id": "req_cc",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "transcript_chunk":
                    transcript_count += 1
                elif msg["type"] == "advice_chunk":
                    advice_count += 1
                elif msg["type"] == "advice_done":
                    advice_done_seen = True
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_cc"}))
                elif msg["type"] == "advisor_failed":
                    # Surface to the assertion so we can read the code.
                    error_codes.append(msg["error_code"])
                elif msg["type"] == "error":
                    error_codes.append(msg["error_code"])
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert error_codes == [], f"unexpected error frames: {error_codes}"
    assert advice_done_seen, "advice must complete cleanly under concurrent capture"
    assert advice_count == 3
    assert transcript_count > 0, "capture must keep flowing during advice"
