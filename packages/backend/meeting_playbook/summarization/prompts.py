"""Prompt assembly for the post-meeting summarizer (slice-10).

Per spec meeting-summary ADDED requirement "Summary prompt assembles 4
fixed sections":
- Stable per-locale system_instruction enumerating the 4 required
  headings + forbidden behaviors
- Per-request user_message rebuilt from meeting metadata + non-empty
  playbook fields + full transcript + chat history
- Empty playbook / chat_history render their localised placeholders
  so the model is signalled to honestly say `(無)` rather than
  invent content
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from meeting_playbook.summarization.base import Locale

# Fixed headings per locale, in document order. Validation in
# `vertex_summarizer._validate_4_headings` matches against this exact tuple.
REQUIRED_HEADINGS: dict[Locale, tuple[str, str, str, str]] = {
    "zh-TW": ("## 重點討論", "## 決議", "## Action items", "## 待解決問題"),
    "en": ("## Key discussion points", "## Decisions", "## Action items", "## Open questions"),
}

# Per-locale instruction line that joins the stable system prompt body.
LOCALE_INSTRUCTION: dict[Locale, str] = {
    "zh-TW": "請用繁體中文（zh-TW）回答。",
    "en": "Reply in English.",
}

# Per-locale labels for the user message section headings.
_USER_HEADINGS: dict[Locale, dict[str, str]] = {
    "zh-TW": {
        "metadata": "## 會議基本資料",
        "playbook": "## Playbook",
        "transcript": "## 整場 Transcript",
        "chat_history": "## In-meeting Advisor 對話",
    },
    "en": {
        "metadata": "## Meeting metadata",
        "playbook": "## Playbook",
        "transcript": "## Full transcript",
        "chat_history": "## In-meeting Advisor chat",
    },
}

_EMPTY_PLAYBOOK: dict[Locale, str] = {"zh-TW": "(尚未填寫)", "en": "(empty playbook)"}
_EMPTY_CHAT: dict[Locale, str] = {"zh-TW": "(無)", "en": "(none)"}
_ADVISOR_LABEL = "Advisor"

# Per-locale labels for non-empty playbook structured fields (matches
# slice-9 advisor prompts.py for consistency).
_FIELD_LABELS: dict[Locale, dict[str, str]] = {
    "zh-TW": {
        "objective": "目標",
        "counterparty_profile": "對方輪廓",
        "anticipated_topics": "預期主題",
        "anticipated_objections": "預期反對",
        "talking_points": "談話要點",
        "red_lines": "紅線",
    },
    "en": {
        "objective": "Objective",
        "counterparty_profile": "Counterparty profile",
        "anticipated_topics": "Anticipated topics",
        "anticipated_objections": "Anticipated objections",
        "talking_points": "Talking points",
        "red_lines": "Red lines",
    },
}

_STRUCTURED_FIELDS: tuple[str, ...] = (
    "objective",
    "counterparty_profile",
    "anticipated_topics",
    "anticipated_objections",
    "talking_points",
    "red_lines",
)


def build_system_instruction(locale: Locale) -> str:
    """Locale-aware system prompt enumerating the 4 required headings.

    Cache-friendly: the same string per locale across requests so Vertex's
    built-in system-instruction cache can hit on repeat regenerates.
    """
    h = REQUIRED_HEADINGS[locale]
    if locale == "en":
        body = (
            "You are Sean's post-meeting note-taker.\n"
            "Your job is to compress the transcript + the playbook Sean prepared\n"
            "+ the in-meeting advisor chat into 4 markdown sections, headings and\n"
            "order EXACTLY as below:\n"
            "\n"
            f"{h[0]}\n"
            "List 3-7 bullets, one per discussion point.\n"
            "\n"
            f"{h[1]}\n"
            "List the explicit decisions made. If none, write `(none)`.\n"
            "\n"
            f"{h[2]}\n"
            "Each item formatted as: - [{owner_or_TBD}] {action}\n"
            "Owner extracted from transcript when explicitly assigned (e.g.\n"
            "'Sean, please...', 'Lin, can you...'); when unclear, fill TBD.\n"
            "\n"
            f"{h[3]}\n"
            "List questions raised in the meeting that remain unresolved.\n"
            "If none, write `(none)`.\n"
            "\n"
            "Strict rules:\n"
            "- DO NOT change the heading text or order.\n"
            "- DO NOT skip any heading (write `(none)` for an empty section).\n"
            "- DO NOT introduce facts beyond the transcript / playbook / chat history.\n"
            "- DO NOT add extra headings (e.g. `## Summary`, `## Conclusion`).\n"
            "- DO NOT merge the 4 sections into a single paragraph.\n"
        )
    else:
        body = (
            "你是 Sean 的會後筆記助理。\n"
            "你的任務是把整場會議的 transcript + Sean 準備的 playbook +\n"
            "會中與 advisor 的對話，濃縮成 4 段 markdown，順序與標題嚴格如下:\n"
            "\n"
            f"{h[0]}\n"
            "列出 3-7 條 bullet，每條一個重點。\n"
            "\n"
            f"{h[1]}\n"
            "列出本場做出的明確決定。沒有則寫 `(無)`。\n"
            "\n"
            f"{h[2]}\n"
            "每條格式: - [{owner_or_TBD}] {action}\n"
            "owner 從 transcript 中明確指派的人名抽取 (例: 'Sean 你...'、\n"
            "'請林經理...'); 無法判斷者填 TBD。\n"
            "\n"
            f"{h[3]}\n"
            "列出本場提出但未解決的問題。沒有則寫 `(無)`。\n"
            "\n"
            "絕對不要:\n"
            "- 改變 4 個 heading 的文字 / 順序\n"
            "- 跳過任何一個 section (empty 寫 `(無)`)\n"
            "- 引入 transcript / playbook / chat history 之外的事實\n"
            "- 加入 ## 摘要、## 總結 之類的多餘 heading\n"
            "- 把 4 個 section 揉在一起寫成段落\n"
        )
    return body + "\n" + LOCALE_INSTRUCTION[locale]


def _format_playbook(playbook: Any | None, locale: Locale) -> str:
    if playbook is None:
        return _EMPTY_PLAYBOOK[locale]
    sections: list[str] = []
    labels = _FIELD_LABELS[locale]
    for field in _STRUCTURED_FIELDS:
        value = (getattr(playbook, field, "") or "").strip()
        if value:
            sections.append(f"### {labels[field]}\n{value}")
    free_form = (getattr(playbook, "free_form_markdown", "") or "").strip()
    if free_form:
        sections.append(free_form)
    if not sections:
        return _EMPTY_PLAYBOOK[locale]
    return "\n\n".join(sections)


def _format_transcript(
    chunks: Sequence[Any],
    me_display_name: str,
    counterparty_display_name: str,
    locale: Locale,
) -> str:
    if not chunks:
        return _EMPTY_CHAT[locale]
    lines: list[str] = []
    for c in chunks:
        speaker = me_display_name if c.speaker == "me" else counterparty_display_name
        ts = c.started_at.strftime("%H:%M:%S")
        lines.append(f"{speaker}：{c.text} ({ts})")
    return "\n".join(lines)


def _format_chat_history(
    messages: Sequence[Any],
    me_display_name: str,
    locale: Locale,
) -> str:
    if not messages:
        return _EMPTY_CHAT[locale]
    lines: list[str] = []
    for m in messages:
        label = me_display_name if m.role == "user" else _ADVISOR_LABEL
        lines.append(f"{label}: {m.content}")
    return "\n".join(lines)


def build_user_message(
    *,
    meeting: Any,
    playbook: Any | None,
    recent_chunks: Sequence[Any],
    chat_history: Sequence[Any],
    locale: Locale,
) -> str:
    """Assemble the per-request user message: metadata → playbook → transcript → chat.

    Section order is fixed per Decision 5; section headings come from
    `_USER_HEADINGS[locale]`. Empty playbook / chat_history render their
    localised placeholders.
    """
    h = _USER_HEADINGS[locale]
    metadata = (
        f"- 標題：{meeting.title}\n"
        f"- 對方：{meeting.counterparty_display_name}\n"
        f"- 我方：{meeting.me_display_name}"
        if locale == "zh-TW"
        else (
            f"- Title: {meeting.title}\n"
            f"- Counterparty: {meeting.counterparty_display_name}\n"
            f"- Me: {meeting.me_display_name}"
        )
    )
    playbook_section = _format_playbook(playbook, locale)
    transcript_section = _format_transcript(
        recent_chunks,
        meeting.me_display_name,
        meeting.counterparty_display_name,
        locale,
    )
    chat_section = _format_chat_history(chat_history, meeting.me_display_name, locale)
    return (
        f"{h['metadata']}\n{metadata}\n\n"
        f"{h['playbook']}\n{playbook_section}\n\n"
        f"{h['transcript']}\n{transcript_section}\n\n"
        f"{h['chat_history']}\n{chat_section}"
    )


__all__ = [
    "LOCALE_INSTRUCTION",
    "REQUIRED_HEADINGS",
    "build_system_instruction",
    "build_user_message",
]
