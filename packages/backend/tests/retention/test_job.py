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


async def _insert_attachment(
    engine: AsyncEngine,
    *,
    att_id: str,
    meeting_id: str | None,
    file_path: Path,
    age_days: float,
    kind: str = "pdf",
    original_name: str = "x.pdf",
    bytes_: int = 100,
    user_id: str = "u_ret",
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting_attachment (
                    id, meeting_id, user_id, file_path, kind, original_name, bytes,
                    uploaded_at
                )
                VALUES (:aid, :mid, :uid, :fp, :kind, :name, :bytes,
                    now() - (:age || ' days')::interval)
                """
            ),
            {
                "aid": att_id,
                "mid": meeting_id,
                "uid": user_id,
                "fp": str(file_path),
                "kind": kind,
                "name": original_name,
                "bytes": bytes_,
                "age": str(age_days),
            },
        )


async def _insert_recording(
    engine: AsyncEngine,
    *,
    rec_id: str,
    meeting_id: str,
    stream: str,
    file_path: Path,
    age_days: float,
    source: str = "live",
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes,
                    created_at, started_at, source
                )
                VALUES (:rid, :mid, :stream, :fp, 100,
                    now() - (:age || ' days')::interval,
                    now() - (:age || ' days')::interval,
                    :source)
                """
            ),
            {
                "rid": rec_id,
                "mid": meeting_id,
                "stream": stream,
                "fp": str(file_path),
                "age": str(age_days),
                "source": source,
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


@pytest.mark.asyncio
async def test_cleanup_treats_offline_source_recordings_identically(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Slice-14 regression: `source = 'offline'` rows obey the same 30-day
    retention clock as `source = 'live'` rows. The cleanup query MUST NOT
    filter on `source`.
    """
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_off_ret", meeting_id="m_off_ret")
    wav = tmp_path / "rec_offline_31d.wav"
    wav.write_bytes(b"\x00" * 100)
    await _insert_recording(
        migrated_engine,
        rec_id="r_off_31d",
        meeting_id="m_off_ret",
        stream="me",
        file_path=wav,
        age_days=31,
        source="offline",
    )

    now = datetime.now(UTC)
    deleted_count = await cleanup(
        now=now, retention_days=30, recordings_dir=tmp_path, session_factory=Session
    )

    assert deleted_count == 1, (
        f"offline-source recording past retention MUST be unlinked; got {deleted_count}"
    )
    assert not wav.exists(), "offline-source WAV file MUST be removed from disk"

    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT source, deleted_at FROM recording WHERE id = 'r_off_31d'")
            )
        ).first()
    assert row is not None
    assert row.source == "offline"
    assert row.deleted_at is not None, (
        "offline-source row's deleted_at MUST be stamped after cleanup"
    )


# ─── Slice 20a: meeting_attachment sweep ────────────────────────────


@pytest.mark.asyncio
async def test_cleanup_deletes_old_attachment_and_leaves_fresh(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Slice-20a: attachment-only scenario. 31-day deleted; 5-day untouched;
    45-day self-heal when file missing.
    """
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_att", meeting_id="m_att")

    old = tmp_path / "att_31d.pdf"
    old.write_bytes(b"\x00" * 100)
    fresh = tmp_path / "att_5d.pdf"
    fresh.write_bytes(b"\x00" * 100)
    missing = tmp_path / "att_45d_missing.pdf"

    await _insert_attachment(
        migrated_engine,
        att_id="a_31d",
        meeting_id="m_att",
        user_id="u_att",
        file_path=old,
        age_days=31,
    )
    await _insert_attachment(
        migrated_engine,
        att_id="a_5d",
        meeting_id="m_att",
        user_id="u_att",
        file_path=fresh,
        age_days=5,
    )
    await _insert_attachment(
        migrated_engine,
        att_id="a_45d",
        meeting_id="m_att",
        user_id="u_att",
        file_path=missing,
        age_days=45,
    )

    now = datetime.now(UTC)
    deleted_count = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        attachments_dir=tmp_path,
        session_factory=Session,
    )
    assert deleted_count == 2, f"expected 2 (31d unlink + 45d self-heal); got {deleted_count}"
    assert not old.exists()
    assert fresh.exists()

    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT id, deleted_at FROM meeting_attachment "
                    "WHERE id IN ('a_31d', 'a_5d', 'a_45d') ORDER BY id"
                )
            )
        ).all()
    by_id = {r.id: r.deleted_at for r in rows}
    assert by_id["a_31d"] is not None
    assert by_id["a_5d"] is None
    assert by_id["a_45d"] is not None


