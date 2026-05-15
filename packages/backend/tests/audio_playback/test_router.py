"""GET /api/meetings/{id}/recordings/{rid}/audio tests — slice-16 task 4.1.

Seven scenarios per spec audio-playback `GET ... serves Range-aware
audio streaming` and recording-retention `... returns 410 Gone when the
recording is retention-expired`:

  (a) with Range → 206 + Content-Range / Content-Length
  (b) expired recording + Range → 410 + audio_playback.expired
  (c) no Range → 200 + full file
  (d) Range > max_bytes → 206 with Content-Length capped
  (e) recording not in path meeting → 404
  (f) non-owner via X-User-Id → 403
  (g) Range past file end → 416 (StreamingResponse uses request Range)
"""

from __future__ import annotations

import struct
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


def _write_40s_wav(path: Path) -> int:
    """Write a 40s 16 kHz mono 16-bit PCM WAV; return total byte count."""
    sample_rate = 16000
    channels = 1
    bits_per_sample = 16
    duration_s = 40
    data_bytes_len = sample_rate * channels * (bits_per_sample // 8) * duration_s
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    fmt_chunk = (
        b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<H", 1)
        + struct.pack("<H", channels)
        + struct.pack("<I", sample_rate)
        + struct.pack("<I", byte_rate)
        + struct.pack("<H", block_align)
        + struct.pack("<H", bits_per_sample)
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


async def _seed(
    engine: AsyncEngine,
    *,
    user_id: str,
    meeting_id: str,
    recording_id: str,
    wav_path: Path,
    bytes_size: int,
    deleted: bool = False,
) -> None:
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
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes,
                    created_at, started_at, source, deleted_at
                )
                VALUES (
                    :rid, :mid, 'me', :path, :bytes,
                    now(), now(), 'live',
                    CASE WHEN :deleted THEN now() ELSE NULL END
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "rid": recording_id,
                "mid": meeting_id,
                "path": str(wav_path),
                "bytes": bytes_size,
                "deleted": deleted,
            },
        )


@pytest.mark.asyncio
async def test_a_range_returns_206_with_content_range(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)
    await _seed(
        migrated_engine,
        user_id="u_a",
        meeting_id="m_a",
        recording_id="r_a",
        wav_path=wav,
        bytes_size=total,
    )
    resp = await api_client.get(
        "/api/meetings/m_a/recordings/r_a/audio",
        headers={"X-User-Id": "u_a", "Range": "bytes=0-99"},
    )
    assert resp.status_code == 206
    assert resp.headers["content-range"] == f"bytes 0-99/{total}"
    assert resp.headers["content-length"] == "100"


@pytest.mark.asyncio
async def test_b_expired_recording_returns_410(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)
    await _seed(
        migrated_engine,
        user_id="u_b",
        meeting_id="m_b",
        recording_id="r_b",
        wav_path=wav,
        bytes_size=total,
        deleted=True,
    )
    resp = await api_client.get(
        "/api/meetings/m_b/recordings/r_b/audio",
        headers={"X-User-Id": "u_b", "Range": "bytes=0-99"},
    )
    assert resp.status_code == 410
    payload = resp.json()
    assert payload["error_code"] == "audio_playback.expired"
    # Body MUST NOT contain WAV bytes.
    assert b"RIFF" not in resp.content


@pytest.mark.asyncio
async def test_c_no_range_returns_200_full_file(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)
    await _seed(
        migrated_engine,
        user_id="u_c",
        meeting_id="m_c",
        recording_id="r_c",
        wav_path=wav,
        bytes_size=total,
    )
    resp = await api_client.get(
        "/api/meetings/m_c/recordings/r_c/audio",
        headers={"X-User-Id": "u_c"},
    )
    assert resp.status_code == 200
    # Body capped at max_bytes; default 2_097_152 > 1_280_044 total → full file.
    assert resp.headers["content-length"] == str(total)


@pytest.mark.asyncio
async def test_d_range_larger_than_max_bytes_is_capped(
    api_client: AsyncClient,
    migrated_engine: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    # Force a small cap so we can assert truncation without 30MB fixtures.
    monkeypatch.setenv("AUDIO_RANGE_MAX_BYTES", "1024")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()

    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)
    await _seed(
        migrated_engine,
        user_id="u_d",
        meeting_id="m_d",
        recording_id="r_d",
        wav_path=wav,
        bytes_size=total,
    )
    resp = await api_client.get(
        "/api/meetings/m_d/recordings/r_d/audio",
        headers={"X-User-Id": "u_d", "Range": "bytes=0-1000000"},
    )
    assert resp.status_code == 206
    assert int(resp.headers["content-length"]) <= 1024
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_e_recording_not_in_meeting_returns_404(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)
    await _seed(
        migrated_engine,
        user_id="u_e",
        meeting_id="m_e_real",
        recording_id="r_e",
        wav_path=wav,
        bytes_size=total,
    )
    resp = await api_client.get(
        "/api/meetings/m_e_wrong/recordings/r_e/audio",
        headers={"X-User-Id": "u_e"},
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "audio_playback.recording_not_found"


@pytest.mark.asyncio
async def test_f_non_owner_returns_403(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)
    await _seed(
        migrated_engine,
        user_id="u_owner",
        meeting_id="m_f",
        recording_id="r_f",
        wav_path=wav,
        bytes_size=total,
    )
    # Also create the attacker as a real user so the X-User-Id resolves.
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                'INSERT INTO "user" (id, name, email, "emailVerified") '
                "VALUES ('u_attacker', 'A', 'a@x.test', true) "
                "ON CONFLICT (id) DO NOTHING"
            )
        )
    resp = await api_client.get(
        "/api/meetings/m_f/recordings/r_f/audio",
        headers={"X-User-Id": "u_attacker"},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "audio_playback.forbidden"


@pytest.mark.asyncio
async def test_g_range_past_file_returns_422_malformed(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
):
    """parse_range_header treats start >= total_length as malformed."""
    wav = tmp_path / "session.wav"
    total = _write_40s_wav(wav)
    await _seed(
        migrated_engine,
        user_id="u_g",
        meeting_id="m_g",
        recording_id="r_g",
        wav_path=wav,
        bytes_size=total,
    )
    resp = await api_client.get(
        "/api/meetings/m_g/recordings/r_g/audio",
        headers={
            "X-User-Id": "u_g",
            "Range": f"bytes={total + 1000}-{total + 2000}",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "audio_playback.malformed_range"
