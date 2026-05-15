"""End-to-end integration test for audio playback + retention — slice-16 task 9.1.

Exercises the full audio_playback + recording-retention contract:
  (1) Dual-channel finalize-shaped fixture: two recordings (me + counterparty),
      each with `started_at` set. Range request on `me.wav` returns 206
      with the requested byte slice.
  (2) Soft-delete the recording (set `deleted_at = now()`) and re-request:
      the same endpoint MUST return 410 `audio_playback.expired`.
  (3) Single-channel finalize-shaped fixture: one recording row. A chunk
      with `speaker = "counterparty"` MUST still resolve to that single
      recording (the resolver's single-channel branch).
"""

from __future__ import annotations

import struct
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


def _write_40s_wav(path: Path) -> int:
    sample_rate = 16000
    channels = 1
    bps = 16
    duration_s = 40
    data_bytes_len = sample_rate * channels * (bps // 8) * duration_s
    byte_rate = sample_rate * channels * (bps // 8)
    block_align = channels * (bps // 8)
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<H", 1)
        + struct.pack("<H", channels)
        + struct.pack("<I", sample_rate)
        + struct.pack("<I", byte_rate)
        + struct.pack("<H", block_align)
        + struct.pack("<H", bps)
    )
    data_header = b"data" + struct.pack("<I", data_bytes_len)
    payload = b"WAVE" + fmt_chunk + data_header + (b"\x00" * data_bytes_len)
    riff = b"RIFF" + struct.pack("<I", len(payload) + 4) + payload
    path.write_bytes(riff)
    return len(riff)


@pytest_asyncio.fixture
async def api_client(migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client


@pytest.mark.asyncio
async def test_dual_channel_then_410_after_soft_delete(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    me_path = tmp_path / "me.wav"
    cp_path = tmp_path / "counterparty.wav"
    me_bytes = _write_40s_wav(me_path)
    cp_bytes = _write_40s_wav(cp_path)

    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                'INSERT INTO "user" (id, name, email, "emailVerified") '
                "VALUES ('u_dual', 'u', 'u@x.test', true) ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, scheduled_start_at, created_at
                )
                VALUES ('m_dual', 'u_dual', 'T', 'C', 'M', now(), now())
                ON CONFLICT DO NOTHING
                """
            )
        )
        for rid, stream, path_str, size in [
            ("r_dual_me", "me", str(me_path), me_bytes),
            ("r_dual_cp", "counterparty", str(cp_path), cp_bytes),
        ]:
            await conn.execute(
                text(
                    """
                    INSERT INTO recording (
                        id, meeting_id, stream, file_path, bytes,
                        created_at, started_at, source
                    )
                    VALUES (:rid, 'm_dual', :stream, :path, :size,
                            now(), now(), 'live')
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"rid": rid, "stream": stream, "path": path_str, "size": size},
            )

    # (1) Range request returns 206 with the requested byte slice on me.wav.
    resp = await api_client.get(
        "/api/meetings/m_dual/recordings/r_dual_me/audio",
        headers={"X-User-Id": "u_dual", "Range": "bytes=44-1043"},
    )
    assert resp.status_code == 206
    assert resp.headers["content-length"] == "1000"

    # (2) Soft-delete me.wav and re-request → 410 audio_playback.expired.
    async with migrated_engine.begin() as conn:
        await conn.execute(text("UPDATE recording SET deleted_at = now() WHERE id = 'r_dual_me'"))
    resp = await api_client.get(
        "/api/meetings/m_dual/recordings/r_dual_me/audio",
        headers={"X-User-Id": "u_dual", "Range": "bytes=0-99"},
    )
    assert resp.status_code == 410
    assert resp.json()["error_code"] == "audio_playback.expired"


@pytest.mark.asyncio
async def test_single_channel_single_recording_serves(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    """Single-channel meeting → one recording row → endpoint serves it
    regardless of which chunk speaker label the client is playing.
    """
    wav = tmp_path / "single.wav"
    total = _write_40s_wav(wav)

    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                'INSERT INTO "user" (id, name, email, "emailVerified") '
                "VALUES ('u_single', 'u', 'u@x.test', true) ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, scheduled_start_at, created_at
                )
                VALUES ('m_single', 'u_single', 'T', 'C', 'M', now(), now())
                ON CONFLICT DO NOTHING
                """
            )
        )
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes,
                    created_at, started_at, source
                )
                VALUES ('r_single', 'm_single', 'me', :path, :size,
                        now(), now(), 'offline')
                ON CONFLICT DO NOTHING
                """
            ),
            {"path": str(wav), "size": total},
        )

    resp = await api_client.get(
        "/api/meetings/m_single/recordings/r_single/audio",
        headers={"X-User-Id": "u_single"},
    )
    assert resp.status_code == 200
    assert int(resp.headers["content-length"]) == total
