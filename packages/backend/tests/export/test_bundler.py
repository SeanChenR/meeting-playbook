"""MeetingExportBundler integration tests (slice-22-export-bundle).

Per spec `meeting-export/spec.md`:
- Bundler streams a ZIP archive for a single meeting.
- Recordings whose Recording row is `deleted_at IS NOT NULL` SHALL be excluded.
- `summary.md` SHALL be skipped when no Summary row exists.
- Bundler MUST stream WAV bytes through chunked reads (peak heap delta < 20 MiB
  on a 200 MiB fixture WAV).
- Cross-user calls raise `MeetingNotFound`.
"""

from __future__ import annotations

import gc
import io
import secrets
import tracemalloc
import wave
import zipfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from meeting_playbook.export.bundler import MeetingExportBundler, MeetingNotFound


# ─── Helpers ────────────────────────────────────────────────────────


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
    engine: AsyncEngine, *, user_id: str, meeting_id: str, title: str = "T"
) -> None:
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name,
                    status, asr_provider, created_at, scheduled_start_at
                )
                VALUES (:id, :uid, :title, 'C', 'M', 'completed', 'qwen3',
                        :now, :now)
                """
            ),
            {"id": meeting_id, "uid": user_id, "title": title, "now": now},
        )


async def _seed_playbook(
    engine: AsyncEngine, *, meeting_id: str, objective: str = "Close deal"
) -> None:
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
                VALUES (:id, :mid, '', :obj, '', '', '', '', '', :now, :now)
                """
            ),
            {
                "id": f"pb_{secrets.token_urlsafe(8)}",
                "mid": meeting_id,
                "obj": objective,
                "now": now,
            },
        )


async def _seed_chunks(
    engine: AsyncEngine,
    *,
    meeting_id: str,
    count: int = 3,
) -> None:
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
    bytes_size: int,
    deleted: bool = False,
) -> None:
    now = datetime.now(UTC)
    deleted_at = now if deleted else None
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
                "bytes": bytes_size,
                "now": now,
                "del": deleted_at,
            },
        )


def _make_wav(path: Path, sample_count: int = 1000) -> None:
    """Write a tiny valid PCM16 mono WAV (defaults to ~2 KB)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        # Silent frames are fine — bundler only cares about bytes.
        w.writeframes(b"\x00\x00" * sample_count)


def _make_large_wav(path: Path, target_bytes: int) -> None:
    """Build a large WAV by writing one big frame buffer directly.

    We do not need a valid header for streaming purposes — the bundler treats
    the file as raw bytes inside the zip entry — but we still use the `wave`
    header to keep the file at least parseable. The body itself is filled
    with zero bytes which compresses well; we use ZIP_STORED to avoid the
    deflate-compression heap growth confounding the streaming test.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Each sample is 2 bytes (PCM16 mono); chunk-write to avoid one big alloc.
    samples_per_chunk = 1 << 19  # 512 KiB of samples = 1 MiB body bytes
    written = 0
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        buf = b"\x00\x00" * samples_per_chunk
        while written < target_bytes:
            w.writeframes(buf)
            written += len(buf)


async def _collect_zip(bundler: MeetingExportBundler, meeting_id: str, user_id: str) -> bytes:
    """Drain the async generator into a single bytes object."""
    buf = io.BytesIO()
    async for chunk in bundler.iter_zip_chunks(meeting_id=meeting_id, user_id=user_id):
        buf.write(chunk)
    return buf.getvalue()


# ─── Fixtures ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def session_factory(
    migrated_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(migrated_engine, expire_on_commit=False)


# ─── Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bundler_includes_playbook_transcript_summary_when_summary_exists(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    """Happy path: ZIP namelist contains 3 markdown + 2 recordings."""
    await _seed_user(migrated_engine, "u_a")
    await _seed_meeting(migrated_engine, user_id="u_a", meeting_id="m_1", title="Q3 Review")
    await _seed_playbook(migrated_engine, meeting_id="m_1", objective="Close Q3 deal")
    await _seed_chunks(migrated_engine, meeting_id="m_1", count=3)
    await _seed_summary(migrated_engine, meeting_id="m_1", markdown="## Decisions\n- ship\n")

    wav_cp = tmp_path / "cp.wav"
    wav_me = tmp_path / "me.wav"
    _make_wav(wav_cp)
    _make_wav(wav_me)
    await _seed_recording(
        migrated_engine,
        meeting_id="m_1",
        stream="counterparty",
        file_path=str(wav_cp),
        bytes_size=wav_cp.stat().st_size,
    )
    await _seed_recording(
        migrated_engine,
        meeting_id="m_1",
        stream="me",
        file_path=str(wav_me),
        bytes_size=wav_me.stat().st_size,
    )

    bundler = MeetingExportBundler(session_factory=session_factory)
    zip_bytes = await _collect_zip(bundler, "m_1", "u_a")

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = set(zf.namelist())
        assert names == {
            "playbook.md",
            "transcript.md",
            "summary.md",
            "recordings/counterparty.wav",
            "recordings/me.wav",
        }
        # Spot-check content.
        playbook_md = zf.read("playbook.md").decode("utf-8")
        assert "# Q3 Review" in playbook_md
        assert "Close Q3 deal" in playbook_md
        transcript_md = zf.read("transcript.md").decode("utf-8")
        assert "# Transcript" in transcript_md
        assert "Line 0" in transcript_md
        summary_md = zf.read("summary.md").decode("utf-8")
        assert "# Summary" in summary_md
        assert "## Decisions" in summary_md


