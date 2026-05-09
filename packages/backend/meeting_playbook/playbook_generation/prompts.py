"""Prompt templates for PlaybookGenerator.

Two-stage strategy (per slice-05 design):
- BUILD_PRIMARY_PROMPT: full event metadata, requires non-empty 7 fields
- BUILD_FALLBACK_PROMPT: invoked when any field came back empty; tells the
  model to fill the missing fields based purely on the event title plus
  general best practices for B2B sales / consulting prep

Round-2 ingest: every prompt is prefixed with `_render_viewer_block` so the
model knows who the playbook is FOR and what role they play in the meeting
(organizer / attendee / external).
"""

from __future__ import annotations

from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.calendar.identity import (
    ViewerRole,
    classify_viewer_role,
    pick_counterparty,
)

# Sentinel inserted when the LLM returns empty even after a fallback call.
EMPTY_FIELD_SENTINEL = "(請自行填寫 / Please fill in)"

_ROLE_GUIDANCE: dict[ViewerRole, str] = {
    "organizer": (
        "They are hosting / driving this meeting; objectives and talking_points "
        "should reflect what they want to achieve and how they want to lead the "
        "discussion."
    ),
    "attendee": (
        "They were invited by someone else; objectives and talking_points should "
        "reflect what they need to learn or contribute as a participant, and what "
        "questions to ask."
    ),
    "external": (
        "They are previewing this event from a calendar they subscribe to but "
        "were not personally invited; the playbook should help them decide what "
        "to take away from observing the meeting."
    ),
}


def _format_event(event: CalendarEvent) -> str:
    attendees = ", ".join(event.attendees) if event.attendees else "(none)"
    description = event.description.strip() or "(empty)"
    organizer = event.organizer or "(unknown)"
    return (
        f"Title: {event.title}\n"
        f"Start: {event.start}\n"
        f"End: {event.end}\n"
        f"Organizer: {organizer}\n"
        f"Attendees: {attendees}\n"
        f"Description:\n{description}"
    )


def _render_viewer_block(event: CalendarEvent, viewer_email: str, viewer_name: str) -> str:
    """Leading paragraph that names the viewer + role + others list."""
    role = classify_viewer_role(event, viewer_email)
    guidance = _ROLE_GUIDANCE[role]

    name = viewer_name.strip()
    if not name:
        name = viewer_email.split("@", 1)[0] if viewer_email and "@" in viewer_email else "the user"

    others = pick_counterparty(event, viewer_email or "")
    email_label = f" ({viewer_email})" if viewer_email else " (viewer email unknown)"

    return (
        f"You are preparing this playbook for {name}{email_label}.\n"
        f"In this meeting their role is: {role}.\n"
        f"{guidance}\n"
        f"The other parties are: {others}.\n"
        f"The playbook is {name}'s OWN preparation notes — they will read it "
        f"alone before the meeting. It is NOT a letter, NOT a chat reply, NOT "
        f"advice addressed to {name}.\n\n"
    )


_FORMAT_RULES = (
    "Format rules (apply to EVERY field):\n"
    "- Write in Traditional Chinese (繁體中文).\n"
    "- Use bullet points and short markdown headings; NO narrative paragraphs.\n"
    "- Use imperative or noun-phrase tone — write `確認對方預算範圍` NOT\n"
    "  `Sean，你要記得確認對方預算範圍`.\n"
    "- Do NOT greet anyone (no `你好`, no `Hi`, no `Dear`).\n"
    "- Do NOT address the viewer in second person (no standalone `你` / `您` /\n"
    "  `你的` to refer to the viewer; the playbook is the viewer's own notes).\n"
    "- Lead with the most actionable item first. Each section should be\n"
    "  scannable in under 10 seconds.\n"
    "- Prefer 3-5 short bullets per field over one long paragraph.\n"
)


def build_primary_prompt(event: CalendarEvent, viewer_email: str, viewer_name: str) -> str:
    prelude = _render_viewer_block(event, viewer_email, viewer_name)
    body = _format_event(event)
    return (
        f"{prelude}"
        "Output a JSON object with exactly these seven keys:\n"
        "  free_form_markdown, objective, counterparty_profile, anticipated_topics,\n"
        "  anticipated_objections, talking_points, red_lines\n"
        "Each value MUST be a non-empty string. The free_form_markdown value MUST\n"
        "contain at least three lines of markdown content. If the event metadata is\n"
        "sparse, use general best practices for the meeting type to populate every\n"
        "field — never leave a field empty.\n\n"
        f"{_FORMAT_RULES}\n"
        f"Calendar event:\n{body}\n"
    )


def build_fallback_prompt(
    event: CalendarEvent,
    missing_fields: list[str],
    viewer_email: str,
    viewer_name: str,
) -> str:
    prelude = _render_viewer_block(event, viewer_email, viewer_name)
    body = _format_event(event)
    fields = ", ".join(missing_fields)
    return (
        f"{prelude}"
        "FALLBACK pass — the previous response left these fields empty: "
        f"{fields}.\n"
        "Re-emit the JSON object with all seven keys. Pay special attention to the\n"
        "missing fields: derive their content purely from the event title plus\n"
        "general best practices for the meeting type. Each value MUST be a non-empty\n"
        "string. The free_form_markdown value MUST contain at least three lines.\n\n"
        f"{_FORMAT_RULES}\n"
        f"Calendar event:\n{body}\n"
    )
