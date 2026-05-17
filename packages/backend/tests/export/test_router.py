"""FastAPI export router integration tests (slice-22-export-bundle).

Per spec `meeting-export/spec.md`:
- 200 + `application/zip` + RFC 5987 dual-value `Content-Disposition` header
  on owned meeting.
- 404 `meeting.not_found` on cross-user export.
- 401 `auth.gateway_bypass` on missing X-User-Id.
- End-to-end shape: namelist matches `{playbook.md, transcript.md,
  summary.md, recordings/<active>.wav}` and soft-deleted recordings are
  absent.
"""

from __future__ import annotations

import io
import secrets
import wave
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.export.router import get_session_factory_for_export
from meeting_playbook.meetings.dependencies import get_session_dependency
from meeting_playbook.server import create_app


@pytest_asyncio.fixture
async def api_client(migrated_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    async def _override_session() -> AsyncIterator[AsyncSession]:
        async with Session() as s:
            yield s

    def _override_factory() -> async_sessionmaker[AsyncSession]:
        return Session

    app = create_app()
    app.dependency_overrides[get_session_dependency] = _override_session
    app.dependency_overrides[get_session_factory_for_export] = _override_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client


async def _seed_user(engine: AsyncEngine, user_id: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:id, :id, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )


async def _seed_meeting(
    engine: AsyncEngine,
    *,
    user_id: str,
    meeting_id: str,
    title: str,
    scheduled: datetime,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name,
                    status, asr_provider, created_at, scheduled_start_at
                )
                VALUES (:id, :uid, :title, 'C', 'M', 'completed', 'qwen3',
                        :now, :sched)
                """
            ),
            {
                "id": meeting_id,
                "uid": user_id,
                "title": title,
                "now": datetime.now(UTC),
                "sched": scheduled,
            },
        )


async def _seed_playbook(engine: AsyncEngine, *, meeting_id: str) -> None:
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO playbook (
                    id, meeting_id, free_form_markdown, objective,
                    counterparty_profile, anticipated_topics,
                    anticipated_objections, talking_points, red_lines,
                    created_at, updated_at
                )
                VALUES (:id, :mid, '', 'Close', '', '', '', '', '', :now, :now)
                """
            ),
            {"id": f"pb_{secrets.token_urlsafe(8)}", "mid": meeting_id, "now": now},
        )


async def _seed_chunks(engine: AsyncEngine, *, meeting_id: str, count: int = 3) -> None:
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        for i in range(count):
            await conn.execute(
                text(
                    """
                    INSERT INTO transcript_chunk (
                        id, meeting_id, speaker, text, started_at, ended_at,
                        asr_provider_used, created_at
                    )
                    VALUES (:id, :mid, :sp, :tx, :start, :end, 'qwen3', :now)
                    """
                ),
                {
                    "id": f"tc_{secrets.token_urlsafe(8)}_{i}",
                    "mid": meeting_id,
                    "sp": "me" if i % 2 == 0 else "counterparty",
                    "tx": f"Line {i}",
                    "start": now,
                    "end": now,
                    "now": now,
                },
            )


async def _seed_summary(engine: AsyncEngine, *, meeting_id: str, markdown: str) -> None:
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO summary (id, meeting_id, markdown, generated_at)
                VALUES (:id, :mid, :md, :now)
                """
            ),
            {
                "id": f"sm_{secrets.token_urlsafe(8)}",
                "mid": meeting_id,
                "md": markdown,
                "now": now,
            },
        )


async def _seed_recording(
    engine: AsyncEngine,
    *,
    meeting_id: str,
    stream: str,
    file_path: str,
    deleted: bool = False,
) -> None:
    now = datetime.now(UTC)
    deleted_at = now if deleted else None
    size = Path(file_path).stat().st_size
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes,
                    created_at, started_at, deleted_at, source
                )
                VALUES (:id, :mid, :stream, :fp, :bytes, :now, :now, :del, 'live')
                """
            ),
            {
                "id": f"rec_{secrets.token_urlsafe(8)}_{stream}",
                "mid": meeting_id,
                "stream": stream,
                "fp": file_path,
                "bytes": size,
                "now": now,
                "del": deleted_at,
            },
        )


def _make_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        w.writeframes(b"\x00\x00" * 500)


