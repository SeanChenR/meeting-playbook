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

import pytest
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
from meeting_playbook.sessions.dependencies import get_capture_factory_dependency

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
        chat_history=(),
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
        chat_history=(),
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
        chat_history=(),
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
        await conn.execute(text('TRUNCATE TABLE "chat_message" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "playbook" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


async def _read_chat_messages(db_url: str, meeting_id: str) -> list[tuple[str, str]]:
    """Read chat_message rows for a meeting in created_at ASC order."""
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, future=True)
    async with Session() as s:
        rows = await s.execute(
            text(
                "SELECT role, content FROM chat_message "
                "WHERE meeting_id = :mid ORDER BY created_at ASC"
            ),
            {"mid": meeting_id},
        )
        out = [(r.role, r.content) for r in rows]
    await engine.dispose()
    return out


async def _seed_chat_messages(
    db_url: str, *, meeting_id: str, pairs: list[tuple[str, str]]
) -> None:
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        from meeting_playbook.chat.repository import ChatMessageRepository

        repo = ChatMessageRepository(s)
        for user_content, advisor_content in pairs:
            await repo.insert_pair_after_advice(
                meeting_id=meeting_id,
                user_content=user_content,
                advisor_content=advisor_content,
            )
    await engine.dispose()


def _build_client(
    db_url_sync: str,
    monkeypatch: pytest.MonkeyPatch,
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
    app.dependency_overrides[get_tactical_advisor_dependency] = lambda: advisor_override
    # Slice-08: the advisor opens its own AsyncSession via session_factory.
    # Point it at the test DB engine, NOT the cached application engine.
    app.dependency_overrides[get_session_factory_dependency] = lambda: Session

    # Slice-11: ASR provider selection moved out of FastAPI Depends; tests
    # patch the router's imported factory function instead.
    if providers_override is None:
        me_p, cp_p = _StubASRProvider(), _StubASRProvider()
    elif isinstance(providers_override, dict):
        me_p = providers_override["me"]
        cp_p = providers_override["counterparty"]
    else:
        me_p, cp_p = providers_override
    monkeypatch.setattr(
        "meeting_playbook.sessions.router.get_asr_providers_for_meeting",
        lambda _name: (me_p, cp_p),
    )
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


def test_request_advice_streams_chunks_then_done(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-08: client `request_advice` → 3 `advice_chunk` frames + 1 `advice_done`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_ad", meeting_id="m_ad"))

    advisor = _ScriptedAdvisor(["alpha ", "beta ", "gamma"])
    # Long-running capture (10 chunks each at 50ms delay) so the WS stays
    # open long enough for advice frames to flow through end-to-end before
    # the session naturally finalizes.
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
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


def test_vertex_quota_error_emits_advisor_failed_and_keeps_ws_open(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-08: ResourceExhausted from advisor → `advisor_failed` `advisor.quota`;
    WS stays open and continues to deliver transcript_chunk frames."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_q", meeting_id="m_q"))

    advisor = _RaisingAdvisor(ResourceExhausted("429 quota exceeded"))
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
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


def test_end_meeting_cancels_in_flight_advice(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-08: a slow advice stream cancelled by end_meeting MUST NOT
    leak any further `advice_chunk` frames. `meeting_ended` arrives
    normally."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_ec", meeting_id="m_ec"))

    advisor = _SlowAdvisor()
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
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


def test_advice_during_active_capture_uses_separate_session(
    _migrated_db_url, tmp_path, monkeypatch
):
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
        monkeypatch,
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


# ─── Slice 9: chatbox path + INSERT-pair-on-success + cancel-previous ─────


class _ChatHistoryRecordingAdvisor:
    """Test advisor: records the chat_history kwarg it receives, yields fixed tokens."""

    def __init__(self, tokens: list[str]):
        self._tokens = tokens
        self.received_chat_history: list = []  # populated on each advise() call

    async def advise(
        self,
        meeting_id,
        recent_chunks,
        playbook,
        me_display_name,
        counterparty_display_name,
        user_question,
        locale,
        chat_history=(),
    ):
        # Capture the rows as plain (role, content) tuples to avoid relying
        # on ORM identity across the test boundary.
        self.received_chat_history = [(m.role, m.content) for m in chat_history]
        for tok in self._tokens:
            yield tok


def test_chat_message_frame_streams_advice_and_inserts_pair_on_done(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-09 4.3: chatbox `chat_message` frame → 3 advice_chunk → advice_done →
    DB has user row + advisor row with the right contents."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_cb", meeting_id="m_cb"))

    advisor = _ScriptedAdvisor(["alpha ", "beta ", "gamma"])
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=10, chunk_delay_s=0.05),
        advisor_override=advisor,
    )
    advice_chunks: list[str] = []
    advice_done_seen = False
    with client.websocket_connect(
        "/api/meetings/m_cb/session", headers={"X-User-Id": "u_cb"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_cb"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "chat_message",
                                "request_id": "r_cb",
                                "content": "對方剛說 X 怎麼回",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "advice_chunk":
                    assert msg["request_id"] == "r_cb"
                    advice_chunks.append(msg["token"])
                elif msg["type"] == "advice_done":
                    assert msg["request_id"] == "r_cb"
                    advice_done_seen = True
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_cb"}))
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert advice_chunks == ["alpha ", "beta ", "gamma"]
    assert advice_done_seen

    rows = asyncio.run(_read_chat_messages(_async_url(_migrated_db_url), "m_cb"))
    assert rows == [("user", "對方剛說 X 怎麼回"), ("advisor", "alpha beta gamma")]


def test_request_advice_button_path_inserts_pair_with_default_user_content(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-09 4.4: button path's user row uses the locale-default prompt string."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_btn", meeting_id="m_btn"))

    advisor = _ScriptedAdvisor(["建議內容"])
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=10, chunk_delay_s=0.05),
        advisor_override=advisor,
    )
    saw_done = False
    with client.websocket_connect(
        "/api/meetings/m_btn/session", headers={"X-User-Id": "u_btn"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_btn"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "request_advice",
                                "request_id": "r_btn",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "advice_done":
                    saw_done = True
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_btn"}))
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert saw_done
    rows = asyncio.run(_read_chat_messages(_async_url(_migrated_db_url), "m_btn"))
    assert rows == [("user", "請給出戰術建議。"), ("advisor", "建議內容")]


def test_failed_advice_writes_no_chat_message_rows(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-09 4.5: ResourceExhausted from advisor → no DB rows written."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_fl", meeting_id="m_fl"))

    advisor = _RaisingAdvisor(ResourceExhausted("429 quota exceeded"))
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=10, chunk_delay_s=0.05),
        advisor_override=advisor,
    )
    seen_failed = None
    with client.websocket_connect(
        "/api/meetings/m_fl/session", headers={"X-User-Id": "u_fl"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_fl"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "chat_message",
                                "request_id": "r_fl",
                                "content": "Q",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "advisor_failed":
                    seen_failed = msg
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_fl"}))
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert seen_failed is not None
    assert seen_failed["error_code"] == "advisor.quota"
    rows = asyncio.run(_read_chat_messages(_async_url(_migrated_db_url), "m_fl"))
    assert rows == [], f"failed advice must not persist any chat_message; got {rows}"


def test_chat_message_cancels_prior_in_flight_advice_no_pair_written_for_cancelled(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-09 4.6: superseding chat_message cancels prior task → only the
    second turn's pair persists; the cancelled first turn writes nothing."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_cn", meeting_id="m_cn"))

    # First send uses a slow advisor that will be cancelled. We swap the
    # advisor override AFTER the first send by patching the dependency
    # override (FastAPI re-resolves overrides per request, and the WS
    # endpoint takes the advisor as a single Depends-injected singleton at
    # connect time — so we can't actually swap mid-WS. Use a stateful advisor
    # instead that hangs the FIRST call and yields a token on the second).
    class _OncePerSecondCallAdvisor:
        """Two-state advisor: first call hangs (so it can be cancelled),
        second call completes immediately. Counter increments at advise()
        invocation (NOT inside the generator body) so it's deterministic
        even if the first generator is cancelled before any __anext__.
        """

        def __init__(self):
            self._call_count = 0

        def advise(
            self,
            meeting_id,
            recent_chunks,
            playbook,
            me_display_name,
            counterparty_display_name,
            user_question,
            locale,
            chat_history=(),
        ):
            self._call_count += 1
            n = self._call_count
            return self._stream(n)

        async def _stream(self, n: int):
            if n == 1:
                await asyncio.sleep(60)
                yield "should-not-arrive"  # pragma: no cover
            else:
                yield "OK"

    advisor = _OncePerSecondCallAdvisor()
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=20, chunk_delay_s=0.05),
        advisor_override=advisor,
    )
    saw_done = False
    received: list[dict] = []
    with client.websocket_connect(
        "/api/meetings/m_cn/session", headers={"X-User-Id": "u_cn"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_cn"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                received.append(msg)
                if msg["type"] == "meeting_started":
                    # First send — will hang on the slow advisor.
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "chat_message",
                                "request_id": "r_a",
                                "content": "A",
                                "locale": "zh-TW",
                            }
                        )
                    )
                    # Brief pause so task A actually starts executing (and
                    # bumps the advisor's call counter to 1) before the
                    # superseding send arrives. Without this the test races:
                    # task A may be cancelled before its body ever runs, so
                    # task B becomes call #1 and also hangs.
                    import time as _time

                    _time.sleep(0.2)
                    # Second send — cancels the first task.
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "chat_message",
                                "request_id": "r_b",
                                "content": "B",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "advice_done":
                    assert msg["request_id"] == "r_b", (
                        f"only the superseding (B) request should reach advice_done; got {msg}"
                    )
                    saw_done = True
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_cn"}))
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert saw_done, f"never saw advice_done; received frames: {[f.get('type') for f in received]}"
    rows = asyncio.run(_read_chat_messages(_async_url(_migrated_db_url), "m_cn"))
    # ONLY the second pair persists — the cancelled first call must NOT
    # have written anything.
    contents = [c for _r, c in rows]
    assert "A" not in contents, f"cancelled first turn must not persist; got {rows}"
    assert rows == [("user", "B"), ("advisor", "OK")]


