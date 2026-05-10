"""Slice-10 summarization prompts — system + user message tests.

Per spec meeting-summary ADDED requirement scenarios for the
`build_system_instruction` and `build_user_message` helpers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from meeting_playbook.summarization.prompts import (
    REQUIRED_HEADINGS,
    build_system_instruction,
    build_user_message,
)


def _meeting(**fields: str) -> Any:
    defaults = {
        "title": "Q3 review",
        "counterparty_display_name": "林經理",
        "me_display_name": "Sean",
    }
    defaults.update(fields)
    return SimpleNamespace(**defaults)


def _playbook(**fields: str) -> Any:
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


def _chunk(speaker: str, text: str, started_at: datetime) -> Any:
    return SimpleNamespace(speaker=speaker, text=text, started_at=started_at)


def _chat(role: str, content: str) -> Any:
    return SimpleNamespace(role=role, content=content)


_NOW = datetime(2026, 5, 11, 14, 30, 0, tzinfo=UTC)


def test_system_instruction_zh_tw_lists_4_headings_verbatim():
    """zh-TW system instruction must contain the 4 literal headings in order
    + a phrase forbidding the model from changing heading text or order."""
    sys = build_system_instruction("zh-TW")
    h = REQUIRED_HEADINGS["zh-TW"]
    assert all(heading in sys for heading in h), f"missing one of {h} in system instruction"
    # Document order check.
    assert sys.index(h[0]) < sys.index(h[1]) < sys.index(h[2]) < sys.index(h[3])
    # Forbids changing heading text/order.
    assert "順序" in sys or "order" in sys.lower()


def test_system_instruction_en_lists_4_headings_verbatim():
    """en system instruction must contain the 4 literal English headings in order."""
    sys = build_system_instruction("en")
    h = REQUIRED_HEADINGS["en"]
    assert all(heading in sys for heading in h), f"missing one of {h}"
    assert sys.index(h[0]) < sys.index(h[1]) < sys.index(h[2]) < sys.index(h[3])
    assert "order" in sys.lower()


def test_user_message_renders_4_section_headings_in_order():
    """User message must contain the 4 section headings in the
    metadata → playbook → transcript → chat order."""
    msg = build_user_message(
        meeting=_meeting(),
        playbook=_playbook(objective="拿下 Q3 deal"),
        recent_chunks=[_chunk("me", "hi", _NOW)],
        chat_history=[_chat("user", "問")],
        locale="zh-TW",
    )
    assert (
        msg.index("## 會議基本資料")
        < msg.index("## Playbook")
        < msg.index("## 整場 Transcript")
        < msg.index("## In-meeting Advisor 對話")
    )


def test_user_message_empty_chat_history_renders_locale_placeholder():
    """zh-TW empty chat_history → section body == `(無)`."""
    msg = build_user_message(
        meeting=_meeting(),
        playbook=_playbook(objective="x"),
        recent_chunks=[_chunk("me", "hi", _NOW)],
        chat_history=[],
        locale="zh-TW",
    )
    chat_section_idx = msg.index("## In-meeting Advisor 對話")
    chat_body = msg[chat_section_idx:].split("\n", 1)[1].strip()
    assert chat_body == "(無)", f"expected `(無)` placeholder, got {chat_body!r}"


def test_user_message_empty_playbook_renders_locale_placeholder():
    """zh-TW fully-empty playbook → `## Playbook` body == `(尚未填寫)`."""
    msg = build_user_message(
        meeting=_meeting(),
        playbook=_playbook(),  # all empty
        recent_chunks=[_chunk("me", "hi", _NOW)],
        chat_history=[_chat("user", "q")],
        locale="zh-TW",
    )
    pb_idx = msg.index("## Playbook")
    next_section_idx = msg.index("## 整場 Transcript")
    pb_body = msg[pb_idx:next_section_idx].split("\n", 1)[1].strip()
    assert pb_body == "(尚未填寫)", f"expected `(尚未填寫)`, got {pb_body!r}"


def test_user_message_transcript_uses_meeting_display_names():
    """Transcript lines use meeting's me / counterparty display names."""
    msg = build_user_message(
        meeting=_meeting(me_display_name="Sean", counterparty_display_name="林經理"),
        playbook=_playbook(),
        recent_chunks=[
            _chunk("counterparty", "對方說的話", _NOW),
            _chunk("me", "我回的話", _NOW),
        ],
        chat_history=[],
        locale="zh-TW",
    )
    assert "Sean：我回的話" in msg
    assert "林經理：對方說的話" in msg


def test_user_message_chat_history_uses_advisor_label_not_counterparty_name():
    """Slice-9 carry-over: advisor lines use literal `Advisor`, not counterparty name."""
    msg = build_user_message(
        meeting=_meeting(counterparty_display_name="林經理"),
        playbook=_playbook(),
        recent_chunks=[],
        chat_history=[_chat("advisor", "建議內容")],
        locale="zh-TW",
    )
    assert "Advisor: 建議內容" in msg
    assert "林經理: 建議內容" not in msg


def test_required_headings_dict_has_both_locales():
    """Sanity: both locales present in REQUIRED_HEADINGS."""
    assert "zh-TW" in REQUIRED_HEADINGS
    assert "en" in REQUIRED_HEADINGS
    assert len(REQUIRED_HEADINGS["zh-TW"]) == 4
    assert len(REQUIRED_HEADINGS["en"]) == 4
