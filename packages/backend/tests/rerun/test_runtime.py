"""Re-run runtime tests — slice-11 task 5.1.

Per spec asr-provider-selection ADDED requirement
"POST /api/meetings/{id}/rerun_asr triggers atomic transcript replacement"
+ design Decision 3 scenarios:

  (a) Concurrent spawn: first call returns True, second returns False
      while task is still in-flight.
  (b) Successful run replaces transcript_chunk rows atomically; new row
      count equals fake-provider chunk count; registry is cleared.
  (c) Inference exception: existing rows preserved (count unchanged); no
      new rows inserted; registry cleared.
  (d) get_status returns idle / pending shapes per spec.
"""

from __future__ import annotations

import asyncio
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.rerun import runtime as rerun_runtime

# ─── Fixtures + helpers ─────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_registries():
    """Make sure no leftover task / progress from a previous test pollutes."""
    rerun_runtime._inflight.clear()
    rerun_runtime._progress.clear()
    yield
    rerun_runtime._inflight.clear()
    rerun_runtime._progress.clear()


def _write_silent_wav(path: Path, *, duration_s: float, sample_rate: int = 16000) -> None:
    """Write a mono 16-bit PCM wav of given duration filled with silence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(duration_s * sample_rate)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


class _FakeProvider:
    """Fake ASRProvider that returns a fixed transcript per call."""

    def __init__(self, *, name: str = "fake", text: str = "hello") -> None:
        self._name = name
        self._text = text
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def warmup(self) -> None:
        return None

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        del audio_bytes, sample_rate_hz, language_hint
        self.calls += 1
        now = datetime.now(UTC)
        return TranscriptChunk(
            text=self._text,
            started_at=now,
            ended_at=now + timedelta(milliseconds=100),
            asr_provider_used=self._name,
            confidence=0.9,
        )


class _RaisingProvider:
    """Provider that always raises (to simulate inference failure)."""

    name: str = "raising"

    async def warmup(self) -> None:
        return None

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        del audio_bytes, sample_rate_hz, language_hint
        raise RuntimeError("simulated inference failure")


async def _seed_meeting_with_recordings(
    engine: AsyncEngine,
    *,
    meeting_id: str,
    user_id: str,
    me_wav: Path,
    cp_wav: Path,
    asr_provider: str = "whisper",
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
                    id, user_id, title, counterparty_display_name,
                    me_display_name, status, asr_provider
                )
                VALUES (:mid, :uid, 'T', 'C', 'M', 'completed', :provider)
                """
            ),
            {"mid": meeting_id, "uid": user_id, "provider": asr_provider},
        )
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes,
                    created_at, started_at
                )
                VALUES ('r_me_' || :mid, :mid, 'me', :fp, 100, now(), now())
                """
            ),
            {"mid": meeting_id, "fp": str(me_wav)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO recording (
                    id, meeting_id, stream, file_path, bytes,
                    created_at, started_at
                )
                VALUES ('r_cp_' || :mid, :mid, 'counterparty', :fp, 100, now(), now())
                """
            ),
            {"mid": meeting_id, "fp": str(cp_wav)},
        )


async def _count_chunks(engine: AsyncEngine, meeting_id: str) -> int:
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT COUNT(*) FROM transcript_chunk WHERE meeting_id = :mid"),
                {"mid": meeting_id},
            )
        ).scalar_one()