def test_chat_message_passes_chat_history_from_db_to_advise(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-09 4.7: prior chat_message rows are fetched from DB and passed
    to advisor.advise(chat_history=...) in created_at order."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_h", meeting_id="m_h"))
    asyncio.run(
        _seed_chat_messages(
            _async_url(_migrated_db_url),
            meeting_id="m_h",
            pairs=[("Q1", "A1"), ("Q2", "A2")],
        )
    )

    advisor = _ChatHistoryRecordingAdvisor(["new-tok"])
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=10, chunk_delay_s=0.05),
        advisor_override=advisor,
    )
    with client.websocket_connect("/api/meetings/m_h/session", headers={"X-User-Id": "u_h"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_h"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "chat_message",
                                "request_id": "r_h",
                                "content": "Q3",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "advice_done":
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_h"}))
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert advisor.received_chat_history == [
        ("user", "Q1"),
        ("advisor", "A1"),
        ("user", "Q2"),
        ("advisor", "A2"),
    ], "advisor must receive prior 4 rows in created_at ASC order"


def test_advice_during_active_capture_with_chat_message_no_session_collision(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-09 4.9: chatbox path under concurrent capture/transcribe writes
    SHALL NOT raise SQLAlchemy InvalidRequestError; both transcript_chunk
    AND advice_chunk frames flow."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_co", meeting_id="m_co"))

    advisor = _ScriptedAdvisor(["a", "b", "c"], per_token_delay_s=0.05)
    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=20, chunk_delay_s=0.02),
        advisor_override=advisor,
    )
    transcript_count = 0
    advice_count = 0
    error_codes: list[str] = []
    saw_done = False
    with client.websocket_connect(
        "/api/meetings/m_co/session", headers={"X-User-Id": "u_co"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_co"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_started":
                    ws.send_text(
                        json.dumps(
                            {
                                "type": "chat_message",
                                "request_id": "r_co",
                                "content": "hi",
                                "locale": "zh-TW",
                            }
                        )
                    )
                elif msg["type"] == "transcript_chunk":
                    transcript_count += 1
                elif msg["type"] == "advice_chunk":
                    advice_count += 1
                elif msg["type"] == "advice_done":
                    saw_done = True
                    ws.send_text(json.dumps({"type": "end_meeting", "meeting_id": "m_co"}))
                elif msg["type"] in ("advisor_failed", "error"):
                    error_codes.append(msg.get("error_code", "?"))
                elif msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert error_codes == [], f"unexpected error frames: {error_codes}"
    assert saw_done
    assert advice_count == 3
    assert transcript_count > 0
    # Pair persisted alongside concurrent capture writes.
    rows = asyncio.run(_read_chat_messages(_async_url(_migrated_db_url), "m_co"))
    assert rows == [("user", "hi"), ("advisor", "abc")]
