"""RecordingRetentionJob.cleanup tests — slice-11 task 4.2.

Per spec recording-retention ADDED requirement
"RecordingRetentionJob.cleanup deletes WAV files older than threshold":

  (a) 31-day-old wav file gets unlinked + row's deleted_at is stamped;
      5-day-old file is left alone; 60-day row whose wav was already deleted
      from disk gets self-healed (deleted_at stamped, no FileNotFoundError
      surfaces).
  (b) Idempotent: running cleanup twice with the same `now` produces zero
      additional unlinks on the second call.
  (c) Cleanup never touches transcript_chunk / chat_message rows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from meeting_playbook.retention.job import cleanup


async def _seed(
    engine: AsyncEngine,
    *,
    user_id: str = "u_ret",
    meeting_id: str = "m_ret",
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, name, email, "emailVerified")
                VALUES (:uid, :uid, :email, true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": user_id, "email": f"{user_id}@example.com"},
        )
        await conn.execute(
            text(
                """
                INSERT INTO meeting (
                    id, user_id, title, counterparty_display_name, me_display_name
                )
                VALUES (:mid, :uid, 'T', 'C', 'M')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"mid": meeting_id, "uid": user_id},
        )


async def _insert_recording(
    engine: AsyncEngine,
    *,
    rec_id: str,
    meeting_id: str,
    stream: str,
    file_path: Path,
    age_days: float,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes, created_at
                )
                VALUES (:rid, :mid, :stream, :fp, 100,
                    now() - (:age || ' days')::interval)
                """
            ),
            {
                "rid": rec_id,
                "mid": meeting_id,
                "stream": stream,
                "fp": str(file_path),
                "age": str(age_days),
            },
        )


@pytest.mark.asyncio
async def test_cleanup_deletes_old_files_and_self_heals_missing(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """31-day file deleted; 5-day file untouched; 60-day-already-missing self-heals."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    # 5 distinct meetings (recording UNIQUE on (meeting_id, stream) makes
    # multi-rows-per-meeting awkward; one meeting per row keeps the test simple).
    await _seed(migrated_engine, user_id="u_ret_a", meeting_id="m_ret_31d")
    await _seed(migrated_engine, user_id="u_ret_a", meeting_id="m_ret_5d")
    await _seed(migrated_engine, user_id="u_ret_a", meeting_id="m_ret_60d")

    wav_31d = tmp_path / "rec_31d.wav"
    wav_31d.write_bytes(b"\x00" * 100)
    wav_5d = tmp_path / "rec_5d.wav"
    wav_5d.write_bytes(b"\x00" * 100)
    wav_60d_missing = tmp_path / "rec_60d_missing.wav"  # never write to disk

    await _insert_recording(
        migrated_engine,
        rec_id="r_31d",
        meeting_id="m_ret_31d",
        stream="me",
        file_path=wav_31d,
        age_days=31,
    )
    await _insert_recording(
        migrated_engine,
        rec_id="r_5d",
        meeting_id="m_ret_5d",
        stream="me",
        file_path=wav_5d,
        age_days=5,
    )
    await _insert_recording(
        migrated_engine,
        rec_id="r_60d",
        meeting_id="m_ret_60d",
        stream="me",
        file_path=wav_60d_missing,
        age_days=60,
    )

    now = datetime.now(UTC)
    deleted_count = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        session_factory=Session,
    )
    assert deleted_count == 2, f"expected 2 (31d unlink + 60d self-heal); got {deleted_count}"
    assert not wav_31d.exists(), "31-day-old wav MUST be unlinked"
    assert wav_5d.exists(), "5-day-old wav MUST be left alone"

    # Verify DB stamps line up with the file-system outcome.
    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT id, deleted_at FROM recording "
                    "WHERE id IN ('r_31d', 'r_5d', 'r_60d') ORDER BY id"
                )
            )
        ).all()
    by_id = {r.id: r.deleted_at for r in rows}
    assert by_id["r_31d"] is not None, "31d row's deleted_at must be stamped"
    assert by_id["r_5d"] is None, "5d row's deleted_at must remain NULL"
    assert by_id["r_60d"] is not None, "60d row self-heal must stamp deleted_at"


@pytest.mark.asyncio
async def test_cleanup_is_idempotent(migrated_engine: AsyncEngine, tmp_path: Path) -> None:
    """Running cleanup twice with the same `now` produces 0 deletions on call 2."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_idem", meeting_id="m_idem")
    wav = tmp_path / "rec_idem.wav"
    wav.write_bytes(b"\x00" * 100)
    await _insert_recording(
        migrated_engine,
        rec_id="r_idem",
        meeting_id="m_idem",
        stream="me",
        file_path=wav,
        age_days=45,
    )

    now = datetime.now(UTC)
    first = await cleanup(
        now=now, retention_days=30, recordings_dir=tmp_path, session_factory=Session
    )
    second = await cleanup(
        now=now, retention_days=30, recordings_dir=tmp_path, session_factory=Session
    )
    assert first == 1
    assert second == 0, "second sweep should be a no-op (deleted_at already stamped)"
    assert not wav.exists()


@pytest.mark.asyncio
async def test_cleanup_never_touches_transcript_chunk_or_chat_message(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """transcript_chunk + chat_message row counts are unaffected by cleanup."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_no_touch", meeting_id="m_no_touch")
    wav = tmp_path / "rec_no_touch.wav"
    wav.write_bytes(b"\x00" * 100)
    await _insert_recording(
        migrated_engine,
        rec_id="r_no_touch",
        meeting_id="m_no_touch",
        stream="me",
        file_path=wav,
        age_days=45,
    )

    now = datetime.now(UTC)
    started = now - timedelta(minutes=5)
    ended = now - timedelta(minutes=4)
    async with migrated_engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO transcript_chunk (
                    id, meeting_id, speaker, text, started_at, ended_at,
                    asr_provider_used, confidence, created_at
                )
                VALUES ('tc_a', 'm_no_touch', 'me', 'hello', :s, :e,
                        'whisper', 0.9, now())
                """
            ),
            {"s": started, "e": ended},
        )
        await conn.execute(
            text(
                """
                INSERT INTO chat_message (id, meeting_id, role, content, created_at)
                VALUES ('cm_a', 'm_no_touch', 'user', 'hi', now())
                """
            )
        )

    await cleanup(now=now, retention_days=30, recordings_dir=tmp_path, session_factory=Session)

    async with migrated_engine.connect() as conn:
        tc_count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM transcript_chunk WHERE meeting_id = 'm_no_touch'")
            )
        ).scalar_one()
        cm_count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM chat_message WHERE meeting_id = 'm_no_touch'")
            )
        ).scalar_one()
    assert tc_count == 1, "cleanup must NOT touch transcript_chunk rows"
    assert cm_count == 1, "cleanup must NOT touch chat_message rows"
