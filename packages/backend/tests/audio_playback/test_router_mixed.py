"""GET /api/meetings/{id}/recordings/mixed/audio tests — slice-25 task 2.1.

Per spec audio-playback ADDED requirement
"GET /api/meetings/{id}/recordings/mixed/audio serves the dual-stream mix
as a Range-aware mono stream":

  - First request triggers lazy mix then serves Range
  - Second request reads cached mixed.wav (no re-mix)
  - Single-channel meeting → 404 recording.mixed_not_applicable
  - Corrupt counterparty.wav → 500 recording.mix_failed
"""

from __future__ import annotations

import time
import wave
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


def _write_mono_wav(path: Path, samples: np.ndarray, sample_rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(samples.astype(np.int16).tobytes())


@pytest_asyncio.fixture
async def api_client_mixed(
    migrated_engine: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    """API client with RECORDINGS_DIR overridden to tmp_path."""
    from meeting_playbook.config import get_settings

    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path))
    get_settings.cache_clear()

    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client

    get_settings.cache_clear()


async def _seed_meeting_and_recordings(
    engine: AsyncEngine,
    *,
    user_id: str,
    meeting_id: str,
    me_path: Path | None = None,
    counterparty_path: Path | None = None,
) -> None:
    """Insert user + meeting, optionally me/them recording rows pointing at given paths."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                'INSERT INTO "user" (id, name, email, "emailVerified") '
                "VALUES (:id, :id, :email, true) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, scheduled_start_at, created_at
                )
                VALUES (:mid, :uid, 'T', 'C', 'M', now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )
        for stream, path in [("me", me_path), ("counterparty", counterparty_path)]:
            if path is None:
                continue
            await conn.execute(
                text(
                    """
                    INSERT INTO recording (
                        id, meeting_id, stream, file_path, bytes,
                        created_at, started_at, source, deleted_at
                    )
                    VALUES (
                        :rid, :mid, :stream, :path, :bytes,
                        now(), now(), 'live', NULL
                    )
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "rid": f"r_{meeting_id}_{stream}",
                    "mid": meeting_id,
                    "stream": stream,
                    "path": str(path),
                    "bytes": path.stat().st_size,
                },
            )


@pytest.mark.asyncio
async def test_first_request_triggers_mix_then_serves_range(
    api_client_mixed: AsyncClient,
    migrated_engine: AsyncEngine,
    tmp_path: Path,
):
    meeting_id = "m_first"
    meeting_dir = tmp_path / meeting_id
    samples = 8000  # 0.5s @ 16kHz — small enough to range-slice cleanly
    _write_mono_wav(meeting_dir / "me.wav", np.full(samples, 100, dtype=np.int16))
    _write_mono_wav(meeting_dir / "counterparty.wav", np.full(samples, 300, dtype=np.int16))
    await _seed_meeting_and_recordings(
        migrated_engine,
        user_id="u_first",
        meeting_id=meeting_id,
        me_path=meeting_dir / "me.wav",
        counterparty_path=meeting_dir / "counterparty.wav",
    )

    resp = await api_client_mixed.get(
        f"/api/meetings/{meeting_id}/recordings/mixed/audio",
        headers={"X-User-Id": "u_first", "Range": "bytes=0-99"},
    )
    assert resp.status_code == 206, resp.text
    assert resp.headers["content-length"] == "100"
    assert (meeting_dir / "mixed.wav").exists()


@pytest.mark.asyncio
async def test_second_request_reads_cached_mix(
    api_client_mixed: AsyncClient,
    migrated_engine: AsyncEngine,
    tmp_path: Path,
):
    meeting_id = "m_cached"
    meeting_dir = tmp_path / meeting_id
    samples = 8000
    _write_mono_wav(meeting_dir / "me.wav", np.full(samples, 100, dtype=np.int16))
    _write_mono_wav(meeting_dir / "counterparty.wav", np.full(samples, 300, dtype=np.int16))
    await _seed_meeting_and_recordings(
        migrated_engine,
        user_id="u_cached",
        meeting_id=meeting_id,
        me_path=meeting_dir / "me.wav",
        counterparty_path=meeting_dir / "counterparty.wav",
    )

    # First call — trigger mix.
    r1 = await api_client_mixed.get(
        f"/api/meetings/{meeting_id}/recordings/mixed/audio",
        headers={"X-User-Id": "u_cached", "Range": "bytes=0-99"},
    )
    assert r1.status_code == 206, r1.text
    mtime_after_first = (meeting_dir / "mixed.wav").stat().st_mtime_ns
    # Tiny sleep to guarantee detectable mtime change if any rewrite occurred.
    time.sleep(0.02)

    # Second call — must NOT rewrite mixed.wav.
    r2 = await api_client_mixed.get(
        f"/api/meetings/{meeting_id}/recordings/mixed/audio",
        headers={"X-User-Id": "u_cached", "Range": "bytes=100-199"},
    )
    assert r2.status_code == 206
    assert (meeting_dir / "mixed.wav").stat().st_mtime_ns == mtime_after_first


@pytest.mark.asyncio
async def test_single_channel_meeting_returns_404_mixed_not_applicable(
    api_client_mixed: AsyncClient,
    migrated_engine: AsyncEngine,
    tmp_path: Path,
):
    meeting_id = "m_solo"
    meeting_dir = tmp_path / meeting_id
    _write_mono_wav(meeting_dir / "me.wav", np.full(8000, 100, dtype=np.int16))
    # no counterparty.wav
    await _seed_meeting_and_recordings(
        migrated_engine,
        user_id="u_solo",
        meeting_id=meeting_id,
        me_path=meeting_dir / "me.wav",
        counterparty_path=None,
    )

    resp = await api_client_mixed.get(
        f"/api/meetings/{meeting_id}/recordings/mixed/audio",
        headers={"X-User-Id": "u_solo"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["error_code"] == "recording.mixed_not_applicable"
    assert not (meeting_dir / "mixed.wav").exists()


@pytest.mark.asyncio
async def test_corrupt_them_wav_returns_500_mix_failed(
    api_client_mixed: AsyncClient,
    migrated_engine: AsyncEngine,
    tmp_path: Path,
):
    meeting_id = "m_corrupt"
    meeting_dir = tmp_path / meeting_id
    _write_mono_wav(meeting_dir / "me.wav", np.full(8000, 100, dtype=np.int16))
    # counterparty.wav contains random bytes — wave.open will raise wave.Error.
    meeting_dir.mkdir(parents=True, exist_ok=True)
    (meeting_dir / "counterparty.wav").write_bytes(b"not a wav file at all" * 100)
    await _seed_meeting_and_recordings(
        migrated_engine,
        user_id="u_corrupt",
        meeting_id=meeting_id,
        me_path=meeting_dir / "me.wav",
        counterparty_path=meeting_dir / "counterparty.wav",
    )

    resp = await api_client_mixed.get(
        f"/api/meetings/{meeting_id}/recordings/mixed/audio",
        headers={"X-User-Id": "u_corrupt"},
    )
    assert resp.status_code == 500, resp.text
    assert resp.json()["error_code"] == "recording.mix_failed"
    # No leftover .tmp file from failed mix.
    assert not (meeting_dir / "mixed.wav.tmp").exists()
    assert not (meeting_dir / "mixed.wav").exists()
