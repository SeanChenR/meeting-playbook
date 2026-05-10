"""Slice-10 runtime — in-flight registry + background task tests.

Per spec meeting-summary ADDED requirement scenarios for
`spawn_summary_task` / `is_pending`.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from meeting_playbook.summarization import runtime
from meeting_playbook.summarization.base import SummaryFormatError

_VALID_MD = "## 重點討論\n- a\n## 決議\n(無)\n## Action items\n- [TBD] x\n## 待解決問題\n(無)\n"


async def _seed_meeting(db_session, *, mid: str = "m_rt") -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ('u_rt', 'Sean', 'sean@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    await db_session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, 'u_rt', 'T', 'C', 'M')
            """
        ),
        {"mid": mid},
    )
    await db_session.commit()


class _FakeSummarizer:
    """Test summarizer that returns / sleeps / raises per init args."""

    def __init__(
        self,
        *,
        text_to_return: str | None = None,
        sleep_seconds: float = 0.0,
        raises: BaseException | None = None,
    ):
        self._text = text_to_return
        self._sleep = sleep_seconds
        self._raises = raises
        self.calls = 0

    async def summarize(self, meeting_id: str) -> str:
        self.calls += 1
        if self._sleep > 0:
            await asyncio.sleep(self._sleep)
        if self._raises is not None:
            raise self._raises
        assert self._text is not None
        return self._text


@pytest.fixture(autouse=True)
def _reset_inflight():
    """Reset the global registry between tests so they're isolated."""
    runtime._inflight.clear()
    yield
    runtime._inflight.clear()


@pytest.mark.asyncio
async def test_spawn_returns_true_first_time_then_false_while_pending(db_session, migrated_engine):
    """Slice-10: concurrent spawn calls — first wins, second returns False."""
    await _seed_meeting(db_session, mid="m_concurrent")
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    summarizer = _FakeSummarizer(text_to_return=_VALID_MD, sleep_seconds=0.5)

    first = await runtime.spawn_summary_task(
        "m_concurrent", summarizer=summarizer, session_factory=Session
    )
    second = await runtime.spawn_summary_task(
        "m_concurrent", summarizer=summarizer, session_factory=Session
    )

    assert first is True
    assert second is False
    assert runtime.is_pending("m_concurrent") is True

    # Wait for the in-flight task to complete so the test cleans up.
    task = runtime._inflight["m_concurrent"]
    await task
    assert runtime.is_pending("m_concurrent") is False


@pytest.mark.asyncio
async def test_successful_run_upserts_then_pops_registry(db_session, migrated_engine):
    """Slice-10: success path writes a summary row + clears the registry."""
    await _seed_meeting(db_session, mid="m_success")
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    summarizer = _FakeSummarizer(text_to_return=_VALID_MD)

    await runtime.spawn_summary_task("m_success", summarizer=summarizer, session_factory=Session)
    await runtime._inflight["m_success"]

    rows = await db_session.execute(
        text("SELECT COUNT(*) FROM summary WHERE meeting_id = 'm_success'")
    )
    assert rows.scalar_one() == 1
    assert runtime.is_pending("m_success") is False


@pytest.mark.asyncio
async def test_failed_run_skips_upsert_but_pops_registry(db_session, migrated_engine):
    """Slice-10: TimeoutError → no row, registry popped, no exception escapes."""
    await _seed_meeting(db_session, mid="m_timeout")
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    summarizer = _FakeSummarizer(raises=TimeoutError("vertex hang"))

    await runtime.spawn_summary_task("m_timeout", summarizer=summarizer, session_factory=Session)
    await runtime._inflight["m_timeout"]  # await without raising

    rows = await db_session.execute(
        text("SELECT COUNT(*) FROM summary WHERE meeting_id = 'm_timeout'")
    )
    assert rows.scalar_one() == 0
    assert runtime.is_pending("m_timeout") is False


@pytest.mark.asyncio
async def test_summary_format_error_treated_as_failure(db_session, migrated_engine):
    """Slice-10: SummaryFormatError → no row, registry popped (same as timeout)."""
    await _seed_meeting(db_session, mid="m_fmt")
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    summarizer = _FakeSummarizer(raises=SummaryFormatError("missing heading"))

    await runtime.spawn_summary_task("m_fmt", summarizer=summarizer, session_factory=Session)
    await runtime._inflight["m_fmt"]

    rows = await db_session.execute(text("SELECT COUNT(*) FROM summary WHERE meeting_id = 'm_fmt'"))
    assert rows.scalar_one() == 0
    assert runtime.is_pending("m_fmt") is False


@pytest.mark.asyncio
async def test_generic_exception_treated_as_failure(db_session, migrated_engine):
    """Slice-10: any other Exception (e.g. quota / auth) → no row, registry popped."""
    await _seed_meeting(db_session, mid="m_quota")
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    summarizer = _FakeSummarizer(raises=RuntimeError("vertex 429 quota"))

    await runtime.spawn_summary_task("m_quota", summarizer=summarizer, session_factory=Session)
    await runtime._inflight["m_quota"]

    rows = await db_session.execute(
        text("SELECT COUNT(*) FROM summary WHERE meeting_id = 'm_quota'")
    )
    assert rows.scalar_one() == 0
    assert runtime.is_pending("m_quota") is False


@pytest.mark.asyncio
async def test_is_pending_returns_false_when_no_entry(db_session):
    """Slice-10: is_pending on never-spawned meeting returns False."""
    assert runtime.is_pending("m_never") is False
