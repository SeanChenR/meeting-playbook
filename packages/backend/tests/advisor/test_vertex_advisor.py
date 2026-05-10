"""VertexFlashAdvisor tests — mock the google-genai SDK so no real API call.

Per slice-08 spec `TacticalAdvisor module exposes a streaming advise() coroutine`:
- per-SDK-chunk yield (transparent forwarding)
- 15-second outer asyncio.timeout

The advisor takes a `client_factory` so tests can inject a mock client without
touching `google.genai.Client`.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from meeting_playbook.advisor.vertex_advisor import VertexFlashAdvisor


def _playbook(**fields: str) -> Any:
    defaults = {
        "free_form_markdown": "test free-form",
        "objective": "test objective",
        "counterparty_profile": "",
        "anticipated_topics": "",
        "anticipated_objections": "",
        "talking_points": "",
        "red_lines": "",
    }
    defaults.update(fields)
    return SimpleNamespace(**defaults)


def _chunk(speaker: str, text: str) -> Any:
    return SimpleNamespace(
        speaker=speaker,
        text=text,
        started_at=datetime.now(UTC),
    )


class _MockSdkChunk:
    """Mimics google-genai stream chunk (only `.text` accessed)."""

    def __init__(self, text: str) -> None:
        self.text = text


def _build_mock_client(stream_factory):
    """Build a MagicMock that returns `stream_factory(**kwargs)` from
    `client.aio.models.generate_content_stream(...)`. The stream_factory must
    return an async iterator (or async generator object)."""
    client = MagicMock()
    client.aio.models.generate_content_stream = lambda **kw: stream_factory(**kw)
    return client


@pytest.mark.asyncio
async def test_advise_yields_text_per_sdk_chunk():
    """Slice-08 spec scenario: yield exactly one string per SDK chunk."""

    async def _stream(**_kw):
        for t in ["建議一", "建議二", "建議三"]:
            yield _MockSdkChunk(t)

    client = _build_mock_client(_stream)
    advisor = VertexFlashAdvisor(client_factory=lambda: client, model_id="gemini-2.0-flash-001")

    out = [
        token
        async for token in advisor.advise(
            meeting_id="m_x",
            recent_chunks=[_chunk("me", "hi")],
            playbook=_playbook(),
            me_display_name="Sean",
            counterparty_display_name="林經理",
            user_question=None,
            locale="zh-TW",
        )
    ]
    assert out == ["建議一", "建議二", "建議三"]


@pytest.mark.asyncio
async def test_advise_skips_empty_text_chunks():
    """Defensive: SDK occasionally emits chunks with empty `.text`. Skip them."""

    async def _stream(**_kw):
        for t in ["a", "", "b", None, "c"]:
            yield _MockSdkChunk(t)  # type: ignore[arg-type]

    client = _build_mock_client(_stream)
    advisor = VertexFlashAdvisor(client_factory=lambda: client, model_id="gemini-2.0-flash-001")

    out = [
        token
        async for token in advisor.advise(
            meeting_id="m_x",
            recent_chunks=[],
            playbook=_playbook(),
            me_display_name="Sean",
            counterparty_display_name="林經理",
            user_question=None,
            locale="zh-TW",
        )
    ]
    assert out == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_advise_raises_timeout_after_15s():
    """Slice-08 spec: outer 15s asyncio.timeout raises TimeoutError on stalled stream."""

    async def _slow_stream(**_kw):
        await asyncio.sleep(20.0)
        yield _MockSdkChunk("never")  # pragma: no cover

    client = _build_mock_client(_slow_stream)
    advisor = VertexFlashAdvisor(client_factory=lambda: client, model_id="gemini-2.0-flash-001")

    started = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        async for _ in advisor.advise(
            meeting_id="m_x",
            recent_chunks=[],
            playbook=_playbook(),
            me_display_name="Sean",
            counterparty_display_name="林經理",
            user_question=None,
            locale="zh-TW",
        ):
            pass
    elapsed = time.monotonic() - started
    # Spec: between 15.0 and 16.0 seconds. Allow generous upper bound for CI noise.
    assert 14.5 <= elapsed <= 17.0, f"timeout fired at {elapsed:.2f}s, expected ~15s"


@pytest.mark.asyncio
async def test_advise_passes_system_instruction_and_user_message_to_sdk():
    """Verify the prompt assembly is wired into the SDK call config."""
    captured: dict[str, Any] = {}

    async def _stream(**kw):
        captured.update(kw)
        if False:
            yield  # never yields; we only inspect kwargs

    client = _build_mock_client(_stream)
    advisor = VertexFlashAdvisor(client_factory=lambda: client, model_id="gemini-2.0-flash-001")

    _ = [
        t
        async for t in advisor.advise(
            meeting_id="m_x",
            recent_chunks=[_chunk("me", "hello")],
            playbook=_playbook(objective="拿下 Q3"),
            me_display_name="Sean",
            counterparty_display_name="林經理",
            user_question=None,
            locale="zh-TW",
        )
    ]

    # Model id forwarded
    assert captured["model"] == "gemini-2.0-flash-001"
    # User message contains assembled context
    contents = captured["contents"]
    assert "拿下 Q3" in contents
    assert "Sean：hello" in contents
    # Config includes system_instruction + generation params
    config = captured["config"]
    # config can be dict or GenerateContentConfig — inspect via getattr fallback
    sys_inst = getattr(config, "system_instruction", None) or config.get("system_instruction")
    assert "請用繁體中文" in sys_inst
    temperature = getattr(config, "temperature", None) or config.get("temperature")
    assert temperature == 0.4
    max_out = getattr(config, "max_output_tokens", None) or config.get("max_output_tokens")
    assert max_out == 400
