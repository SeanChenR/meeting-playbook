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
from meeting_playbook.chat.models import ChatMessage
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
# Slice-09: chat history section heading. Sits between dialogue + question.
_CHAT_HISTORY_HEADING: dict[Locale, str] = {
    "zh-TW": "## 對話紀錄",
    "en": "## Chat history",
}
# Slice-09: literal label for advisor-role rows in chat_history. Always
# `Advisor`, NOT the meeting's counterparty_display_name — the advisor is
# distinct from the counterparty and conflating them confuses the model.
_ADVISOR_LABEL = "Advisor"

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
    """Mode-aware system prompt + locale directive.

    Slice-09 revision: the prompt now describes TWO modes so the model
    can decide format based on Sean's actual question. Slice-08 forced
    every reply to be a 3-5 item bullet list which produced absurd
    output when Sean asked meta questions like "what did I ask you
    before?" or said "hi".

    Cache-friendly: the same string per locale across requests so
    Vertex's built-in system-instruction cache can hit on repeat clicks.
    """
    if locale == "en":
        body = (
            "You are Sean's tactical sales advisor for live B2B meetings.\n"
            "\n"
            "You operate in two modes; pick the one that fits Sean's question:\n"
            "\n"
            "**Tactical mode** (default — Sean clicks 'Get Advice', or asks for"
            " advice / suggestions / next move / how-to-respond):\n"
            "- Output a Markdown bullet list, 3-5 items, each ≤ 30 characters.\n"
            "- Direct, immediately actionable. Avoid platitudes.\n"
            "- Use **bold** to highlight the single most important phrase.\n"
            "- If the recent dialog has no actionable signal, say:\n"
            '  "No clear tactical hook in the recent dialog; you may proactively'
            ' steer the topic."\n'
            "\n"
            "**Conversational mode** (Sean asks a meta / clarifying / recap"
            " question, makes small talk, or asks about prior chat history):\n"
            "- Reply naturally — full sentences, paragraphs, or whatever fits.\n"
            "- Match Sean's register (formal question → professional answer;\n"
            "  casual greeting → brief casual reply).\n"
            "- For 'what did I ask before?' / 'recap our chat' style questions,\n"
            "  answer factually from the chat history section.\n"
            "- Keep it concise; no filler.\n"
            "\n"
            "NEVER invent facts not in the playbook, transcript, or chat history.\n"
        )
    else:
        body = (
            "You are Sean's tactical sales advisor for live B2B meetings.\n"
            "\n"
            "你有兩個模式，依 Sean 的問題自行判斷該用哪個:\n"
            "\n"
            "**戰術模式** (預設 — Sean 按 Get Advice 鈕、或明確要建議 / 下一步 /"
            " 怎麼回應):\n"
            "- 輸出 Markdown bullet list，3-5 條，每條 ≤ 30 字。\n"
            "- 直白、可立即執行，避免空話。\n"
            "- 用 **bold** 標出最重要的一個短語。\n"
            "- 若 60 秒對話無明顯戰術點，回:\n"
            "  「目前對話無明顯戰術點，可主動推進議題。」\n"
            "\n"
            "**對話模式** (Sean 問 meta / 澄清 / 摘要問題、閒聊、或問之前聊過什麼):\n"
            "- 自然回應 — 完整句子、段落、看狀況選格式。\n"
            "- 配合 Sean 的口吻 (正式問題 → 專業回答；隨口打招呼 → 簡短回應)。\n"
            "- 「我前面問過什麼」/「幫我摘要對話」這類問題，從 chat history\n"
            "  區段如實回答。\n"
            "- 簡潔，不要廢話。\n"
            "\n"
            "絕對不要捏造 playbook、transcript、chat history 之外的事實。\n"
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


def _format_chat_history(
    messages: Sequence[ChatMessage],
    me_display_name: str,
    locale: Locale,
) -> str:
    """Render chat_history as a `## 對話紀錄` (zh-TW) / `## Chat history` (en)
    section. Returns the empty string when `messages` is empty so the caller
    can omit the section entirely (no empty headings).
    """
    if not messages:
        return ""
    lines: list[str] = []
    for m in messages:
        label = me_display_name if m.role == "user" else _ADVISOR_LABEL
        lines.append(f"{label}: {m.content}")
    body = "\n".join(lines)
    return f"{_CHAT_HISTORY_HEADING[locale]}\n{body}"


def build_user_message(
    playbook: Playbook | None,
    recent_chunks: Sequence[TranscriptChunk],
    me_display_name: str,
    counterparty_display_name: str,
    user_question: str | None,
    locale: Locale,
    chat_history: Sequence[ChatMessage] = (),
) -> str:
    """Assemble the per-request user message.

    Section order: playbook → recent dialogue → (chat history if any) → question.
    Empty playbook / dialogue render their localised placeholders so the model
    sees explicit "no signal here" markers and avoids hallucinating advice.
    Empty chat_history omits the section heading entirely.
    """
    playbook_md = _format_playbook_md(playbook, locale)
    dialogue_md = _format_dialogue(
        recent_chunks, me_display_name, counterparty_display_name, locale
    )
    chat_history_section = _format_chat_history(chat_history, me_display_name, locale)
    question_line = _format_question_line(user_question, locale)

    parts: list[str] = [
        f"{_PLAYBOOK_HEADING[locale]}\n{playbook_md}",
        f"{_DIALOGUE_HEADING[locale]}\n{dialogue_md}",
    ]
    if chat_history_section:
        parts.append(chat_history_section)
    parts.append(question_line)
    return "\n\n".join(parts)


__all__ = [
    "LOCALE_INSTRUCTION",
    "build_system_instruction",
    "build_user_message",
]
