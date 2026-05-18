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

# ─── Mocks ─────────────────────────────────────────────────────────────────


class _StubASRProvider:
    name = "mock_asr"

    async def warmup(self) -> None:
        return None

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        return TranscriptChunk(
            text="hello world",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC) + timedelta(milliseconds=100),
            asr_provider_used=self.name,
            confidence=0.9,
        )


class _ScriptedCapture:
    """Mock capture session: yields N AudioChunks then is closed by service."""

    def __init__(
        self,
        *,
        meeting_id: str,
        recordings_dir: Path,
        n_chunks: int = 2,
        stream_label: str = "me",
        raise_on_enter: bool = False,
    ):
        self._n = n_chunks
        self.meeting_id = meeting_id
        self.recordings_dir = Path(recordings_dir)
        self.stream_label = stream_label
        self.wav_path = self.recordings_dir / meeting_id / f"{stream_label}.wav"
        self._raise_on_enter = raise_on_enter

    async def __aenter__(self):
        if self._raise_on_enter:
            raise RuntimeError(f"simulated open failure for {self.stream_label}")
        self.wav_path.parent.mkdir(parents=True, exist_ok=True)
        # Stub WAV so the recording row's file_size is non-zero.
        self.wav_path.write_bytes(b"\x00" * 100)
        return self

    async def __aexit__(self, *exc):
        return None

    async def stop(self) -> None:
        # No-op for scripted captures (events() exhausts naturally).
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


# ─── DB helpers (sync test calls asyncio.run) ──────────────────────────────


