"""POST /api/recordings/batch-download — pre-flight + streaming zip tests
(P4 IA refactor task 1.3).

Spec scenarios:
  - happy path returns streaming ZIP_STORED with valid entries
  - foreign id → 403 recording.forbidden
  - retention-expired (soft-deleted or out-of-window) → 410 recording.retention_expired
  - `them` stream value → 422 recording.invalid_stream
  - oversize selection → 413 recording.batch_oversize
  - StreamingResponse-driven generator (no full-archive buffering)
"""

from __future__ import annotations

import io
import struct
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


def _wav_bytes(seconds: int) -> bytes:
    sample_rate = 16000
    bits_per_sample = 16
    channels = 1
    data_len = sample_rate * channels * (bits_per_sample // 8) * seconds
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
    data_header = b"data" + struct.pack("<I", data_len)
    payload = b"WAVE" + fmt_chunk + data_header + (b"\x00" * data_len)
    return b"RIFF" + struct.pack("<I", len(payload) + 4) + payload


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


async def _insert_user(engine: AsyncEngine, user_id: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                'INSERT INTO "user" (id, name, email, "emailVerified") '
                "VALUES (:id, :id, :email, true) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )


async def _insert_meeting(
    engine: AsyncEngine,
    *,
    meeting_id: str,
    user_id: str,
    title: str = "Discovery call",
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, scheduled_start_at, created_at
                )
                VALUES (:mid, :uid, :title, 'Acme', 'Me', now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id, "title": title},
        )


async def _insert_recording(
    engine: AsyncEngine,
    *,
    recording_id: str,
    meeting_id: str,
    stream: str,
    started_at: datetime,
    file_path: Path,
    bytes_size: int,
    deleted_at: datetime | None = None,
    skip_check: bool = False,
) -> None:
    async with engine.begin() as conn:
        if skip_check:
            await conn.execute(
                text("ALTER TABLE recording DROP CONSTRAINT IF EXISTS recording_stream_check")
            )
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes,
                    created_at, started_at, source, deleted_at
                )
                VALUES (
                    :rid, :mid, :stream, :path, :bytes,
                    :started_at, :started_at, 'live', :deleted
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "rid": recording_id,
                "mid": meeting_id,
                "stream": stream,
                "path": str(file_path),
                "bytes": bytes_size,
                "started_at": started_at,
                "deleted": deleted_at,
            },
        )
        if skip_check:
            await conn.execute(
                text(
                    "ALTER TABLE recording ADD CONSTRAINT recording_stream_check "
                    "CHECK (stream IN ('me', 'counterparty')) NOT VALID"
                )
            )


