"""TacticalAdvisor prompt assembly tests.

Per slice-08 spec `Advice context assembly uses the last 60 seconds of
transcript and non-empty playbook fields` + `Advice output language follows
the request_advice frame's locale field`.

These tests build minimal in-memory `TranscriptChunk` and `Playbook` objects
without DB so they're fast + deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from meeting_playbook.advisor.prompts import (
    LOCALE_INSTRUCTION,
    build_system_instruction,
    build_user_message,
)


def _chunk(speaker: str, text: str, started_at: datetime) -> Any:
    """Build a duck-typed TranscriptChunk-like object for prompt builder."""
    return SimpleNamespace(
        speaker=speaker,
        text=text,
        started_at=started_at,
    )


def _playbook(**fields: str) -> Any:
    """Build a duck-typed Playbook-like object; all 7 fields default to ""."""
    defaults = {
        "free_form_markdown": "",
        "objective": "",
        "counterparty_profile": "",
        "anticipated_topics": "",
        "anticipated_objections": "",
        "talking_points": "",
        "red_lines": "",
    }
    defaults.update(fields)
    return SimpleNamespace(**defaults)


_NOW = datetime(2026, 5, 10, 14, 30, 0, tzinfo=UTC)


def test_user_message_uses_display_names():
    """Slice-08: prompt's dialogue section uses meeting display names verbatim."""
    chunks = [
        _chunk("counterparty", "對方剛說的話", _NOW),
        _chunk("me", "我回的話", _NOW + timedelta(seconds=10)),
        _chunk("counterparty", "對方繼續說", _NOW + timedelta(seconds=20)),
        _chunk("me", "我繼續回", _NOW + timedelta(seconds=30)),
    ]
    msg = build_user_message(
        playbook=_playbook(objective="拿下 Q3 deal"),
        recent_chunks=chunks,
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question=None,
        locale="zh-TW",
    )
    # 4 dialogue lines exist, ordered by started_at
    assert "Sean：我回的話" in msg
    assert "Sean：我繼續回" in msg
    assert "林經理：對方剛說的話" in msg
    assert "林經理：對方繼續說" in msg
    # Order check: 對方剛說的話 (index 0) appears BEFORE 我回的話 (index 1)
    assert (
        msg.index("對方剛說的話")
        < msg.index("我回的話")
        < msg.index("對方繼續說")
        < msg.index("我繼續回")
    )


def test_user_message_omits_empty_playbook_fields():
    """Slice-08: only non-empty structured fields appear; free_form appended when set."""
    pb = _playbook(objective="拿下 Q3 deal", free_form_markdown="# 自由筆記\n- 點 1\n- 點 2")
    msg = build_user_message(
        playbook=pb,
        recent_chunks=[],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question=None,
        locale="zh-TW",
    )
    # objective heading + value present
    assert "## 目標" in msg
    assert "拿下 Q3 deal" in msg
    # free_form appended
    assert "自由筆記" in msg
    # the OTHER 5 structured fields are NOT rendered as headings
    for missing in ("## 對方輪廓", "## 預期主題", "## 預期反對", "## 談話要點", "## 紅線"):
        assert missing not in msg, f"empty field heading leaked: {missing}"


def test_empty_inputs_render_placeholders():
    """Slice-08: zero chunks + empty playbook → explicit zh-TW placeholders."""
    msg = build_user_message(
        playbook=_playbook(),  # all 7 empty
        recent_chunks=[],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question=None,
        locale="zh-TW",
    )
    assert "(無對話內容)" in msg
    assert "(尚未填寫)" in msg


def test_user_question_is_appended_when_supplied():
    """Slice-08 forward-compat for slice-9 chatbox: user_question routes to its own line."""
    msg = build_user_message(
        playbook=_playbook(objective="X"),
        recent_chunks=[_chunk("me", "...", _NOW)],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question="他剛說的 budget 怎麼回？",
        locale="zh-TW",
    )
    assert "Sean 想問：他剛說的 budget 怎麼回？" in msg


def test_user_question_none_uses_default_question():
    """Slice-08 default branch: no user_question → default question line."""
    msg = build_user_message(
        playbook=_playbook(objective="X"),
        recent_chunks=[_chunk("me", "...", _NOW)],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question=None,
        locale="zh-TW",
    )
    assert "請給出戰術建議。" in msg
    # The user_question branch text MUST NOT appear
    assert "想問" not in msg


