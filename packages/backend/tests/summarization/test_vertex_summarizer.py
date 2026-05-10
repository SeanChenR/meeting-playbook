"""VertexProSummarizer — slice-10 SDK + heading-validation tests.

Per spec meeting-summary ADDED requirement scenarios for `summarize`:
returns markdown when 4 headings present, raises SummaryFormatError on
missing / out-of-order heading, raises asyncio.TimeoutError after 90s.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from meeting_playbook.summarization.base import SummaryFormatError
from meeting_playbook.summarization.vertex_summarizer import VertexProSummarizer

_VALID_MD = "## 重點討論\n- a\n## 決議\n(無)\n## Action items\n- [TBD] x\n## 待解決問題\n(無)\n"


async def _seed_meeting(db_session, *, mid: str = "m_v") -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO "user" (id, name, email, "emailVerified")
            VALUES ('u_v', 'Sean', 'sean@example.com', true)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    await db_session.execute(
        text(
            """
            INSERT INTO meeting (id, user_id, title, counterparty_display_name, me_display_name)
            VALUES (:mid, 'u_v', 'T', '林經理', 'Sean')
            """
        ),
        {"mid": mid},
    )
    await db_session.commit()


def _build_mock_client(text_to_return: str | None = None, sleep_seconds: float = 0.0):
    """Mock that mimics google-genai async API: client.aio.models.generate_content
    is an awaitable that returns an object with `.text`."""
    client = MagicMock()

    async def _generate_content(**_kw):
        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)
        return SimpleNamespace(text=text_to_return)

    client.aio.models.generate_content = _generate_content
    return client


def _make_summarizer(
    migrated_engine,
    *,
    text_to_return: str | None = None,
    sleep_seconds: float = 0.0,
) -> VertexProSummarizer:
    """Build a VertexProSummarizer pointed at the test AsyncEngine.

    Slice-10: summarizer opens its own AsyncSession per call (separate
    from the request-scoped session). We hand it a fresh
    `async_sessionmaker` bound to the test engine so its internal fetches
    see the seeded data.
    """
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    return VertexProSummarizer(
        client_factory=lambda: _build_mock_client(text_to_return, sleep_seconds),
        model_id="gemini-2.5-pro",
        session_factory=Session,
        locale="zh-TW",
    )


@pytest.mark.asyncio
async def test_summarize_returns_markdown_when_4_headings_present_in_order(
    db_session, migrated_engine
):
    """Slice-10: valid markdown with 4 headings in order → returned verbatim."""
    await _seed_meeting(db_session, mid="m_ok")
    summarizer = _make_summarizer(migrated_engine, text_to_return=_VALID_MD)
    out = await summarizer.summarize("m_ok")
    assert out == _VALID_MD


@pytest.mark.asyncio
async def test_summarize_raises_summary_format_error_when_heading_missing(
    db_session, migrated_engine
):
    """Slice-10: missing `## 決議` → SummaryFormatError."""
    await _seed_meeting(db_session, mid="m_miss")
    bad = (
        "## 重點討論\n- a\n"
        # `## 決議` missing
        "## Action items\n- [TBD] x\n"
        "## 待解決問題\n(無)\n"
    )
    summarizer = _make_summarizer(migrated_engine, text_to_return=bad)
    with pytest.raises(SummaryFormatError, match="決議"):
        await summarizer.summarize("m_miss")


@pytest.mark.asyncio
async def test_summarize_raises_summary_format_error_when_headings_out_of_order(
    db_session, migrated_engine
):
    """Slice-10: `## Action items` before `## 決議` → SummaryFormatError."""
    await _seed_meeting(db_session, mid="m_ord")
    bad = (
        "## 重點討論\n- a\n"
        "## Action items\n- [TBD] x\n"  # out of order
        "## 決議\n(無)\n"
        "## 待解決問題\n(無)\n"
    )
    summarizer = _make_summarizer(migrated_engine, text_to_return=bad)
    with pytest.raises(SummaryFormatError, match="out of order"):
        await summarizer.summarize("m_ord")


@pytest.mark.asyncio
async def test_summarize_raises_timeout_after_90s(db_session, migrated_engine):
    """Slice-10: 90s outer asyncio.timeout caps the Vertex call.

    We DON'T actually wait 90s — patch _STREAM_TIMEOUT_S to 0.5s and use
    a 5s sleep mock so the assertion runs in <1s wall-clock.
    """
    from meeting_playbook.summarization import vertex_summarizer as vs

    await _seed_meeting(db_session, mid="m_to")
    summarizer = _make_summarizer(migrated_engine, text_to_return=_VALID_MD, sleep_seconds=5.0)

    original = vs._STREAM_TIMEOUT_S
    vs._STREAM_TIMEOUT_S = 0.5
    try:
        started = time.monotonic()
        with pytest.raises(asyncio.TimeoutError):
            await summarizer.summarize("m_to")
        elapsed = time.monotonic() - started
        assert 0.4 <= elapsed <= 1.5, f"timeout fired at {elapsed:.2f}s, expected ~0.5s"
    finally:
        vs._STREAM_TIMEOUT_S = original


@pytest.mark.asyncio
async def test_summarize_raises_summary_format_error_when_meeting_missing(
    db_session, migrated_engine
):
    """Slice-10: meeting deleted before summarize() runs → SummaryFormatError."""
    summarizer = _make_summarizer(migrated_engine, text_to_return=_VALID_MD)
    with pytest.raises(SummaryFormatError, match="not found"):
        await summarizer.summarize("m_does_not_exist")


@pytest.mark.asyncio
async def test_summarize_calls_sdk_with_assembled_prompt(db_session, migrated_engine):
    """Slice-10: prompt assembly + locale are wired into the SDK call config."""
    captured: dict[str, Any] = {}

    async def _capture(**kw):
        captured.update(kw)
        return SimpleNamespace(text=_VALID_MD)

    client = MagicMock()
    client.aio.models.generate_content = _capture

    await _seed_meeting(db_session, mid="m_cap")
    Session = async_sessionmaker(migrated_engine, expire_on_commit=False)
    summarizer = VertexProSummarizer(
        client_factory=lambda: client,
        model_id="gemini-2.5-pro",
        session_factory=Session,
        locale="zh-TW",
    )
    await summarizer.summarize("m_cap")

    assert captured["model"] == "gemini-2.5-pro"
    contents = captured["contents"]
    # Meeting metadata renders the title.
    assert "T" in contents  # meeting title
    # 4 user-message section headings present.
    assert "## 會議基本資料" in contents
    assert "## Playbook" in contents
    assert "## 整場 Transcript" in contents
    assert "## In-meeting Advisor 對話" in contents
    # System instruction (config) contains the 4 required output headings.
    config = captured["config"]
    sys_inst = getattr(config, "system_instruction", None) or config.get("system_instruction")
    for required in ("## 重點討論", "## 決議", "## Action items", "## 待解決問題"):
        assert required in sys_inst