@pytest.mark.asyncio
async def test_cleanup_processes_recordings_and_attachments_together(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Mixed sweep: 2 old recordings + 2 old attachments → returns 4."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_mix", meeting_id="m_mix_a")
    await _seed(migrated_engine, user_id="u_mix", meeting_id="m_mix_b")

    wav_a = tmp_path / "rec_a.wav"
    wav_a.write_bytes(b"\x00" * 100)
    wav_b = tmp_path / "rec_b.wav"
    wav_b.write_bytes(b"\x00" * 100)
    att_a = tmp_path / "att_a.pdf"
    att_a.write_bytes(b"\x00" * 100)
    att_b = tmp_path / "att_b.pdf"
    att_b.write_bytes(b"\x00" * 100)

    await _insert_recording(
        migrated_engine,
        rec_id="r_mix_a",
        meeting_id="m_mix_a",
        stream="me",
        file_path=wav_a,
        age_days=35,
    )
    await _insert_recording(
        migrated_engine,
        rec_id="r_mix_b",
        meeting_id="m_mix_b",
        stream="me",
        file_path=wav_b,
        age_days=35,
    )
    await _insert_attachment(
        migrated_engine,
        att_id="a_mix_a",
        meeting_id="m_mix_a",
        user_id="u_mix",
        file_path=att_a,
        age_days=35,
    )
    await _insert_attachment(
        migrated_engine,
        att_id="a_mix_b",
        meeting_id="m_mix_b",
        user_id="u_mix",
        file_path=att_b,
        age_days=35,
    )

    now = datetime.now(UTC)
    count = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        attachments_dir=tmp_path,
        session_factory=Session,
    )
    assert count == 4
    for f in (wav_a, wav_b, att_a, att_b):
        assert not f.exists()


@pytest.mark.asyncio
async def test_cleanup_attachment_idempotent_second_call_returns_zero(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Idempotency: running cleanup twice with the same `now` is a no-op the
    second time around for attachments too.
    """
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_idem_a", meeting_id="m_idem_a")
    att = tmp_path / "idem_att.pdf"
    att.write_bytes(b"\x00" * 100)
    await _insert_attachment(
        migrated_engine,
        att_id="a_idem",
        meeting_id="m_idem_a",
        user_id="u_idem_a",
        file_path=att,
        age_days=45,
    )

    now = datetime.now(UTC)
    first = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        attachments_dir=tmp_path,
        session_factory=Session,
    )
    second = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        attachments_dir=tmp_path,
        session_factory=Session,
    )
    assert first == 1
    assert second == 0
    assert not att.exists()


@pytest.mark.asyncio
async def test_cleanup_unlink_failure_does_not_abort_transaction(
    migrated_engine: AsyncEngine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One attachment unlink raising PermissionError must not stop the loop —
    the other row should still get its `deleted_at` stamped.
    """
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_perm", meeting_id="m_perm")
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"\x00" * 100)
    good = tmp_path / "good.pdf"
    good.write_bytes(b"\x00" * 100)
    await _insert_attachment(
        migrated_engine,
        att_id="a_bad",
        meeting_id="m_perm",
        user_id="u_perm",
        file_path=bad,
        age_days=45,
    )
    await _insert_attachment(
        migrated_engine,
        att_id="a_good",
        meeting_id="m_perm",
        user_id="u_perm",
        file_path=good,
        age_days=45,
    )

    real_unlink = Path.unlink

    def _selective_unlink(self, *args, **kwargs):
        if self == bad:
            raise PermissionError("simulated FS denial")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _selective_unlink)

    now = datetime.now(UTC)
    count = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        attachments_dir=tmp_path,
        session_factory=Session,
    )
    assert count == 1
    assert bad.exists()  # still on disk because unlink raised
    assert not good.exists()

    async with migrated_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT id, deleted_at FROM meeting_attachment "
                    "WHERE id IN ('a_bad', 'a_good') ORDER BY id"
                )
            )
        ).all()
    by_id = {r.id: r.deleted_at for r in rows}
    assert by_id["a_bad"] is None, "bad row deleted_at must remain NULL"
    assert by_id["a_good"] is not None, "good row deleted_at must be stamped"


