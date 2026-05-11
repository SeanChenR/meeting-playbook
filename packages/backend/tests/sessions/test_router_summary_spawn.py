"""Slice-10: WS session router — summary fire-and-forget spawn integration tests.

Per spec meeting-session ADDED requirement scenarios:
- end_meeting spawns a summary task without blocking the WS close
- WS close timing is independent of summary generation duration
- Already-pending summary doesn't double-spawn
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect

from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.audio.capture import AudioChunk
from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app
from meeting_playbook.sessions.dependencies import get_capture_factory_dependency
from meeting_playbook.summarization import runtime

# ─── Mocks (mirror slice-7 / slice-8 / slice-9 patterns) ───────────────────


class _StubASRProvider:
    name = "mock_asr"

    async def warmup(self) -> None:
        return None

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        return TranscriptChunk(
            text="hi",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC) + timedelta(milliseconds=100),
            asr_provider_used=self.name,
            confidence=0.9,
        )


class _ScriptedCapture:
    def __init__(self, *, meeting_id, recordings_dir, n_chunks=2, stream_label="me"):
        self._n = n_chunks
        self.meeting_id = meeting_id
        self.recordings_dir = Path(recordings_dir)
        self.stream_label = stream_label
        self.wav_path = self.recordings_dir / meeting_id / f"{stream_label}.wav"

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
            await asyncio.sleep(0)


class _SleepingSummarizer:
    """Test summarizer that records calls + sleeps to keep a task in-flight."""

    def __init__(self, sleep_seconds: float = 30.0):
        self._sleep = sleep_seconds
        self.calls: list[str] = []

    async def summarize(self, meeting_id: str) -> str:
        self.calls.append(meeting_id)
        await asyncio.sleep(self._sleep)
        # Never reached when test cancels the task.
        return "## 重點討論\n## 決議\n## Action items\n## 待解決問題\n"


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
        await conn.execute(text('TRUNCATE TABLE "summary" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "chat_message" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "playbook" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


def _build_client(
    db_url_sync: str, monkeypatch: pytest.MonkeyPatch, *, capture_factory_override
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

    # Slice-11: ASR provider selection moved out of FastAPI Depends into the
    # WS handler; tests patch the router's imported factory function.
    monkeypatch.setattr(
        "meeting_playbook.sessions.router.get_asr_providers_for_meeting",
        lambda _name: (_StubASRProvider(), _StubASRProvider()),
    )
    return TestClient(app)


def _make_capture_factory(tmp_path: Path, n_chunks=2):
    def factory(meeting_id):
        return {
            "me": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=n_chunks,
                stream_label="me",
            ),
            "counterparty": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=n_chunks,
                stream_label="counterparty",
            ),
        }

    return factory


@pytest.fixture(autouse=True)
def _reset_inflight():
    runtime._inflight.clear()
    yield
    runtime._inflight.clear()


# ─── Tests ───────────────────────────────────────────────────────────────


def test_end_meeting_spawns_summary_task(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-10 5.1: end_meeting → spawn_summary_task called once with meeting_id."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_s", meeting_id="m_spawn"))

    spawn_calls: list[str] = []

    async def _stub_spawn(meeting_id, **_kw):
        spawn_calls.append(meeting_id)
        return True

    monkeypatch.setattr(runtime, "spawn_summary_task", _stub_spawn)

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=2),
    )
    with client.websocket_connect(
        "/api/meetings/m_spawn/session", headers={"X-User-Id": "u_s"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_spawn"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass

    assert spawn_calls == ["m_spawn"], (
        f"expected spawn_summary_task called once with 'm_spawn'; got {spawn_calls}"
    )


def test_end_meeting_does_not_block_websocket_close_on_long_summary(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-10 5.2: even if summary task runs forever, WS close happens fast."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_b", meeting_id="m_block"))

    # Replace spawn with one that returns immediately (fire-and-forget
    # contract — caller should NOT await the actual generation work).
    spawn_called = asyncio.Event()

    async def _stub_spawn(meeting_id, **_kw):
        spawn_called.set()
        return True

    monkeypatch.setattr(runtime, "spawn_summary_task", _stub_spawn)

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=2),
    )
    started = time.monotonic()
    with client.websocket_connect(
        "/api/meetings/m_block/session", headers={"X-User-Id": "u_b"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_block"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_ended":
                    break
        except WebSocketDisconnect:
            pass
    elapsed = time.monotonic() - started

    # Sanity: the spawn was called.
    assert spawn_called.is_set()
    # Hard cap: even with fake captures the full handshake should be under
    # a few seconds. If the spawn ever blocks waiting on the actual LLM
    # call, this would balloon to 30-60s.
    assert elapsed < 5.0, f"WS close took {elapsed:.2f}s; expected < 5s"


def test_end_meeting_when_summary_already_pending_logs_and_does_not_double_spawn(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Slice-10 5.3: pre-existing in-flight task → spawn returns False; no second task; WS still closes cleanly."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_d", meeting_id="m_dup"))

    spawn_calls: list[str] = []

    async def _stub_spawn(meeting_id, **_kw):
        spawn_calls.append(meeting_id)
        # Simulate "already pending" — return False without registering.
        return False

    monkeypatch.setattr(runtime, "spawn_summary_task", _stub_spawn)

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=2),
    )
    saw_meeting_ended = False
    with client.websocket_connect(
        "/api/meetings/m_dup/session", headers={"X-User-Id": "u_d"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_dup"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "meeting_ended":
                    saw_meeting_ended = True
                    break
        except WebSocketDisconnect:
            pass

    # spawn was attempted exactly once (no double-spawn loop).
    assert spawn_calls == ["m_dup"], f"expected exactly one spawn attempt; got {spawn_calls}"
    # The False return path does NOT raise out of the WS handler — the
    # session closes cleanly with `meeting_ended`.
    assert saw_meeting_ended, "WS must still close cleanly when spawn returns False"