async def _insert_existing_chunk(
    engine: AsyncEngine, *, meeting_id: str, chunk_id: str = "tc_existing"
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO transcript_chunk (
                    id, meeting_id, speaker, text, started_at, ended_at,
                    asr_provider_used, confidence, created_at
                )
                VALUES (:tid, :mid, 'me', 'old text', now() - interval '1 minute',
                        now() - interval '50 seconds', 'whisper', 0.9, now())
                """
            ),
            {"tid": chunk_id, "mid": meeting_id},
        )


# ─── Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_spawn_first_true_second_false(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Spec scenario (a): two concurrent spawns — first wins, second sees in-flight."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    me_wav = tmp_path / "me.wav"
    cp_wav = tmp_path / "cp.wav"
    # Long enough that the first task is still inferring when the second
    # spawn arrives. _FakeProvider.transcribe_chunk returns instantly, but
    # we make the chunks add up so the await chain takes >0 ms.
    _write_silent_wav(me_wav, duration_s=15)
    _write_silent_wav(cp_wav, duration_s=15)

    await _seed_meeting_with_recordings(
        migrated_engine,
        meeting_id="m_dup",
        user_id="u_dup",
        me_wav=me_wav,
        cp_wav=cp_wav,
    )

    class _SlowProvider(_FakeProvider):
        async def transcribe_chunk(self, *a, **kw):
            await asyncio.sleep(0.05)
            return await super().transcribe_chunk(*a, **kw)

    providers = {"me": _SlowProvider(), "counterparty": _SlowProvider()}

    first = await rerun_runtime.spawn_rerun_task(
        "m_dup", providers=providers, session_factory=Session
    )
    second = await rerun_runtime.spawn_rerun_task(
        "m_dup", providers=providers, session_factory=Session
    )

    assert first is True, "first spawn must win"
    assert second is False, "second spawn must see in-flight task"
    assert rerun_runtime.is_pending("m_dup")

    await rerun_runtime._inflight["m_dup"]


@pytest.mark.asyncio
async def test_successful_run_replaces_existing_chunks(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Spec scenario (b): success path replaces transcript_chunk atomically."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    me_wav = tmp_path / "me.wav"
    cp_wav = tmp_path / "cp.wav"
    # 25s wav at 10s/chunk → 3 chunks per stream → 6 total.
    _write_silent_wav(me_wav, duration_s=25)
    _write_silent_wav(cp_wav, duration_s=25)

    await _seed_meeting_with_recordings(
        migrated_engine,
        meeting_id="m_ok",
        user_id="u_ok",
        me_wav=me_wav,
        cp_wav=cp_wav,
    )
    await _insert_existing_chunk(migrated_engine, meeting_id="m_ok")
    pre_count = await _count_chunks(migrated_engine, "m_ok")
    assert pre_count == 1, "seed should have 1 existing chunk"

    me_provider = _FakeProvider(name="qwen3", text="me transcribed")
    cp_provider = _FakeProvider(name="qwen3", text="cp transcribed")

    spawned = await rerun_runtime.spawn_rerun_task(
        "m_ok",
        providers={"me": me_provider, "counterparty": cp_provider},
        session_factory=Session,
    )
    assert spawned is True
    await rerun_runtime._inflight["m_ok"]

    post_count = await _count_chunks(migrated_engine, "m_ok")
    # 25s -> 3 chunks per stream, 2 streams -> 6 total.
    assert post_count == 6, f"expected 6 new chunks (existing wiped); got {post_count}"
    assert me_provider.calls == 3
    assert cp_provider.calls == 3
    # Registry is cleared after the task completes.
    assert "m_ok" not in rerun_runtime._inflight
    assert "m_ok" not in rerun_runtime._progress
    assert not rerun_runtime.is_pending("m_ok")


@pytest.mark.asyncio
async def test_silent_chunks_with_empty_transcript_are_skipped(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Slice-11 fix: rows whose transcribe returns empty/whitespace text
    are filtered before write — re-run wouldn't otherwise know to skip
    silence (Whisper has VAD inside the model; Qwen3 just returns "").
    """
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    me_wav = tmp_path / "me.wav"
    cp_wav = tmp_path / "cp.wav"
    # 25s wav -> 3 chunks per stream -> 6 attempted.
    _write_silent_wav(me_wav, duration_s=25)
    _write_silent_wav(cp_wav, duration_s=25)

    await _seed_meeting_with_recordings(
        migrated_engine,
        meeting_id="m_skip",
        user_id="u_skip",
        me_wav=me_wav,
        cp_wav=cp_wav,
    )

    class _OddSilentProvider(_FakeProvider):
        """Returns text only on EVEN call indices; empty for odd."""

        def __init__(self) -> None:
            super().__init__(name="qwen3", text="hello")

        async def transcribe_chunk(self, *args, **kwargs):
            self.calls += 1
            now = datetime.now(UTC)
            text = "spoken" if self.calls % 2 == 0 else "  "  # whitespace = silence-equivalent
            return TranscriptChunk(
                text=text,
                started_at=now,
                ended_at=now + timedelta(milliseconds=10),
                asr_provider_used=self._name,
                confidence=0.9,
            )

    me_provider = _OddSilentProvider()
    cp_provider = _OddSilentProvider()

    await rerun_runtime.spawn_rerun_task(
        "m_skip",
        providers={"me": me_provider, "counterparty": cp_provider},
        session_factory=Session,
    )
    await rerun_runtime._inflight["m_skip"]

    # Each provider gets 3 calls; only EVEN-indexed calls return text.
    # me: calls 1,2,3 → only call 2 keeps a row → 1 kept.
    # cp: same pattern → 1 kept. Total = 2.
    post_count = await _count_chunks(migrated_engine, "m_skip")
    assert post_count == 2, f"expected 2 non-silent rows; got {post_count}"
    # progress.processed counts ALL attempts, not just kept rows — so the
    # polling counter doesn't appear to stall on silence-heavy meetings.
    assert me_provider.calls == 3
    assert cp_provider.calls == 3


@pytest.mark.asyncio
async def test_inference_failure_preserves_existing_rows(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Spec scenario (c): any chunk raise → existing chunks preserved, no partial state."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    me_wav = tmp_path / "me.wav"
    cp_wav = tmp_path / "cp.wav"
    _write_silent_wav(me_wav, duration_s=15)
    _write_silent_wav(cp_wav, duration_s=15)

    await _seed_meeting_with_recordings(
        migrated_engine,
        meeting_id="m_fail",
        user_id="u_fail",
        me_wav=me_wav,
        cp_wav=cp_wav,
    )
    await _insert_existing_chunk(migrated_engine, meeting_id="m_fail", chunk_id="tc_existing_fail")
    pre_count = await _count_chunks(migrated_engine, "m_fail")
    assert pre_count == 1

    spawned = await rerun_runtime.spawn_rerun_task(
        "m_fail",
        providers={"me": _RaisingProvider(), "counterparty": _RaisingProvider()},
        session_factory=Session,
    )
    assert spawned is True
    await rerun_runtime._inflight["m_fail"]  # exception is logged + swallowed

    post_count = await _count_chunks(migrated_engine, "m_fail")
    assert post_count == 1, (
        "existing transcript_chunk row MUST survive a failed re-run; "
        f"got {post_count} (delta={post_count - pre_count})"
    )
    # Registry cleared even on failure.
    assert "m_fail" not in rerun_runtime._inflight
    assert "m_fail" not in rerun_runtime._progress


def test_get_status_returns_idle_when_no_task() -> None:
    """Spec scenario (d) — idle shape when no task ever spawned."""
    snapshot = rerun_runtime.get_status("m_never_spawned")
    assert snapshot == {"status": "idle", "chunks_processed": 0, "chunks_total": 0}


@pytest.mark.asyncio
async def test_get_status_returns_pending_with_progress_during_run(
    migrated_engine: AsyncEngine, tmp_path: Path
) -> None:
    """Spec scenario (d) — pending shape with real counters mid-run."""
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    me_wav = tmp_path / "me.wav"
    cp_wav = tmp_path / "cp.wav"
    _write_silent_wav(me_wav, duration_s=25)  # 3 chunks
    _write_silent_wav(cp_wav, duration_s=25)  # 3 chunks → total 6

    await _seed_meeting_with_recordings(
        migrated_engine,
        meeting_id="m_prog",
        user_id="u_prog",
        me_wav=me_wav,
        cp_wav=cp_wav,
    )

    inflight_event = asyncio.Event()
    can_finish_event = asyncio.Event()

    class _GatedProvider(_FakeProvider):
        async def transcribe_chunk(self, *a, **kw):
            inflight_event.set()
            await can_finish_event.wait()
            return await super().transcribe_chunk(*a, **kw)

    spawned = await rerun_runtime.spawn_rerun_task(
        "m_prog",
        providers={"me": _GatedProvider(), "counterparty": _GatedProvider()},
        session_factory=Session,
    )
    assert spawned is True

    # Wait for the task to enter its first transcribe_chunk so total has
    # been set by the pre-pass.
    await asyncio.wait_for(inflight_event.wait(), timeout=2.0)

    snapshot = rerun_runtime.get_status("m_prog")
    assert snapshot["status"] == "pending"
    assert snapshot["chunks_total"] == 6, f"expected 6 total chunks; got {snapshot}"
    assert snapshot["chunks_processed"] >= 0  # may be 0 if we caught it before processed += 1

    # Let the task finish.
    can_finish_event.set()
    await rerun_runtime._inflight["m_prog"]

    final = rerun_runtime.get_status("m_prog")
    assert final == {"status": "idle", "chunks_processed": 0, "chunks_total": 0}
