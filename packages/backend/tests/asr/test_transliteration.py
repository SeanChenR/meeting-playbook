"""Simplified → Traditional Chinese transliteration tests (slice-11 fix).

Two layers covered here:
  1. `to_traditional_chinese` itself — character + Taiwan-phrase substitution
  2. `_TraditionalChineseProvider` decorator — wraps any ASRProvider and
     post-processes its TranscriptChunk.text on the fly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from meeting_playbook.asr.base import TranscriptChunk
from meeting_playbook.asr.factory import _TraditionalChineseProvider
from meeting_playbook.asr.transliteration import to_traditional_chinese

# ─── to_traditional_chinese ────────────────────────────────────────


def test_simple_character_conversion() -> None:
    """Basic 简 → 簡 character-level swap."""
    assert to_traditional_chinese("简体中文") == "簡體中文"


def test_taiwan_phrase_substitution() -> None:
    """`s2twp` config swaps mainland phrases for Taiwan equivalents."""
    # 軟件 (mainland) → 軟體 (Taiwan)
    assert "軟體" in to_traditional_chinese("软件开发")
    # 视频 (mainland) → 視訊 (Taiwan tech term, e.g. 視訊會議 / 視訊通話).
    # OpenCC `s2twp` picks 視訊 over 影片 for the meeting-context phrase
    # — both are common in Taiwan, but 視訊 is the IT/business default.
    assert "視訊" in to_traditional_chinese("视频会议")


def test_already_traditional_passes_through() -> None:
    """Idempotent on Traditional input."""
    src = "繁體中文"
    assert to_traditional_chinese(src) == src


def test_empty_input_returns_unchanged() -> None:
    assert to_traditional_chinese("") == ""
    assert to_traditional_chinese("   ") == "   "


def test_non_chinese_passes_through() -> None:
    assert to_traditional_chinese("hello world") == "hello world"
    # Mixed: English untouched, Chinese converted
    out = to_traditional_chinese("hello 简体 world")
    assert "hello" in out and "world" in out and "簡體" in out


# ─── _TraditionalChineseProvider decorator ─────────────────────────


class _StubProvider:
    """Returns a fixed TranscriptChunk per call. Mimics the ASRProvider
    Protocol shape without doing any real ASR."""

    name: str = "stub"

    def __init__(self, text: str = "简体测试") -> None:
        self._text = text
        self.warmup_calls = 0
        self.transcribe_calls = 0

    async def warmup(self) -> None:
        self.warmup_calls += 1

    async def transcribe_chunk(self, audio_bytes, sample_rate_hz, language_hint=None):
        del audio_bytes, sample_rate_hz, language_hint
        self.transcribe_calls += 1
        now = datetime.now(UTC)
        return TranscriptChunk(
            text=self._text,
            started_at=now,
            ended_at=now + timedelta(milliseconds=10),
            asr_provider_used=self.name,
            confidence=0.9,
        )


@pytest.mark.asyncio
async def test_decorator_converts_simplified_to_traditional() -> None:
    inner = _StubProvider(text="简体中文文本")
    wrapped = _TraditionalChineseProvider(inner)

    chunk = await wrapped.transcribe_chunk(b"", 16000)
    assert chunk.text == "簡體中文文字"  # `s2twp` also swaps "文本" → "文字"


@pytest.mark.asyncio
async def test_decorator_forwards_warmup_and_name() -> None:
    inner = _StubProvider()
    wrapped = _TraditionalChineseProvider(inner)
    assert wrapped.name == inner.name
    await wrapped.warmup()
    assert inner.warmup_calls == 1


@pytest.mark.asyncio
async def test_decorator_preserves_other_chunk_fields() -> None:
    """Only `text` is rewritten; timestamps + provider-name + confidence pass
    through unchanged."""
    inner = _StubProvider(text="测试")
    wrapped = _TraditionalChineseProvider(inner)

    chunk = await wrapped.transcribe_chunk(b"", 16000)
    assert chunk.text == "測試"
    assert chunk.asr_provider_used == "stub"
    assert chunk.confidence == 0.9
    assert chunk.ended_at >= chunk.started_at


@pytest.mark.asyncio
async def test_decorator_handles_empty_text() -> None:
    """Inner returns "" (silence) → wrapper returns "" without raising."""
    inner = _StubProvider(text="")
    wrapped = _TraditionalChineseProvider(inner)
    chunk = await wrapped.transcribe_chunk(b"", 16000)
    assert chunk.text == ""