@pytest.mark.asyncio
async def test_bundler_raises_meeting_not_found_for_cross_user(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(migrated_engine, "u_a")
    await _seed_user(migrated_engine, "u_b")
    await _seed_meeting(migrated_engine, user_id="u_b", meeting_id="m_2")

    bundler = MeetingExportBundler(session_factory=session_factory)

    with pytest.raises(MeetingNotFound):
        async for _ in bundler.iter_zip_chunks(meeting_id="m_2", user_id="u_a"):
            pass


@pytest.mark.asyncio
async def test_bundler_excludes_recording_when_deleted_at_set(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    """Soft-deleted recording is excluded but other artefacts remain."""
    await _seed_user(migrated_engine, "u_a")
    await _seed_meeting(migrated_engine, user_id="u_a", meeting_id="m_3")
    await _seed_playbook(migrated_engine, meeting_id="m_3")
    await _seed_chunks(migrated_engine, meeting_id="m_3", count=2)
    await _seed_summary(migrated_engine, meeting_id="m_3", markdown="ok")

    wav_cp = tmp_path / "cp.wav"
    wav_me = tmp_path / "me.wav"
    _make_wav(wav_cp)
    _make_wav(wav_me)
    await _seed_recording(
        migrated_engine,
        meeting_id="m_3",
        stream="counterparty",
        file_path=str(wav_cp),
        bytes_size=wav_cp.stat().st_size,
    )
    await _seed_recording(
        migrated_engine,
        meeting_id="m_3",
        stream="me",
        file_path=str(wav_me),
        bytes_size=wav_me.stat().st_size,
        deleted=True,
    )

    bundler = MeetingExportBundler(session_factory=session_factory)
    zip_bytes = await _collect_zip(bundler, "m_3", "u_a")

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = set(zf.namelist())
        assert "recordings/counterparty.wav" in names
        assert "recordings/me.wav" not in names
        assert "playbook.md" in names
        assert "transcript.md" in names
        assert "summary.md" in names


@pytest.mark.asyncio
async def test_bundler_excludes_all_recordings_when_all_expired(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed_user(migrated_engine, "u_a")
    await _seed_meeting(migrated_engine, user_id="u_a", meeting_id="m_4")
    await _seed_playbook(migrated_engine, meeting_id="m_4")
    await _seed_chunks(migrated_engine, meeting_id="m_4", count=1)
    await _seed_summary(migrated_engine, meeting_id="m_4", markdown="ok")

    wav_cp = tmp_path / "cp.wav"
    wav_me = tmp_path / "me.wav"
    _make_wav(wav_cp)
    _make_wav(wav_me)
    await _seed_recording(
        migrated_engine,
        meeting_id="m_4",
        stream="counterparty",
        file_path=str(wav_cp),
        bytes_size=wav_cp.stat().st_size,
        deleted=True,
    )
    await _seed_recording(
        migrated_engine,
        meeting_id="m_4",
        stream="me",
        file_path=str(wav_me),
        bytes_size=wav_me.stat().st_size,
        deleted=True,
    )

    bundler = MeetingExportBundler(session_factory=session_factory)
    zip_bytes = await _collect_zip(bundler, "m_4", "u_a")

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = set(zf.namelist())
        assert names == {"playbook.md", "transcript.md", "summary.md"}


@pytest.mark.asyncio
async def test_bundler_skips_summary_when_no_summary_row(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    await _seed_user(migrated_engine, "u_a")
    await _seed_meeting(migrated_engine, user_id="u_a", meeting_id="m_5")
    await _seed_playbook(migrated_engine, meeting_id="m_5")
    await _seed_chunks(migrated_engine, meeting_id="m_5", count=1)
    # NO summary seeded.
    wav = tmp_path / "rec.wav"
    _make_wav(wav)
    await _seed_recording(
        migrated_engine,
        meeting_id="m_5",
        stream="counterparty",
        file_path=str(wav),
        bytes_size=wav.stat().st_size,
    )

    bundler = MeetingExportBundler(session_factory=session_factory)
    zip_bytes = await _collect_zip(bundler, "m_5", "u_a")

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = set(zf.namelist())
        assert "summary.md" not in names
        assert "playbook.md" in names
        assert "transcript.md" in names
        assert "recordings/counterparty.wav" in names


@pytest.mark.asyncio
async def test_bundler_streams_wav_without_loading_full_file(
    migrated_engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    """Peak heap delta MUST remain under 20 MiB while streaming a 200 MiB WAV.

    Spec scenario: "Bundler refuses to materialize a large WAV in memory."

    We assert peak < 20 MiB. The 200 MiB target is a deliberate magnitude
    that would force naive `f.read()` implementations to blow well past the
    budget, while chunked-streaming + spooled tmpfile (4 MiB spool) easily
    stays under it.
    """
    await _seed_user(migrated_engine, "u_a")
    await _seed_meeting(migrated_engine, user_id="u_a", meeting_id="m_big")
    await _seed_playbook(migrated_engine, meeting_id="m_big")

    big_wav = tmp_path / "big.wav"
    _make_large_wav(big_wav, target_bytes=200 * 1024 * 1024)
    await _seed_recording(
        migrated_engine,
        meeting_id="m_big",
        stream="counterparty",
        file_path=str(big_wav),
        bytes_size=big_wav.stat().st_size,
    )

    bundler = MeetingExportBundler(session_factory=session_factory)

    gc.collect()
    tracemalloc.start()

    # Drain the generator but DO NOT keep the bytes in memory — write to
    # /dev/null-equivalent so the assertion measures the bundler's own
    # allocation footprint, not our buffer.
    null_sink = tmp_path / "sink.zip"
    with null_sink.open("wb") as sink:
        async for chunk in bundler.iter_zip_chunks(meeting_id="m_big", user_id="u_a"):
            sink.write(chunk)

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # 20 MiB ceiling per spec scenario.
    assert peak < 20 * 1024 * 1024, f"peak heap = {peak} bytes (>= 20 MiB)"