async def _setup_meeting(
    db_url: str,
    *,
    user_id: str,
    meeting_id: str,
    status: str = "scheduled",
    asr_provider: str = "whisper",
):
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
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, status, asr_provider
                )
                VALUES (:mid, :uid, 'T', 'C', 'M', :status, :provider)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    asr_provider = EXCLUDED.asr_provider
                """
            ),
            {
                "mid": meeting_id,
                "uid": user_id,
                "status": status,
                "provider": asr_provider,
            },
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
    monkeypatch: pytest.MonkeyPatch,
    *,
    capture_factory_override,
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

    # Slice-11: provider selection moved out of FastAPI Depends and into the
    # WS handler (so it can branch on meeting.asr_provider). Tests patch the
    # router's imported factory function — accepts dict OR tuple override.
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


def _make_capture_factory(tmp_path: Path, n_chunks: int = 2):
    """Slice-7: factory returns a dict[Stream, capture]. Both me + counterparty
    captures by default emit `n_chunks` events.

    Slice-27: factory signature is `(meeting_id, mode)`. `mode="single"`
    returns only the `me` capture (mirrors `_default_capture_factory`).
    """

    def factory(meeting_id: str, mode: str = "dual"):
        me_cap = _ScriptedCapture(
            meeting_id=meeting_id,
            recordings_dir=tmp_path,
            n_chunks=n_chunks,
            stream_label="me",
        )
        if mode == "single":
            return {"me": me_cap}
        return {
            "me": me_cap,
            "counterparty": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=n_chunks,
                stream_label="counterparty",
            ),
        }

    return factory


# ─── Tests ─────────────────────────────────────────────────────────────────


def test_unauthenticated_ws_is_rejected_before_upgrade(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_a", meeting_id="m_a"))

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path),
    )
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/meetings/m_a/session"):
            pass
    assert exc_info.value.code == 4401
    assert "auth.gateway_bypass" in (exc_info.value.reason or "")


def test_cross_user_ws_is_rejected_with_not_found(_migrated_db_url, tmp_path, monkeypatch):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_owner", meeting_id="m_b"))

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path),
    )
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/meetings/m_b/session", headers={"X-User-Id": "u_attacker"}),
    ):
        pass
    assert exc_info.value.code == 4404
    assert "meeting.not_found" in (exc_info.value.reason or "")


def test_start_meeting_id_mismatch_emits_bad_start_then_closes(
    _migrated_db_url, tmp_path, monkeypatch
):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_c", meeting_id="m_c"))

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path),
    )
    with client.websocket_connect("/api/meetings/m_c/session", headers={"X-User-Id": "u_c"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_WRONG"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert msg["error_code"] == "session.bad_start"


def test_start_when_status_is_completed_emits_bad_status(_migrated_db_url, tmp_path, monkeypatch):
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
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path),
    )
    with client.websocket_connect("/api/meetings/m_d/session", headers={"X-User-Id": "u_d"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_d"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert msg["error_code"] == "session.bad_status"


def test_full_session_round_trip_emits_started_chunks_ended_and_completes_status(
    _migrated_db_url, tmp_path, monkeypatch
):
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_e", meeting_id="m_e"))

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
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
    # Slice-7: now two streams each yield 2 chunks → 4 transcript frames total.
    assert types_seen.count("transcript_chunk") == 4

    final_status = asyncio.run(_read_meeting_status(_async_url(_migrated_db_url), "m_e"))
    assert final_status == "completed"


# ─── Slice 7: dual-stream router tests ────────────────────────────────────


def test_no_blackhole_device_aborts_session(_migrated_db_url, tmp_path, monkeypatch):
    """Pre-flight: missing BlackHole → error frame + close, status stays scheduled."""
    from meeting_playbook.audio.devices import NoBlackholeDevice

    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_nb", meeting_id="m_nb"))

    def failing_factory(meeting_id: str, mode: str = "dual"):
        raise NoBlackholeDevice("BlackHole 2ch not detected — see docs/BLACKHOLE_SETUP.md")

    client = _build_client(_migrated_db_url, monkeypatch, capture_factory_override=failing_factory)

    with client.websocket_connect(
        "/api/meetings/m_nb/session", headers={"X-User-Id": "u_nb"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_nb"}))
        msg = json.loads(ws.receive_text())

    assert msg["type"] == "error"
    assert msg["error_code"] == "session.no_blackhole_device"

    # Status MUST remain `scheduled` so the user can retry after fixing audio.
    final_status = asyncio.run(_read_meeting_status(_async_url(_migrated_db_url), "m_nb"))
    assert final_status == "scheduled"


def test_dual_stream_session_emits_transcripts_for_both_speakers(
    _migrated_db_url, tmp_path, monkeypatch
):
    """Both me + counterparty transcript frames arrive over the WebSocket."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_ds", meeting_id="m_ds"))

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=3),
    )
    transcript_speakers: list[str] = []
    with client.websocket_connect(
        "/api/meetings/m_ds/session", headers={"X-User-Id": "u_ds"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_ds"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "transcript_chunk":
                    transcript_speakers.append(msg["speaker"])
        except WebSocketDisconnect:
            pass

    # Each stream emitted 3 chunks → 3 me + 3 counterparty.
    assert transcript_speakers.count("me") == 3
    assert transcript_speakers.count("counterparty") == 3


def test_stream_failed_at_start_aborts(_migrated_db_url, tmp_path, monkeypatch):
    """Capture __aenter__ raising → error frame `session.stream_failed_at_start`."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_sf", meeting_id="m_sf"))

    def factory(meeting_id: str, mode: str = "dual"):
        return {
            "me": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=2,
                stream_label="me",
            ),
            "counterparty": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=2,
                stream_label="counterparty",
                raise_on_enter=True,  # simulate device open failure
            ),
        }

    client = _build_client(_migrated_db_url, monkeypatch, capture_factory_override=factory)
    error_codes: list[str] = []
    with client.websocket_connect(
        "/api/meetings/m_sf/session", headers={"X-User-Id": "u_sf"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_sf"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "error":
                    error_codes.append(msg["error_code"])
        except WebSocketDisconnect:
            pass

    assert "session.stream_failed_at_start" in error_codes


# ─── Slice 11: WS connect uses factory keyed on meeting.asr_provider ───────


def _make_factory_spy(monkeypatch):
    """Replace the router's factory import with a spy that records the
    provider_name it was called with AND returns stub providers (so the
    rest of the WS round-trip still exercises real wiring)."""
    calls: list[str] = []

    def _spy(name: str):
        calls.append(name)
        return _StubASRProvider(), _StubASRProvider()

    monkeypatch.setattr(
        "meeting_playbook.sessions.router.get_asr_providers_for_meeting",
        _spy,
    )
    return calls


def test_qwen3_meeting_resolves_via_factory_with_qwen3(_migrated_db_url, tmp_path, monkeypatch):
    """A meeting with `asr_provider=qwen3` triggers factory("qwen3") at WS connect."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _setup_meeting(
            _async_url(_migrated_db_url),
            user_id="u_q",
            meeting_id="m_q",
            asr_provider="qwen3",
        )
    )

    db_url_async = _async_url(_migrated_db_url)
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    app.dependency_overrides[get_capture_factory_dependency] = lambda: _make_capture_factory(
        tmp_path, n_chunks=1
    )
    calls = _make_factory_spy(monkeypatch)
    client = TestClient(app)

    with client.websocket_connect("/api/meetings/m_q/session", headers={"X-User-Id": "u_q"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_q"}))
        try:
            while True:
                ws.receive_text()
        except WebSocketDisconnect:
            pass

    assert calls == ["qwen3"], (
        f"factory MUST be called once with the meeting's asr_provider; got {calls}"
    )


def test_whisper_meeting_resolves_via_factory_with_whisper(_migrated_db_url, tmp_path, monkeypatch):
    """A meeting with `asr_provider=whisper` triggers factory("whisper") at WS connect."""
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _setup_meeting(
            _async_url(_migrated_db_url),
            user_id="u_w",
            meeting_id="m_w",
            asr_provider="whisper",
        )
    )

    db_url_async = _async_url(_migrated_db_url)
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    app.dependency_overrides[get_capture_factory_dependency] = lambda: _make_capture_factory(
        tmp_path, n_chunks=1
    )
    calls = _make_factory_spy(monkeypatch)
    client = TestClient(app)

    with client.websocket_connect("/api/meetings/m_w/session", headers={"X-User-Id": "u_w"}) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_w"}))
        try:
            while True:
                ws.receive_text()
        except WebSocketDisconnect:
            pass

    assert calls == ["whisper"], (
        f"factory MUST be called once with the meeting's asr_provider; got {calls}"
    )


class _CallCountingASRProvider:
    """Marker provider whose transcribe_chunk hits a counter, so a test
    can assert each chunk was handled by the connect-time instance."""

    def __init__(self, marker: str) -> None:
        self.marker = marker
        self.transcribe_calls = 0

    name: str = "marker_asr"

    async def warmup(self) -> None:
        return None

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        self.transcribe_calls += 1
        return TranscriptChunk(
            text=f"chunk_{self.transcribe_calls}",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC) + timedelta(milliseconds=50),
            asr_provider_used=self.marker,
            confidence=0.9,
        )