# ─── Slice 24: staged attachment sweep ──────────────────────────────


async def _insert_staged_attachment(
    engine: AsyncEngine,
    *,
    att_id: str,
    user_id: str,
    file_path: Path,
    age_hours: float,
    bytes_: int = 100,
) -> None:
    """Insert a staged (orphan, meeting_id NULL) attachment row.

    Slice-24 retention sweep targets these specifically — they have no
    parent meeting row, so the legacy 30-day attached sweep would never
    touch them.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO meeting_attachment (
                    id, meeting_id, user_id, file_path, kind, original_name, bytes,
                    uploaded_at
                )
                VALUES (:aid, NULL, :uid, :fp, 'pdf', 'x.pdf', :bytes,
                    now() - (:age || ' hours')::interval)
                """
            ),
            {
                "aid": att_id,
                "uid": user_id,
                "fp": str(file_path),
                "bytes": bytes_,
                "age": str(age_hours),
            },
        )


@pytest.mark.asyncio
async def test_cleanup_removes_staged_older_than_ttl(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Slice-24 D7: staged row older than STAGED_ATTACHMENT_TTL_HOURS is hard-deleted."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_stg", meeting_id="m_stg_ignored")

    old = tmp_path / "stg_old.pdf"
    old.write_bytes(b"\x00" * 100)
    await _insert_staged_attachment(
        migrated_engine,
        att_id="a_stg_old",
        user_id="u_stg",
        file_path=old,
        age_hours=25,  # > 24h default
    )

    now = datetime.now(UTC)
    count = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        attachments_dir=tmp_path,
        session_factory=Session,
        staged_ttl_hours=24,
    )
    assert count == 1, f"expected 1 staged sweep; got {count}"
    assert not old.exists(), "Old staged file MUST be unlinked"

    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(text("SELECT id FROM meeting_attachment WHERE id = 'a_stg_old'"))
        ).first()
    assert row is None, "Old staged row MUST be hard-deleted (not soft-deleted)"


@pytest.mark.asyncio
async def test_cleanup_keeps_staged_younger_than_ttl(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """A staged row younger than the TTL stays untouched."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_stg_y", meeting_id="m_stg_y_ignored")

    fresh = tmp_path / "stg_fresh.pdf"
    fresh.write_bytes(b"\x00" * 100)
    await _insert_staged_attachment(
        migrated_engine,
        att_id="a_stg_fresh",
        user_id="u_stg_y",
        file_path=fresh,
        age_hours=1,
    )

    now = datetime.now(UTC)
    count = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        attachments_dir=tmp_path,
        session_factory=Session,
        staged_ttl_hours=24,
    )
    assert count == 0, f"fresh staged row MUST not be swept; got {count}"
    assert fresh.exists()

    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT id, meeting_id, deleted_at "
                    "FROM meeting_attachment WHERE id = 'a_stg_fresh'"
                )
            )
        ).first()
    assert row is not None
    assert row.meeting_id is None
    assert row.deleted_at is None


@pytest.mark.asyncio
async def test_cleanup_staged_sweep_unlink_failure_logs_and_continues(
    migrated_engine: AsyncEngine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Best-effort unlink: a missing file does NOT prevent the row from being deleted."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)

    await _seed(migrated_engine, user_id="u_stg_m", meeting_id="m_stg_m_ignored")

    missing = tmp_path / "stg_missing.pdf"  # never written to disk
    await _insert_staged_attachment(
        migrated_engine,
        att_id="a_stg_missing",
        user_id="u_stg_m",
        file_path=missing,
        age_hours=48,
    )

    now = datetime.now(UTC)
    count = await cleanup(
        now=now,
        retention_days=30,
        recordings_dir=tmp_path,
        attachments_dir=tmp_path,
        session_factory=Session,
        staged_ttl_hours=24,
    )
    assert count == 1
    async with migrated_engine.connect() as conn:
        row = (
            await conn.execute(text("SELECT id FROM meeting_attachment WHERE id = 'a_stg_missing'"))
        ).first()
    assert row is None
