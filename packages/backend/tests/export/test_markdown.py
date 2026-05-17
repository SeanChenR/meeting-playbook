"""Pure-function tests for export/markdown.py.

Per slice-22-export-bundle spec `meeting-export/spec.md`:
- `playbook_to_markdown` — deterministic H1 + free-form + 6 H2 sections,
  empty fields render `_(empty)_`.
- `transcript_to_markdown` — `# Transcript` + one paragraph per chunk with
  speaker label mapping (`me`/`counterparty`/`speaker_cluster_N`).
- `summary_to_markdown` — `# Summary` + summary.markdown passthrough.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from meeting_playbook.export.markdown import (
    playbook_to_markdown,
    summary_to_markdown,
    transcript_to_markdown,
)


@dataclass(frozen=True)
class _PlaybookStub:
    free_form_markdown: str
    objective: str
    counterparty_profile: str
    anticipated_topics: str
    anticipated_objections: str
    talking_points: str
    red_lines: str


@dataclass(frozen=True)
class _ChunkStub:
    speaker: str
    text: str
    started_at: datetime


@dataclass(frozen=True)
class _SummaryStub:
    markdown: str


# ─── playbook_to_markdown ───────────────────────────────────────────


def test_playbook_markdown_emits_six_field_h2() -> None:
    """Spec scenario: Fully populated Playbook emits six H2 sections plus free-form."""
    playbook = _PlaybookStub(
        free_form_markdown="Note: skip dessert",
        objective="Close Q3 deal",
        counterparty_profile="林經理, VP Eng",
        anticipated_topics="Pricing, timeline",
        anticipated_objections="Budget freeze",
        talking_points="ROI in 6 months",
        red_lines="No exclusivity",
    )

    md = playbook_to_markdown(playbook, meeting_title="Quarterly Review")

    assert md.startswith("# Quarterly Review")
    assert "Note: skip dessert" in md
    # Six H2 sections in exact order.
    expected_order = [
        "## Objective",
        "## Counterparty Profile",
        "## Anticipated Topics",
        "## Anticipated Objections",
        "## Talking Points",
        "## Red Lines",
    ]
    last_pos = -1
    for header in expected_order:
        pos = md.find(header)
        assert pos > last_pos, f"{header} missing or out of order in:\n{md}"
        last_pos = pos
    # Each field's content appears under its header.
    assert "Close Q3 deal" in md
    assert "林經理, VP Eng" in md
    assert "Pricing, timeline" in md
    assert "Budget freeze" in md
    assert "ROI in 6 months" in md
    assert "No exclusivity" in md


def test_playbook_markdown_empty_field_placeholder() -> None:
    """Spec scenario: Empty Playbook fields render as _(empty)_ placeholder."""
    playbook = _PlaybookStub(
        free_form_markdown="",
        objective="",  # empty
        counterparty_profile="林經理",
        anticipated_topics="Pricing",
        anticipated_objections="Budget",
        talking_points="   ",  # whitespace-only → empty after strip
        red_lines="No exclusivity",
    )

    md = playbook_to_markdown(playbook, meeting_title="X")

    # Objective and Talking Points → _(empty)_, others render content.
    objective_section = md.split("## Objective", 1)[1].split("## Counterparty Profile", 1)[0]
    talking_section = md.split("## Talking Points", 1)[1].split("## Red Lines", 1)[0]
    assert "_(empty)_" in objective_section
    assert "_(empty)_" in talking_section
    # Non-empty sections do NOT carry the placeholder.
    cp_section = md.split("## Counterparty Profile", 1)[1].split("## Anticipated Topics", 1)[0]
    assert "_(empty)_" not in cp_section
    assert "林經理" in cp_section


# ─── transcript_to_markdown ─────────────────────────────────────────


def test_transcript_markdown_speaker_label_mapping() -> None:
    """Spec scenario: Mixed speakers render with locale-aware labels."""
    chunks = [
        _ChunkStub(
            speaker="me",
            started_at=datetime(2026, 5, 1, 10, 0, 0, tzinfo=UTC),
            text="Hi",
        ),
        _ChunkStub(
            speaker="counterparty",
            started_at=datetime(2026, 5, 1, 10, 0, 5, tzinfo=UTC),
            text="Hello",
        ),
        _ChunkStub(
            speaker="speaker_cluster_3",
            started_at=datetime(2026, 5, 1, 10, 0, 10, tzinfo=UTC),
            text="Joining",
        ),
    ]

    md = transcript_to_markdown(chunks)

    assert md.startswith("# Transcript")
    assert "**[10:00:00] Me (我方)**: Hi" in md
    assert "**[10:00:05] Counterparty (對方)**: Hello" in md
    assert "**[10:00:10] 與會者 3**: Joining" in md


def test_transcript_markdown_empty_list() -> None:
    """Spec scenario: Empty chunk list still renders the H1."""
    assert transcript_to_markdown([]) == "# Transcript\n"


# ─── summary_to_markdown ────────────────────────────────────────────


def test_summary_markdown_passes_through() -> None:
    """Spec scenario: Summary markdown is included unchanged."""
    summary = _SummaryStub(markdown="## Decisions\n- Ship Q3 launch.\n")
    assert summary_to_markdown(summary) == "# Summary\n\n## Decisions\n- Ship Q3 launch.\n\n"
