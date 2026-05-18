"""GET /api/recordings — list endpoint tests (P4 IA refactor task 1.2).

Spec scenarios covered:
  - default-sorted list ordered by captured_at DESC and Recording-window scoped
  - filter by date range (`since`/`until`)
  - search by meeting title via ILIKE
  - page-based pagination metadata
  - foreign-user isolation
  - legacy `them` stream values filtered out
  - retention-expired rows excluded (deleted_at IS NOT NULL OR out-of-window)
  - 401 when X-User-Id header missing (auth.gateway_bypass)
"""

from __future__ import annotations

import struct
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
    """Build an in-memory valid 16 kHz mono 16-bit PCM WAV of the given length."""
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
    counterparty: str = "Acme Inc.",
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name,
                    me_display_name, scheduled_start_at, created_at
                )
                VALUES (:mid, :uid, :title, :cp, 'Me', now(), now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id, "title": title, "cp": counterparty},
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
        # Some scenarios need to insert legacy `them` rows that the CHECK
        # constraint would normally reject. Drop the constraint for the
        # insert, then immediately restore it so the schema-shape test
        # downstream still sees the constraint intact.
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
async def test_list_orders_by_captured_at_desc_inside_window(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_list")
    await _insert_meeting(migrated_engine, meeting_id="m_list", user_id="u_list")

    now = datetime.now(UTC)
    wav = tmp_path / "r.wav"
    wav.write_bytes(_wav_bytes(1))
    size = wav.stat().st_size

    await _insert_recording(
        migrated_engine,
        recording_id="r_old",
        meeting_id="m_list",
        stream="me",
        started_at=now - timedelta(days=2),
        file_path=wav,
        bytes_size=size,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_new",
        meeting_id="m_list",
        stream="counterparty",
        started_at=now - timedelta(hours=1),
        file_path=wav,
        bytes_size=size,
    )

    resp = await api_client.get("/api/recordings", headers={"X-User-Id": "u_list"})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    ids = [row["id"] for row in payload["recordings"]]
    assert ids == ["r_new", "r_old"]
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 25
    # duration_ms derived from bytes - 44 header / 32_000 bytes-per-second.
    expected_ms = ((size - 44) * 1000) // 32_000
    for row in payload["recordings"]:
        assert row["duration_ms"] == expected_ms
        assert row["byte_size"] == size
        assert row["meeting_title"] == "Discovery call"
        assert row["counterparty_label"] == "Acme Inc."
        assert row["stream"] in {"me", "counterparty"}


@pytest.mark.asyncio
async def test_list_excludes_retention_expired_and_soft_deleted(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_ret")
    # The recording table has UNIQUE (meeting_id, stream); one fresh meeting
    # per row keeps the test independent of the production constraint.
    await _insert_meeting(migrated_engine, meeting_id="m_inside", user_id="u_ret")
    await _insert_meeting(migrated_engine, meeting_id="m_outside", user_id="u_ret")
    await _insert_meeting(migrated_engine, meeting_id="m_soft", user_id="u_ret")
    now = datetime.now(UTC)
    wav = tmp_path / "ret.wav"
    wav.write_bytes(_wav_bytes(1))
    size = wav.stat().st_size

    await _insert_recording(
        migrated_engine,
        recording_id="r_inside",
        meeting_id="m_inside",
        stream="me",
        started_at=now - timedelta(days=5),
        file_path=wav,
        bytes_size=size,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_outside",
        meeting_id="m_outside",
        stream="me",
        started_at=now - timedelta(days=60),
        file_path=wav,
        bytes_size=size,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_soft",
        meeting_id="m_soft",
        stream="me",
        started_at=now - timedelta(days=2),
        file_path=wav,
        bytes_size=size,
        deleted_at=now,
    )

    resp = await api_client.get("/api/recordings", headers={"X-User-Id": "u_ret"})
    assert resp.status_code == 200
    payload = resp.json()
    ids = [row["id"] for row in payload["recordings"]]
    assert ids == ["r_inside"]
    assert payload["total"] == 1


@pytest.mark.asyncio
async def test_list_isolates_foreign_user_rows(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_a")
    await _insert_user(migrated_engine, "u_b")
    await _insert_meeting(migrated_engine, meeting_id="m_a", user_id="u_a")
    await _insert_meeting(migrated_engine, meeting_id="m_b", user_id="u_b")
    now = datetime.now(UTC)
    wav = tmp_path / "iso.wav"
    wav.write_bytes(_wav_bytes(1))
    size = wav.stat().st_size

    await _insert_recording(
        migrated_engine,
        recording_id="r_a",
        meeting_id="m_a",
        stream="me",
        started_at=now - timedelta(days=1),
        file_path=wav,
        bytes_size=size,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_b",
        meeting_id="m_b",
        stream="me",
        started_at=now - timedelta(days=1),
        file_path=wav,
        bytes_size=size,
    )

    resp = await api_client.get("/api/recordings", headers={"X-User-Id": "u_b"})
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()["recordings"]]
    assert ids == ["r_b"]


@pytest.mark.asyncio
async def test_list_filters_legacy_them_stream_values(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_them")
    await _insert_meeting(migrated_engine, meeting_id="m_them_ok", user_id="u_them")
    await _insert_meeting(migrated_engine, meeting_id="m_them_legacy", user_id="u_them")
    now = datetime.now(UTC)
    wav = tmp_path / "them.wav"
    wav.write_bytes(_wav_bytes(1))
    size = wav.stat().st_size

    await _insert_recording(
        migrated_engine,
        recording_id="r_ok",
        meeting_id="m_them_ok",
        stream="me",
        started_at=now - timedelta(hours=1),
        file_path=wav,
        bytes_size=size,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_legacy",
        meeting_id="m_them_legacy",
        stream="them",
        started_at=now - timedelta(hours=2),
        file_path=wav,
        bytes_size=size,
        skip_check=True,
    )

    resp = await api_client.get("/api/recordings", headers={"X-User-Id": "u_them"})
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()["recordings"]]
    assert ids == ["r_ok"]


@pytest.mark.asyncio
async def test_list_pagination_metadata_reflects_offset(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_pg")
    now = datetime.now(UTC)
    wav = tmp_path / "p.wav"
    wav.write_bytes(_wav_bytes(1))
    size = wav.stat().st_size

    for i in range(7):
        await _insert_meeting(migrated_engine, meeting_id=f"m_pg_{i:02d}", user_id="u_pg")
        await _insert_recording(
            migrated_engine,
            recording_id=f"r_pg_{i:02d}",
            meeting_id=f"m_pg_{i:02d}",
            stream="me",
            started_at=now - timedelta(hours=i + 1),
            file_path=wav,
            bytes_size=size,
        )

    resp = await api_client.get(
        "/api/recordings?page=2&page_size=3",
        headers={"X-User-Id": "u_pg"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 3
    assert payload["total"] == 7
    assert len(payload["recordings"]) == 3
    # The 4th, 5th, 6th most recent rows (0-indexed offset 3, 4, 5).
    assert [r["id"] for r in payload["recordings"]] == ["r_pg_03", "r_pg_04", "r_pg_05"]


@pytest.mark.asyncio
async def test_list_search_uses_ilike_on_meeting_title(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_s")
    await _insert_meeting(
        migrated_engine, meeting_id="m_acme", user_id="u_s", title="Acme negotiation"
    )
    await _insert_meeting(
        migrated_engine, meeting_id="m_globex", user_id="u_s", title="Globex sync"
    )
    now = datetime.now(UTC)
    wav = tmp_path / "s.wav"
    wav.write_bytes(_wav_bytes(1))
    size = wav.stat().st_size

    await _insert_recording(
        migrated_engine,
        recording_id="r_acme",
        meeting_id="m_acme",
        stream="me",
        started_at=now - timedelta(hours=1),
        file_path=wav,
        bytes_size=size,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_globex",
        meeting_id="m_globex",
        stream="me",
        started_at=now - timedelta(hours=2),
        file_path=wav,
        bytes_size=size,
    )

    resp = await api_client.get(
        "/api/recordings?search=acme",
        headers={"X-User-Id": "u_s"},
    )
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()["recordings"]]
    assert ids == ["r_acme"]


@pytest.mark.asyncio
async def test_list_date_range_filter_inside_window(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    await _insert_user(migrated_engine, "u_dr")
    await _insert_meeting(migrated_engine, meeting_id="m_dr_in", user_id="u_dr")
    await _insert_meeting(migrated_engine, meeting_id="m_dr_out", user_id="u_dr")
    now = datetime.now(UTC)
    wav = tmp_path / "dr.wav"
    wav.write_bytes(_wav_bytes(1))
    size = wav.stat().st_size

    in_range = now - timedelta(days=3)
    out_of_range = now - timedelta(days=10)
    await _insert_recording(
        migrated_engine,
        recording_id="r_in",
        meeting_id="m_dr_in",
        stream="me",
        started_at=in_range,
        file_path=wav,
        bytes_size=size,
    )
    await _insert_recording(
        migrated_engine,
        recording_id="r_out",
        meeting_id="m_dr_out",
        stream="me",
        started_at=out_of_range,
        file_path=wav,
        bytes_size=size,
    )

    since = (now - timedelta(days=5)).date().isoformat()
    resp = await api_client.get(
        f"/api/recordings?since={since}",
        headers={"X-User-Id": "u_dr"},
    )
    assert resp.status_code == 200
    ids = [row["id"] for row in resp.json()["recordings"]]
    assert ids == ["r_in"]


@pytest.mark.asyncio
async def test_list_requires_gateway_user_header(api_client: AsyncClient) -> None:
    resp = await api_client.get("/api/recordings")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "auth.gateway_bypass"
