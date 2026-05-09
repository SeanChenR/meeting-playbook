"""WebSocket endpoint integration tests — slice-06.

Per spec meeting-session ADDED requirement scenarios:
- Owner upgrades to WebSocket successfully
- Non-owner is rejected with meeting.not_found
- Unauthenticated request is rejected before upgrade
- First client message must be start_meeting matching the path id
- Successful session emits the expected message sequence

Uses sync `fastapi.testclient.TestClient` for WebSocket support; DB seed
runs via `asyncio.run` inside the sync test body.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect

from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.audio.capture import AudioChunk, AudioCaptureService
from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.sessions.dependencies import (
    get_asr_provider_dependency,
    get_capture_factory_dependency,
)
from meeting_playbook.server import create_app


# ─── Mocks ─────────────────────────────────────────────────────────────────


class _StubASRProvider:
    name = "mock_asr"

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        return TranscriptChunk(
            text="hello world",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc) + timedelta(milliseconds=100),
            asr_provider_used=self.name,
            confidence=0.9,
        )


class _ScriptedCapture:
    """Mock capture session: yields N AudioChunks then is closed by service."""

    def __init__(self, *, meeting_id: str, recordings_dir: Path, n_chunks: int = 2):
        self._n = n_chunks
        self.meeting_id = meeting_id
        self.recordings_dir = Path(recordings_dir)
        self.wav_path = self.recordings_dir / meeting_id / "me.wav"

    async def __aenter__(self):
        self.wav_path.parent.mkdir(parents=True, exist_ok=True)
        # Write a stub WAV file so the recording row's file_size is non-zero.
        self.wav_path.write_bytes(b"\x00" * 100)
        return self

    async def __aexit__(self, *exc):
        return None

    async def events(self) -> AsyncIterator[AudioChunk]:
        for _ in range(self._n):
            now = datetime.now(timezone.utc)
            yield AudioChunk(
                audio_bytes=b"\x00\x00" * 100,
                sample_rate_hz=16000,
                started_at=now,
                ended_at=now + timedelta(seconds=1),
            )
            await asyncio.sleep(0)


# ─── DB helpers (sync test calls asyncio.run) ──────────────────────────────


async def _setup_meeting(db_url: str, *, user_id: str, meeting_id: str, status: str = "scheduled"):
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
                VALUES (:mid, :uid, 'T', 'C', 'M', :status)
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status
                """
            ),
            {"mid": meeting_id, "uid": user_id, "status": status},
        )
        await s.commit()
    await engine.dispose()


async def _read_meeting_status(db_url: str, meeting_id: str) -> str:
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        rows = await s.execute(
            text("SELECT status FROM meeting WHERE id = :mid"),
            {"mid": meeting_id},
        )
        row = rows.first()
    await engine.dispose()
    return row.status if row else ""


async def _truncate(db_url: str):
    engine = create_async_engine(db_url, future=True)
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE TABLE "transcript_chunk" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "recording" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "playbook" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "meeting" RESTART IDENTITY CASCADE'))
        await conn.execute(text('TRUNCATE TABLE "user" RESTART IDENTITY CASCADE'))
    await engine.dispose()


# ─── App + client factory ──────────────────────────────────────────────────


def _async_url(sync_url: str) -> str:
    if sync_url.startswith("postgresql+asyncpg://"):
        return sync_url
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


def _build_client(
    db_url_sync: str,
    *,
    capture_factory_override,
    asr_override=None,
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
    if asr_override:
        app.dependency_overrides[get_asr_provider_dependency] = lambda: asr_override
    else:
        app.dependency_overrides[get_asr_provider_dependency] = lambda: _StubASRProvider()
    return TestClient(app)


def _make_capture_factory(tmp_path: Path, n_chunks: int = 2):
    def factory(meeting_id: str) -> AudioCaptureService:
        return _ScriptedCapture(meeting_id=meeting_id, recordings_dir=tmp_path, n_chunks=n_chunks)

    return factory


# ─── Tests ─────────────────────────────────────────────────────────────────


def test_unauthenticated_ws_is_rejected_before_upgrade(_migrated_db_url, tmp_path):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_a"))

    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path),
    )
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/meetings/m_a/session"):
            pass
    assert exc_info.value.code == 4401
    assert "auth.gateway_bypass" in (exc_info.value.reason or "")


def test_cross_user_ws_is_rejected_with_not_found(_migrated_db_url, tmp_path):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_owner", meeting_id="m_b"))

    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path),
    )
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/meetings/m_b/session", headers={"X-User-Id": "u_attacker"}
        ):
            pass
    assert exc_info.value.code == 4404
    assert "meeting.not_found" in (exc_info.value.reason or "")


def test_start_meeting_id_mismatch_emits_bad_start_then_closes(_migrated_db_url, tmp_path):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_c", meeting_id="m_c"))

    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path),
    )
    with client.websocket_connect("/api/meetings/m_c/session", headers={"X-User-Id": "u_c"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_WRONG"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert msg["error_code"] == "session.bad_start"


def test_start_when_status_is_completed_emits_bad_status(_migrated_db_url, tmp_path):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _setup_meeting(
            _async_url(_migrated_db_url),
            user_id="u_d",
            meeting_id="m_d",
            status="completed",
        )
    )

    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path),
    )
    with client.websocket_connect("/api/meetings/m_d/session", headers={"X-User-Id": "u_d"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_d"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert msg["error_code"] == "session.bad_status"


def test_full_session_round_trip_emits_started_chunks_ended_and_completes_status(
    _migrated_db_url, tmp_path
):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_e", meeting_id="m_e"))

    client = _build_client(
        _migrated_db_url,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=2),
    )
    types_seen: list[str] = []
    with client.websocket_connect("/api/meetings/m_e/session", headers={"X-User-Id": "u_e"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_e"}))
        # Drain all server frames until disconnect; the scripted capture
        # exhausts after 2 chunks and triggers session finalize, so the
        # client never needs to send end_meeting in this scenario.
        try:
            while True:
                raw = ws.receive_text()
                types_seen.append(json.loads(raw)["type"])
        except WebSocketDisconnect:
            pass

    assert types_seen[0] == "meeting_started"
    assert types_seen[-1] == "meeting_ended"
    assert types_seen.count("transcript_chunk") == 2

    final_status = asyncio.run(_read_meeting_status(_async_url(_migrated_db_url), "m_e"))
    assert final_status == "completed"
