"""Simplified → Traditional Chinese (Taiwan) transliteration helper.

Backstory: Qwen3-ASR-1.7B and Whisper large-v3-turbo are both trained on
predominantly simplified-Chinese corpora, so their Mandarin output lands
in 简体 even when the speaker is using 國語 (zh-TW). Per CLAUDE.md domain
language ("用語必須是台灣慣用"), every transcript chunk written to the DB
should be in Traditional Chinese with Taiwan phrase substitutions
(e.g. 「軟件→軟體」, 「視頻→影片」, 「博客→部落格」).

We use OpenCC's `s2twp` config — Simplified → Traditional, Taiwan
variants, with phrase substitution. The `opencc-python-reimplemented`
package is pure Python (no C extension) so it's safe to import in any
process without build-system surprises.

Usage:
    from meeting_playbook.asr.transliteration import to_traditional_chinese
    text_zhTW = to_traditional_chinese("简体中文文本")  # → "簡體中文文字"

This module owns the singleton converter so we don't pay the load cost
on every chunk. The converter is stateless + thread-safe per OpenCC docs.
"""

from __future__ import annotations

from functools import lru_cache

from opencc import OpenCC


@lru_cache(maxsize=1)
def _converter() -> OpenCC:
    return OpenCC("s2twp")


def to_traditional_chinese(text: str) -> str:
    """Convert a string from simplified Chinese to Traditional (Taiwan).

    Idempotent on text that's already Traditional. Empty / whitespace-only
    input is returned unchanged. Non-Chinese characters pass through.
    """
    if not text or not text.strip():
        return text
    return _converter().convert(text)


__all__ = ["to_traditional_chinese"]