async def _update_meeting_asr_provider(db_url: str, meeting_id: str, value: str) -> None:
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        await s.execute(
            text("UPDATE meeting SET asr_provider = :v WHERE id = :mid"),
            {"v": value, "mid": meeting_id},
        )
        await s.commit()
    await engine.dispose()


def test_mid_session_provider_switch_ignored(_migrated_db_url, tmp_path, monkeypatch):
    """Slice-11 spec scenario "Mid-session provider switch is ignored by the live WS".

    Connect with meeting.asr_provider="whisper" → factory returns a marker
    provider stand-in. While the WS is open, UPDATE meeting.asr_provider to
    "qwen3" out of band. The factory MUST NOT be called again, and the
    same marker provider must transcribe both chunks.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(
        _setup_meeting(
            _async_url(_migrated_db_url),
            user_id="u_swap",
            meeting_id="m_swap",
            asr_provider="whisper",
        )
    )

    me_provider = _CallCountingASRProvider(marker="whisper-marker-me")
    cp_provider = _CallCountingASRProvider(marker="whisper-marker-cp")
    factory_calls: list[str] = []

    def _spy(name: str):
        factory_calls.append(name)
        return me_provider, cp_provider

    monkeypatch.setattr(
        "meeting_playbook.sessions.router.get_asr_providers_for_meeting",
        _spy,
    )

    db_url_async = _async_url(_migrated_db_url)
    engine = create_async_engine(db_url_async, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_session():
        async with Session() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    app.dependency_overrides[get_capture_factory_dependency] = lambda: _make_capture_factory(
        tmp_path, n_chunks=2
    )
    client = TestClient(app)

    transcript_markers: list[str] = []
    saw_first = False
    with client.websocket_connect(
        "/api/meetings/m_swap/session", headers={"X-User-Id": "u_swap"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_swap"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "transcript_chunk":
                    transcript_markers.append(msg["asr_provider_used"])
                    if not saw_first:
                        # Out-of-band PUT-equivalent: flip the row to qwen3.
                        # The live session must NOT pick this up.
                        asyncio.run(
                            _update_meeting_asr_provider(
                                _async_url(_migrated_db_url), "m_swap", "qwen3"
                            )
                        )
                        saw_first = True
        except WebSocketDisconnect:
            pass

    # Factory was resolved exactly once at connect time — no re-read.
    assert factory_calls == ["whisper"], (
        f"factory MUST resolve once at connect; got {factory_calls}"
    )
    # All transcript chunks came from the connect-time providers (markers).
    assert me_provider.transcribe_calls == 2
    assert cp_provider.transcribe_calls == 2
    assert all(m.startswith("whisper-marker-") for m in transcript_markers), (
        f"every chunk must be transcribed by the connect-time provider; got {transcript_markers}"
    )

    # Sanity: the row really did flip in the database (the trigger landed).
    async def _read_provider() -> str:
        engine2 = create_async_engine(_async_url(_migrated_db_url), future=True)
        Session2 = async_sessionmaker(engine2, expire_on_commit=False)
        async with Session2() as s:
            row = (
                await s.execute(text("SELECT asr_provider FROM meeting WHERE id = 'm_swap'"))
            ).first()
        await engine2.dispose()
        return row.asr_provider if row else ""

    assert asyncio.run(_read_provider()) == "qwen3"


# ─── Slice-27 (single-channel-recording-entry): mode = single ─────────────


async def _read_recordings(db_url: str, meeting_id: str) -> list[dict]:
    """List the recording rows for a meeting (stream + file_path only)."""
    engine = create_async_engine(db_url, future=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT stream, file_path FROM recording "
                    "WHERE meeting_id = :mid ORDER BY stream"
                ),
                {"mid": meeting_id},
            )
        ).all()
    await engine.dispose()
    return [{"stream": r.stream, "file_path": r.file_path} for r in rows]


def test_single_mode_skips_blackhole_check(_migrated_db_url, tmp_path, monkeypatch):
    """`mode: "single"` MUST start `meeting_started` even with NO BlackHole.

    Spec scenario "Missing BlackHole device does NOT abort a single-mode
    session" — the factory is allowed to return only `{"me": ...}` and the
    router accepts it without raising `session.no_blackhole_device`.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_s1", meeting_id="m_s1"))

    # Factory raises NoBlackholeDevice for dual but returns mic-only for single.
    # If the router still calls into BlackHole discovery somewhere we'd see
    # the dual path explode here.
    def factory(meeting_id: str, mode: str = "dual"):
        if mode == "dual":
            from meeting_playbook.audio.devices import NoBlackholeDevice as _NBHD

            raise _NBHD("no BlackHole")
        return {
            "me": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=1,
                stream_label="me",
            ),
        }

    client = _build_client(_migrated_db_url, monkeypatch, capture_factory_override=factory)
    types_seen: list[str] = []
    with client.websocket_connect(
        "/api/meetings/m_s1/session", headers={"X-User-Id": "u_s1"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_s1", "mode": "single"}))
        try:
            while True:
                raw = ws.receive_text()
                types_seen.append(json.loads(raw)["type"])
        except WebSocketDisconnect:
            pass

    assert "meeting_started" in types_seen, (
        f"single mode must reach meeting_started; got {types_seen}"
    )
    assert "error" not in types_seen, f"no error frame expected; got {types_seen}"


def test_single_mode_finalize_writes_one_recording(_migrated_db_url, tmp_path, monkeypatch):
    """After a single-mode finalize, the DB has exactly one `recording` row
    with `stream = 'me'`. No `counterparty` row is written.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_s2", meeting_id="m_s2"))

    def factory(meeting_id: str, mode: str = "dual"):
        # Mode is single → only mic capture is created.
        return {
            "me": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=1,
                stream_label="me",
            ),
        }

    client = _build_client(_migrated_db_url, monkeypatch, capture_factory_override=factory)
    with client.websocket_connect(
        "/api/meetings/m_s2/session", headers={"X-User-Id": "u_s2"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_s2", "mode": "single"}))
        try:
            while True:
                ws.receive_text()
        except WebSocketDisconnect:
            pass

    rows = asyncio.run(_read_recordings(_async_url(_migrated_db_url), "m_s2"))
    assert len(rows) == 1, f"single mode must produce 1 recording row; got {rows}"
    assert rows[0]["stream"] == "me", f"recording.stream must be 'me'; got {rows[0]}"
    assert rows[0]["file_path"].endswith("me.wav"), (
        f"single mode file path must end with me.wav; got {rows[0]}"
    )


class _WarmupCountingASRProvider:
    """ASRProvider stand-in that records every warmup() call."""

    name = "warmup-counter"

    def __init__(self) -> None:
        self.warmup_calls = 0

    async def warmup(self) -> None:
        self.warmup_calls += 1

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        return TranscriptChunk(
            text="hi",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC) + timedelta(milliseconds=50),
            asr_provider_used=self.name,
            confidence=0.9,
        )


def test_single_mode_warmup_calls_only_me_provider(_migrated_db_url, tmp_path, monkeypatch):
    """Per D4: single mode warms up `me_provider` only — the `counterparty`
    provider's `warmup()` MUST NOT be awaited.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_s3", meeting_id="m_s3"))

    me_provider = _WarmupCountingASRProvider()
    cp_provider = _WarmupCountingASRProvider()

    def factory(meeting_id: str, mode: str = "dual"):
        return {
            "me": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=1,
                stream_label="me",
            ),
        }

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=factory,
        providers_override=(me_provider, cp_provider),
    )
    with client.websocket_connect(
        "/api/meetings/m_s3/session", headers={"X-User-Id": "u_s3"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_s3", "mode": "single"}))
        try:
            while True:
                ws.receive_text()
        except WebSocketDisconnect:
            pass

    assert me_provider.warmup_calls == 1, (
        f"me_provider.warmup() must run once; got {me_provider.warmup_calls}"
    )
    assert cp_provider.warmup_calls == 0, (
        f"counterparty_provider.warmup() MUST NOT run in single mode; got {cp_provider.warmup_calls}"
    )


def test_dual_mode_unchanged_regression(_migrated_db_url, tmp_path, monkeypatch):
    """Dual mode (the default) still produces TWO recording rows + warms up
    BOTH ASR providers. Guards against the new branch breaking the legacy path.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_s4", meeting_id="m_s4"))

    me_provider = _WarmupCountingASRProvider()
    cp_provider = _WarmupCountingASRProvider()

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=_make_capture_factory(tmp_path, n_chunks=1),
        providers_override=(me_provider, cp_provider),
    )
    with client.websocket_connect(
        "/api/meetings/m_s4/session", headers={"X-User-Id": "u_s4"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_s4", "mode": "dual"}))
        try:
            while True:
                ws.receive_text()
        except WebSocketDisconnect:
            pass

    rows = asyncio.run(_read_recordings(_async_url(_migrated_db_url), "m_s4"))
    streams = sorted(r["stream"] for r in rows)
    assert streams == ["counterparty", "me"], (
        f"dual mode must produce both recording rows; got {streams}"
    )
    assert me_provider.warmup_calls == 1
    assert cp_provider.warmup_calls == 1


# ─── Task 3.2 — single-mode failure modes ──────────────────────────────────


def test_single_mode_mic_missing_emits_no_audio_device(_migrated_db_url, tmp_path, monkeypatch):
    """`mode="single"` + factory raises `MicDeviceNotFound` → server emits
    `session.no_audio_device` and the meeting status stays `scheduled`.
    """
    from meeting_playbook.audio.devices import MicDeviceNotFound

    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_sm1", meeting_id="m_sm1"))

    def factory(meeting_id: str, mode: str = "dual"):
        raise MicDeviceNotFound("mic missing")

    client = _build_client(_migrated_db_url, monkeypatch, capture_factory_override=factory)
    with client.websocket_connect(
        "/api/meetings/m_sm1/session", headers={"X-User-Id": "u_sm1"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_sm1", "mode": "single"}))
        msg = json.loads(ws.receive_text())

    assert msg["type"] == "error"
    assert msg["error_code"] == "session.no_audio_device"
    final_status = asyncio.run(_read_meeting_status(_async_url(_migrated_db_url), "m_sm1"))
    assert final_status == "scheduled"


def test_single_mode_warmup_failure_emits_stream_failed_at_start(
    _migrated_db_url, tmp_path, monkeypatch
):
    """`mode="single"` + ASR provider's `warmup()` raises → server emits
    `session.stream_failed_at_start` and rolls the meeting back to `completed`.
    """
    asyncio.run(_truncate(_async_url(_migrated_db_url)))
    asyncio.run(_setup_meeting(_async_url(_migrated_db_url), user_id="u_sm2", meeting_id="m_sm2"))

    class _BoomMeProvider:
        name = "boom"

        async def warmup(self) -> None:
            raise RuntimeError("warmup blew up")

        async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
            return TranscriptChunk(
                text="",
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                asr_provider_used=self.name,
                confidence=0.0,
            )

    def factory(meeting_id: str, mode: str = "dual"):
        return {
            "me": _ScriptedCapture(
                meeting_id=meeting_id,
                recordings_dir=tmp_path,
                n_chunks=1,
                stream_label="me",
            ),
        }

    client = _build_client(
        _migrated_db_url,
        monkeypatch,
        capture_factory_override=factory,
        providers_override=(_BoomMeProvider(), _StubASRProvider()),
    )
    error_codes: list[str] = []
    with client.websocket_connect(
        "/api/meetings/m_sm2/session", headers={"X-User-Id": "u_sm2"}
    ) as ws:
        ws.send_text(json.dumps({"type": "start_meeting", "meeting_id": "m_sm2", "mode": "single"}))
        try:
            while True:
                raw = ws.receive_text()
                msg = json.loads(raw)
                if msg["type"] == "error":
                    error_codes.append(msg["error_code"])
        except WebSocketDisconnect:
            pass

    assert "session.stream_failed_at_start" in error_codes
    # Per existing router behaviour for warmup failure: meeting flips to completed.
    final_status = asyncio.run(_read_meeting_status(_async_url(_migrated_db_url), "m_sm2"))
    assert final_status == "completed"