# ─── Locale switch ──────────────────────────────────────────────────


def test_locale_switches_system_instruction():
    """Slice-08: system_instruction includes the locale's directive line."""
    sys_zh = build_system_instruction("zh-TW")
    sys_en = build_system_instruction("en")
    assert "請用繁體中文" in sys_zh
    assert "Reply in English" in sys_en
    # And NOT the other locale's directive in each
    assert "Reply in English" not in sys_zh
    assert "請用繁體中文" not in sys_en


@pytest.mark.parametrize(
    "locale,expected",
    [
        ("zh-TW", "請給出戰術建議。"),
        ("en", "Please give tactical advice."),
    ],
)
def test_user_message_question_line_locale_aware_when_no_question(locale, expected):
    """Slice-08: default question line is locale-specific."""
    msg = build_user_message(
        playbook=_playbook(),
        recent_chunks=[],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question=None,
        locale=locale,
    )
    assert expected in msg


def test_locale_instruction_dict_has_both_locales():
    """Sanity: both supported locales appear in LOCALE_INSTRUCTION."""
    assert "zh-TW" in LOCALE_INSTRUCTION
    assert "en" in LOCALE_INSTRUCTION


# ─── Slice 9: chat_history multi-turn context ─────────────────────────────


def _chat(role: str, content: str) -> Any:
    """Build a duck-typed ChatMessage-like object for prompt builder."""
    return SimpleNamespace(role=role, content=content)


def test_chat_history_section_omitted_when_empty():
    """Slice-09 Decision 5: empty chat_history → no `## 對話紀錄` heading."""
    msg = build_user_message(
        playbook=_playbook(objective="拿下 deal"),
        recent_chunks=[_chunk("me", "hello", _NOW)],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question=None,
        locale="zh-TW",
        chat_history=[],
    )
    assert "## 對話紀錄" not in msg
    assert "## Chat history" not in msg


def test_chat_history_section_renders_in_order_with_role_labels():
    """Slice-09 Decision 5: 4 messages render in array order with `Sean:` / `Advisor:`."""
    history = [
        _chat("user", "問題A"),
        _chat("advisor", "回答A"),
        _chat("user", "問題B"),
        _chat("advisor", "回答B"),
    ]
    msg = build_user_message(
        playbook=_playbook(objective="x"),
        recent_chunks=[],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question=None,
        locale="zh-TW",
        chat_history=history,
    )
    assert "## 對話紀錄" in msg
    # All four lines present.
    for needed in ("Sean: 問題A", "Advisor: 回答A", "Sean: 問題B", "Advisor: 回答B"):
        assert needed in msg, f"missing line: {needed}"
    # In-order check.
    assert (
        msg.index("Sean: 問題A")
        < msg.index("Advisor: 回答A")
        < msg.index("Sean: 問題B")
        < msg.index("Advisor: 回答B")
    )


def test_chat_history_section_sits_between_transcript_and_question():
    """Slice-09 Decision 5: section order is playbook → 60s dialogue → chat history → question."""
    msg = build_user_message(
        playbook=_playbook(objective="拿下 deal"),
        recent_chunks=[_chunk("counterparty", "對方說", _NOW)],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question="新問題",
        locale="zh-TW",
        chat_history=[_chat("user", "之前問過"), _chat("advisor", "之前回過")],
    )
    # Heading-by-heading order check.
    assert (
        msg.index("## 會議 playbook")
        < msg.index("## 最近 60 秒對話")
        < msg.index("## 對話紀錄")
        < msg.index("新問題")
    )


def test_chat_history_uses_advisor_label_not_counterparty_name():
    """Slice-09 Decision 5: advisor lines use literal 'Advisor:', not counterparty_display_name."""
    msg = build_user_message(
        playbook=_playbook(),
        recent_chunks=[],
        me_display_name="Sean",
        counterparty_display_name="林經理",
        user_question=None,
        locale="zh-TW",
        chat_history=[_chat("advisor", "建議內容")],
    )
    assert "Advisor: 建議內容" in msg
    assert "林經理: 建議內容" not in msg
    assert "林經理：建議內容" not in msg  # also not the full-width colon variant