@pytest.mark.asyncio
async def test_export_endpoint_returns_zip_with_correct_disposition(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Owned meeting → 200 + Content-Type application/zip + RFC 5987 header."""
    await _seed_user(migrated_engine, "u_a")
    await _seed_meeting(
        migrated_engine,
        user_id="u_a",
        meeting_id="m_disp",
        title="Q3 規劃會議",
        scheduled=datetime(2026, 5, 15, 14, 0, 0, tzinfo=UTC),
    )
    await _seed_playbook(migrated_engine, meeting_id="m_disp")
    await _seed_chunks(migrated_engine, meeting_id="m_disp", count=1)
    wav = tmp_path / "cp.wav"
    _make_wav(wav)
    await _seed_recording(
        migrated_engine,
        meeting_id="m_disp",
        stream="counterparty",
        file_path=str(wav),
    )

    resp = await api_client.get(
        "/api/meetings/m_disp/export",
        headers={"X-User-Id": "u_a"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment;"), disposition
    # ASCII fallback filename and date suffix present.
    assert "filename=" in disposition
    assert "2026-05-15" in disposition
    # RFC 5987 unicode form.
    assert "filename*=UTF-8''" in disposition
    # Body is a valid ZIP.
    with zipfile.ZipFile(io.BytesIO(resp.content), "r") as zf:
        names = set(zf.namelist())
        assert "playbook.md" in names
        assert "transcript.md" in names
        assert "recordings/counterparty.wav" in names


@pytest.mark.asyncio
async def test_export_endpoint_returns_404_for_other_users_meeting(
    api_client: AsyncClient, migrated_engine: AsyncEngine
) -> None:
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    await _seed_meeting(
        migrated_engine,
        user_id="u_b",
        meeting_id="m_other",
        title="Other user",
        scheduled=datetime(2026, 5, 1, tzinfo=UTC),
    )

    resp = await api_client.get(
        "/api/meetings/m_other/export",
        headers={"X-User-Id": "u_a"},
    )

    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["error_code"] == "meeting.not_found"


@pytest.mark.asyncio
async def test_export_endpoint_rejects_missing_x_user_id(
    api_client: AsyncClient,
) -> None:
    resp = await api_client.get("/api/meetings/anything/export")
    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert body["error_code"] == "auth.gateway_bypass"


@pytest.mark.asyncio
async def test_export_endpoint_end_to_end_bundle_shape(
    api_client: AsyncClient, migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """End-to-end: full meeting with 2 recordings (1 deleted), summary, playbook, 3 chunks."""
    await _seed_user(migrated_engine, "u_e2e")
    await _seed_meeting(
        migrated_engine,
        user_id="u_e2e",
        meeting_id="m_e2e",
        title="E2E meeting",
        scheduled=datetime(2026, 5, 15, 14, 0, 0, tzinfo=UTC),
    )
    await _seed_playbook(migrated_engine, meeting_id="m_e2e")
    await _seed_chunks(migrated_engine, meeting_id="m_e2e", count=3)
    await _seed_summary(migrated_engine, meeting_id="m_e2e", markdown="## Notes\n- ok\n")

    wav_active = tmp_path / "active.wav"
    wav_expired = tmp_path / "expired.wav"
    _make_wav(wav_active)
    _make_wav(wav_expired)
    await _seed_recording(
        migrated_engine,
        meeting_id="m_e2e",
        stream="counterparty",
        file_path=str(wav_active),
    )
    await _seed_recording(
        migrated_engine,
        meeting_id="m_e2e",
        stream="me",
        file_path=str(wav_expired),
        deleted=True,
    )

    # Use the streaming-aware path: read raw body bytes.
    resp = await api_client.get(
        "/api/meetings/m_e2e/export",
        headers={"X-User-Id": "u_e2e"},
    )

    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert "filename=" in disposition
    assert "filename*=UTF-8''" in disposition

    with zipfile.ZipFile(io.BytesIO(resp.content), "r") as zf:
        names = set(zf.namelist())
        assert names == {
            "playbook.md",
            "transcript.md",
            "summary.md",
            "recordings/counterparty.wav",
        }
        assert "recordings/me.wav" not in names

    # No-summary branch
    await _seed_meeting(
        migrated_engine,
        user_id="u_e2e",
        meeting_id="m_e2e_no_sum",
        title="No summary",
        scheduled=datetime(2026, 5, 15, tzinfo=UTC),
    )
    await _seed_playbook(migrated_engine, meeting_id="m_e2e_no_sum")
    await _seed_chunks(migrated_engine, meeting_id="m_e2e_no_sum", count=1)
    resp2 = await api_client.get(
        "/api/meetings/m_e2e_no_sum/export", headers={"X-User-Id": "u_e2e"}
    )
    with zipfile.ZipFile(io.BytesIO(resp2.content), "r") as zf:
        names2 = set(zf.namelist())
        assert "summary.md" not in names2
        assert names2 == {"playbook.md", "transcript.md"}

    # All-recordings-expired branch
    await _seed_meeting(
        migrated_engine,
        user_id="u_e2e",
        meeting_id="m_e2e_all_exp",
        title="All expired",
        scheduled=datetime(2026, 5, 15, tzinfo=UTC),
    )
    await _seed_playbook(migrated_engine, meeting_id="m_e2e_all_exp")
    await _seed_chunks(migrated_engine, meeting_id="m_e2e_all_exp", count=1)
    await _seed_summary(migrated_engine, meeting_id="m_e2e_all_exp", markdown="x")
    wav_exp2 = tmp_path / "exp2.wav"
    _make_wav(wav_exp2)
    await _seed_recording(
        migrated_engine,
        meeting_id="m_e2e_all_exp",
        stream="counterparty",
        file_path=str(wav_exp2),
        deleted=True,
    )
    resp3 = await api_client.get(
        "/api/meetings/m_e2e_all_exp/export", headers={"X-User-Id": "u_e2e"}
    )
    with zipfile.ZipFile(io.BytesIO(resp3.content), "r") as zf:
        names3 = set(zf.namelist())
        assert names3 == {"playbook.md", "transcript.md", "summary.md"}
        assert not any(n.startswith("recordings/") for n in names3)
