"""PlaybookGenerator multimodal path tests — slice-20c task 4.1.

Covers the spec contract that `generate(... attachment_refs=())` keeps the
pre-slice byte-identical call path (plain string contents), and that
non-empty `attachment_refs` switches to a list of google-genai Parts.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from meeting_playbook.calendar.client import CalendarEvent
from meeting_playbook.playbook_generation.generator import (
    CONTENT_FIELDS,
    PlaybookGenerator,
)


@dataclass(frozen=True)
class _AttachmentRef:
    id: str
    kind: str
    file_path: str
    original_name: str


def _make_event() -> CalendarEvent:
    return CalendarEvent(
        id="evt_1",
        title="Q3 sync",
        start="2026-05-20T10:00:00+08:00",
        end="2026-05-20T11:00:00+08:00",
        attendees=["alex@example.com"],
        description="Discuss Q3 plan",
        organizer="me@example.com",
        organizer_email="me@example.com",
    )


def _full_draft_json() -> str:
    return json.dumps({field: f"value for {field}" * 3 for field in CONTENT_FIELDS})


@pytest.mark.asyncio
async def test_empty_attachments_passes_plain_string_to_call_model() -> None:
    """Pre-slice-20c contract: empty attachment_refs → contents is a string."""
    received: list[object] = []

    async def _capture(contents: object) -> str:
        received.append(contents)
        return _full_draft_json()

    gen = PlaybookGenerator(call_model=_capture, timeout_seconds=5.0)
    await gen.generate(_make_event(), viewer_email="me@example.com", viewer_name="Sean")

    assert received, "call_model was never invoked"
    assert isinstance(received[0], str), (
        f"contents must be a string, got {type(received[0]).__name__}"
    )


@pytest.mark.asyncio
async def test_non_empty_attachments_passes_parts_list_to_call_model(
    tmp_path: Path,
) -> None:
    """Slice-20c: non-empty attachment_refs → contents is a list of Parts."""
    received: list[object] = []

    async def _capture(contents: object) -> str:
        received.append(contents)
        return _full_draft_json()

    note = tmp_path / "agenda.md"
    note.write_text("# Agenda\n- topic A\n- topic B")
    refs = [
        _AttachmentRef(
            id="att_agenda",
            kind="markdown",
            file_path=str(note),
            original_name="agenda.md",
        )
    ]

    gen = PlaybookGenerator(call_model=_capture, timeout_seconds=5.0)
    await gen.generate(
        _make_event(),
        viewer_email="me@example.com",
        viewer_name="Sean",
        attachment_refs=refs,
    )

    assert received, "call_model was never invoked"
    contents = received[0]
    assert isinstance(contents, list), (
        f"contents must be a Parts list, got {type(contents).__name__}"
    )
    assert len(contents) >= 1


@pytest.mark.asyncio
async def test_attachment_text_propagates_into_prompt_string(tmp_path: Path) -> None:
    """The combined text Part MUST carry the extracted attachment text."""
    received: list[object] = []

    async def _capture(contents: object) -> str:
        received.append(contents)
        return _full_draft_json()

    note = tmp_path / "agenda.md"
    note.write_text("# Agenda\n- topic A")
    refs = [
        _AttachmentRef(
            id="att_agenda",
            kind="markdown",
            file_path=str(note),
            original_name="agenda.md",
        )
    ]

    gen = PlaybookGenerator(call_model=_capture, timeout_seconds=5.0)
    await gen.generate(
        _make_event(),
        viewer_email="me@example.com",
        viewer_name="Sean",
        attachment_refs=refs,
    )

    parts = received[0]
    assert isinstance(parts, list)
    # The last element is the combined text Part. We inspect via __dict__ /
    # attribute access since the mock SDK exposes Parts as opaque objects.
    text_part = parts[-1]
    text_value = getattr(text_part, "text", "")
    assert "agenda" in text_value.lower() or "topic A" in text_value


def test_sync_runner() -> None:
    """Wrapper so we don't need a class fixture for the async tests above."""
    asyncio.run(test_empty_attachments_passes_plain_string_to_call_model())
