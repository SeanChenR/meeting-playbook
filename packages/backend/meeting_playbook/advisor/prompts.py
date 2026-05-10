"""Prompt assembly for the TacticalAdvisor (Vertex Flash, in-meeting).

Per slice-08 design:
- system_instruction is locale-aware and stable per locale (cache-friendly)
- user_message rebuilt per request: non-empty playbook fields + last-60s
  dialogue + question line
- Empty inputs render explicit placeholders so the model is signalled to
  honestly say "no actionable signal" rather than hallucinate.
"""

from __future__ import annotations

from collections.abc import Sequence

from meeting_playbook.advisor.base import Locale
from meeting_playbook.playbooks.models import Playbook
from meeting_playbook.sessions.models import TranscriptChunk

# Per-locale instruction line that joins the stable system prompt body.
LOCALE_INSTRUCTION: dict[Locale, str] = {
    "zh-TW": "請用繁體中文（zh-TW）回答。",
    "en": "Reply in English.",
}

# Default question line when the user did not supply user_question (slice-8
# button-only path). Slice-9 chatbox path supplies user_question and falls into
# the alternate branch in `build_user_message`.
_DEFAULT_QUESTION_LINE: dict[Locale, str] = {
    "zh-TW": "請給出戰術建議。",
    "en": "Please give tactical advice.",
}

# Placeholder rendered when the assembled context section has nothing to show.
_EMPTY_DIALOGUE_PLACEHOLDER: dict[Locale, str] = {
    "zh-TW": "(無對話內容)",
    "en": "(no recent dialog)",
}
_EMPTY_PLAYBOOK_PLACEHOLDER: dict[Locale, str] = {
    "zh-TW": "(尚未填寫)",
    "en": "(empty playbook)",
}

# Per-locale section headings + structured-field labels (Markdown headings).
_PLAYBOOK_HEADING: dict[Locale, str] = {
    "zh-TW": "## 會議 playbook",
    "en": "## Meeting playbook",
}
_DIALOGUE_HEADING: dict[Locale, str] = {
    "zh-TW": "## 最近 60 秒對話",
    "en": "## Last 60 seconds of dialog",
}

# Structured field labels per locale (matches frontend i18n).
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

# Field iteration order — same as the playbook editor in the UI.
_STRUCTURED_FIELDS: tuple[str, ...] = (
    "objective",
    "counterparty_profile",
    "anticipated_topics",
    "anticipated_objections",
    "talking_points",
    "red_lines",
)


def build_system_instruction(locale: Locale) -> str:
    """Stable system prompt + locale directive.

    Cache-friendly: the same string per locale across requests so Vertex's
    built-in system-instruction cache can hit on repeat clicks.
    """
    if locale == "en":
        body = (
            "You are Sean's tactical sales advisor for live B2B meetings.\n"
            "Output rules:\n"
            "- Format: Markdown bullet list, 3-5 items, each ≤ 30 characters.\n"
            "- Tone: direct, immediately actionable. Avoid platitudes.\n"
            "- Use **bold** to highlight the single most important phrase.\n"
            "- If the recent dialog gives no actionable signal, say so honestly:\n"
            '  "No clear tactical hook in the recent dialog; you may proactively'
            ' steer the topic."\n'
            "- NEVER invent facts not in the playbook or transcript.\n"
        )
    else:
        body = (
            "You are Sean's tactical sales advisor for live B2B meetings.\n"
            "Output rules:\n"
            "- Format: Markdown bullet list, 3-5 items, each ≤ 30 characters.\n"
            "- Tone: 直白、可立即執行 (immediately actionable). Avoid platitudes.\n"
            "- Use **bold** to highlight the single most important phrase.\n"
            "- If the recent dialog gives no actionable signal, say so honestly:\n"
            "  「目前對話無明顯戰術點，可主動推進議題。」\n"
            "- NEVER invent facts not in the playbook or transcript.\n"
        )
    return body + LOCALE_INSTRUCTION[locale]


def _format_dialogue(
    chunks: Sequence[TranscriptChunk],
    me_display_name: str,
    counterparty_display_name: str,
    locale: Locale,
) -> str:
    if not chunks:
        return _EMPTY_DIALOGUE_PLACEHOLDER[locale]
    lines: list[str] = []
    for c in chunks:
        name = me_display_name if c.speaker == "me" else counterparty_display_name
        ts = c.started_at.strftime("%H:%M:%S")
        lines.append(f"{name}：{c.text} ({ts})")
    return "\n".join(lines)


def _format_playbook_md(playbook: Playbook | None, locale: Locale) -> str:
    if playbook is None:
        return _EMPTY_PLAYBOOK_PLACEHOLDER[locale]

    sections: list[str] = []
    labels = _FIELD_LABELS[locale]
    for field in _STRUCTURED_FIELDS:
        value = getattr(playbook, field, "") or ""
        if value.strip():
            sections.append(f"## {labels[field]}\n{value.strip()}")

    free_form = (playbook.free_form_markdown or "").strip()
    if free_form:
        sections.append(free_form)

    if not sections:
        return _EMPTY_PLAYBOOK_PLACEHOLDER[locale]
    return "\n\n".join(sections)


def _format_question_line(user_question: str | None, locale: Locale) -> str:
    if user_question is None:
        return _DEFAULT_QUESTION_LINE[locale]
    if locale == "en":
        return f"Sean asks: {user_question}\nPlease answer based on the above context."
    return f"Sean 想問：{user_question}\n請根據以上 context 回答。"


def build_user_message(
    playbook: Playbook | None,
    recent_chunks: Sequence[TranscriptChunk],
    me_display_name: str,
    counterparty_display_name: str,
    user_question: str | None,
    locale: Locale,
) -> str:
    """Assemble the per-request user message: playbook + dialogue + question.

    Empty playbook / dialogue render their localised placeholders so the model
    sees explicit "no signal here" markers and avoids hallucinating advice.
    """
    playbook_md = _format_playbook_md(playbook, locale)
    dialogue_md = _format_dialogue(
        recent_chunks, me_display_name, counterparty_display_name, locale
    )
    question_line = _format_question_line(user_question, locale)
    return (
        f"{_PLAYBOOK_HEADING[locale]}\n{playbook_md}\n\n"
        f"{_DIALOGUE_HEADING[locale]}\n{dialogue_md}\n\n"
        f"{question_line}"
    )


__all__ = [
    "LOCALE_INSTRUCTION",
    "build_system_instruction",
    "build_user_message",
]