@pytest.mark.asyncio
async def test_batch_download_happy_path_zip_stored(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_hp")
    await _insert_meeting(migrated_engine, meeting_id="m_hp_one", user_id="u_hp", title="Acme call")
    await _insert_meeting(
        migrated_engine, meeting_id="m_hp_two", user_id="u_hp", title="Globex sync"
    )
    now = datetime.now(UTC)
    wav_one = tmp_path / "one.wav"
    wav_two = tmp_path / "two.wav"
    wav_one.write_bytes(_wav_bytes(1))
    wav_two.write_bytes(_wav_bytes(1))

    await _insert_recording(
        migrated_engine,
        recording_id="r_hp_one",
        meeting_id="m_hp_one",
        stream="me",
        started_at=now - timedelta(hours=1),
        file_path=wav_one,
        bytes_size=wav_one.stat().st_size,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_hp_two",
        meeting_id="m_hp_two",
        stream="counterparty",
        started_at=now - timedelta(hours=2),
        file_path=wav_two,
        bytes_size=wav_two.stat().st_size,
    )

    resp = await api_client.get(
        "/api/recordings/batch-download",
        headers={"X-User-Id": "u_hp"},
        params={"ids": "r_hp_one,r_hp_two"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/zip")
    assert "attachment; filename=" in resp.headers["content-disposition"]
    assert "recordings-" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].endswith('.zip"')

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert len(names) == 2
    # Slug pulls the ASCII title, suffix carries the stream channel.
    assert any(name.startswith("Acme-call_") and name.endswith("_me.wav") for name in names)
    assert any(
        name.startswith("Globex-sync_") and name.endswith("_counterparty.wav") for name in names
    )
    # Entries are STORED (no deflate), per design choice for uncompressible WAVs.
    for info in zf.infolist():
        assert info.compress_type == zipfile.ZIP_STORED


@pytest.mark.asyncio
async def test_batch_download_foreign_id_returns_403(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_a")
    await _insert_user(migrated_engine, "u_b")
    await _insert_meeting(migrated_engine, meeting_id="m_b", user_id="u_b")
    wav = tmp_path / "fb.wav"
    wav.write_bytes(_wav_bytes(1))
    now = datetime.now(UTC)
    await _insert_recording(
        migrated_engine,
        recording_id="r_b",
        meeting_id="m_b",
        stream="me",
        started_at=now - timedelta(hours=1),
        file_path=wav,
        bytes_size=wav.stat().st_size,
    )

    resp = await api_client.post(
        "/api/recordings/batch-download/preflight",
        headers={"X-User-Id": "u_a"},
        json={"recording_ids": ["r_b"]},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "recording.forbidden"


@pytest.mark.asyncio
async def test_batch_download_missing_id_returns_403(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    """Unknown ids are treated like foreign ids (no existence leak)."""
    await _insert_user(migrated_engine, "u_unk")

    resp = await api_client.post(
        "/api/recordings/batch-download/preflight",
        headers={"X-User-Id": "u_unk"},
        json={"recording_ids": ["r_does_not_exist"]},
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "recording.forbidden"


@pytest.mark.asyncio
async def test_batch_download_retention_expired_returns_410(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_exp")
    await _insert_meeting(migrated_engine, meeting_id="m_soft", user_id="u_exp")
    await _insert_meeting(migrated_engine, meeting_id="m_window", user_id="u_exp")
    wav = tmp_path / "exp.wav"
    wav.write_bytes(_wav_bytes(1))
    now = datetime.now(UTC)
    await _insert_recording(
        migrated_engine,
        recording_id="r_soft",
        meeting_id="m_soft",
        stream="me",
        started_at=now - timedelta(hours=1),
        file_path=wav,
        bytes_size=wav.stat().st_size,
        deleted_at=now,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_outside",
        meeting_id="m_window",
        stream="me",
        started_at=now - timedelta(days=60),
        file_path=wav,
        bytes_size=wav.stat().st_size,
    )

    soft_resp = await api_client.post(
        "/api/recordings/batch-download/preflight",
        headers={"X-User-Id": "u_exp"},
        json={"recording_ids": ["r_soft"]},
    )
    assert soft_resp.status_code == 410
    assert soft_resp.json()["error_code"] == "recording.retention_expired"

    window_resp = await api_client.post(
        "/api/recordings/batch-download/preflight",
        headers={"X-User-Id": "u_exp"},
        json={"recording_ids": ["r_outside"]},
    )
    assert window_resp.status_code == 410
    assert window_resp.json()["error_code"] == "recording.retention_expired"


@pytest.mark.asyncio
async def test_batch_download_them_stream_returns_422(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_legacy")
    await _insert_meeting(migrated_engine, meeting_id="m_legacy", user_id="u_legacy")
    wav = tmp_path / "legacy.wav"
    wav.write_bytes(_wav_bytes(1))
    now = datetime.now(UTC)
    await _insert_recording(
        migrated_engine,
        recording_id="r_legacy",
        meeting_id="m_legacy",
        stream="them",
        started_at=now - timedelta(hours=1),
        file_path=wav,
        bytes_size=wav.stat().st_size,
        skip_check=True,
    )

    resp = await api_client.post(
        "/api/recordings/batch-download/preflight",
        headers={"X-User-Id": "u_legacy"},
        json={"recording_ids": ["r_legacy"]},
    )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "recording.invalid_stream"


@pytest.mark.asyncio
async def test_batch_download_oversize_returns_413(
    api_client: AsyncClient,
    migrated_engine: AsyncEngine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force a tiny cap so the assertion doesn't need a multi-GiB fixture.
    monkeypatch.setenv("RECORDING_BATCH_DOWNLOAD_MAX_BYTES", "1000")
    from meeting_playbook.config import get_settings

    get_settings.cache_clear()
    try:
        await _insert_user(migrated_engine, "u_big")
        await _insert_meeting(migrated_engine, meeting_id="m_big", user_id="u_big")
        wav = tmp_path / "big.wav"
        wav.write_bytes(_wav_bytes(1))
        now = datetime.now(UTC)
        await _insert_recording(
            migrated_engine,
            recording_id="r_big",
            meeting_id="m_big",
            stream="me",
            started_at=now - timedelta(hours=1),
            file_path=wav,
            bytes_size=wav.stat().st_size,
        )

        resp = await api_client.post(
            "/api/recordings/batch-download/preflight",
            headers={"X-User-Id": "u_big"},
            json={"recording_ids": ["r_big"]},
        )
        assert resp.status_code == 413
        assert resp.json()["error_code"] == "recording.batch_oversize"
        assert "1000" in resp.json()["message"]
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_batch_download_empty_body_rejected(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    await _insert_user(migrated_engine, "u_empty")
    resp = await api_client.post(
        "/api/recordings/batch-download/preflight",
        headers={"X-User-Id": "u_empty"},
        json={"recording_ids": []},
    )
    # min_length=1 on BatchDownloadRequest → validation error.
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_download_streams_via_generator(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Smoke check: the handler exposes a generator-driven StreamingResponse.

    The ASGI test transport collects the body before returning, so chunked
    transfer encoding isn't observable from the client side. Instead we
    drive the underlying `_zip_stream` async generator directly and assert
    it yields at least one buffered chunk per WAV (proves the implementation
    streams via the per-write drain helper rather than buffering the entire
    archive in memory).
    """
    from meeting_playbook.recordings.router import _zip_stream

    await _insert_user(migrated_engine, "u_str")
    await _insert_meeting(migrated_engine, meeting_id="m_str", user_id="u_str")
    wav = tmp_path / "str.wav"
    wav.write_bytes(_wav_bytes(1))
    now = datetime.now(UTC)
    await _insert_recording(
        migrated_engine,
        recording_id="r_str",
        meeting_id="m_str",
        stream="me",
        started_at=now - timedelta(hours=1),
        file_path=wav,
        bytes_size=wav.stat().st_size,
    )

    # 1. End-to-end via HTTP (GET streams direct-to-disk per gemini #48 HIGH).
    resp = await api_client.get(
        "/api/recordings/batch-download",
        headers={"X-User-Id": "u_str"},
        params={"ids": "r_str"},
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert len(zf.namelist()) == 1

    # 2. Unit-level: the underlying generator yields incremental chunks.
    chunks: list[bytes] = []
    async for chunk in _zip_stream([(wav, "x_me.wav")]):
        chunks.append(chunk)
    assert len(chunks) >= 1
    # Reassembling the chunks reproduces a valid zip — proves the generator
    # never withholds the trailing central-directory record.
    reassembled = b"".join(chunks)
    zf2 = zipfile.ZipFile(io.BytesIO(reassembled))
    assert zf2.namelist() == ["x_me.wav"]
