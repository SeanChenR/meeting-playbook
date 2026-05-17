"""Pure-function markdown serializers for the per-meeting export bundle.

Per slice-22-export-bundle design.md > Markdown 序列化規則:
  - `playbook_to_markdown` produces a deterministic document: H1 = meeting
    title; optional free-form markdown; six structured H2 sections in a
    fixed order; empty fields render as `_(empty)_` so consumers can grep
    for unfilled slots.
  - `transcript_to_markdown` emits `# Transcript` followed by one paragraph
    per chunk: `**[HH:MM:SS] {label}**: {text}` where speaker labels are
    mapped per the domain glossary (`me` → `Me (我方)`,
    `counterparty` → `Counterparty (對方)`,
    `speaker_cluster_N` → `與會者 N`). Other speaker values pass through.
  - `summary_to_markdown` wraps an existing `summary.markdown` payload under
    an `# Summary` H1 without any other transformation; the bundler is
    responsible for skipping the call when no Summary row exists.

All three functions are pure — they do no I/O and rely only on the dataclass
attributes specified in the slice-22 spec. Models are not imported directly
so the helpers can be unit-tested without a database session.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

EMPTY_PLACEHOLDER = "_(empty)_"

# Order is the contract — do NOT reorder without bumping the spec.
_PLAYBOOK_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Objective", "objective"),
    ("Counterparty Profile", "counterparty_profile"),
    ("Anticipated Topics", "anticipated_topics"),
    ("Anticipated Objections", "anticipated_objections"),
    ("Talking Points", "talking_points"),
    ("Red Lines", "red_lines"),
)

_SPEAKER_CLUSTER_RE = re.compile(r"^speaker_cluster_(\d+)$")


class _PlaybookLike(Protocol):
    free_form_markdown: str
    objective: str
    counterparty_profile: str
    anticipated_topics: str
    anticipated_objections: str
    talking_points: str
    red_lines: str


class _ChunkLike(Protocol):
    speaker: str
    text: str
    started_at: datetime


class _SummaryLike(Protocol):
    markdown: str


def _field_body(value: str) -> str:
    """Return the body string for a Playbook field, or the empty placeholder."""
    stripped = value.strip()
    return stripped if stripped else EMPTY_PLACEHOLDER


def playbook_to_markdown(playbook: _PlaybookLike, *, meeting_title: str) -> str:
    """Serialize a Playbook row into the spec-defined deterministic markdown.

    Layout:
        # {meeting_title}

        {free_form_markdown if non-empty}

        ## Objective
        {objective or _(empty)_}

        ## Counterparty Profile
        ...
    """
    parts: list[str] = [f"# {meeting_title}", ""]

    free_form = playbook.free_form_markdown.strip()
    if free_form:
        parts.extend([free_form, ""])

    for header, attr in _PLAYBOOK_SECTIONS:
        parts.append(f"## {header}")
        parts.append(_field_body(getattr(playbook, attr)))
        parts.append("")

    # Trim trailing blank lines down to a single newline terminator.
    while len(parts) > 1 and parts[-1] == "":
        parts.pop()
    return "\n".join(parts) + "\n"


def _speaker_label(speaker: str) -> str:
    """Map a stored `chunk.speaker` value to the display label per the glossary.

    `me` / `counterparty` are domain-glossary fixed labels. The clustering
    pipeline (slice-12) may emit `speaker_cluster_N` for unassigned voices —
    we surface those as `與會者 N` so non-attributed speakers still read
    naturally. Any other value passes through unchanged.
    """
    if speaker == "me":
        return "Me (我方)"
    if speaker == "counterparty":
        return "Counterparty (對方)"
    match = _SPEAKER_CLUSTER_RE.match(speaker)
    if match is not None:
        return f"與會者 {int(match.group(1))}"
    return speaker


def transcript_to_markdown(chunks: Iterable[_ChunkLike]) -> str:
    """Serialize TranscriptChunk rows into markdown per the spec contract.

    Empty input still produces the H1 header so consumers see a stable
    shape (the bundler always writes `transcript.md`, even for a silent
    meeting).
    """
    chunk_list = list(chunks)
    if not chunk_list:
        return "# Transcript\n"

    lines: list[str] = ["# Transcript", ""]
    for chunk in chunk_list:
        label = _speaker_label(chunk.speaker)
        # `strftime` here renders local-clock time per the chunk's tzinfo.
        # ASR pipeline stores `started_at` as UTC, but consumers only care
        # about HH:MM:SS — we do not localise here, keeping output stable.
        timestamp = chunk.started_at.strftime("%H:%M:%S")
        lines.append(f"**[{timestamp}] {label}**: {chunk.text}")
    return "\n".join(lines) + "\n"


def summary_to_markdown(summary: _SummaryLike) -> str:
    """Wrap an existing Summary.markdown payload under an `# Summary` H1.

    The bundler MUST NOT invoke this when `summary` is None — callers are
    responsible for skipping `summary.md` in that case.
    """
    return f"# Summary\n\n{summary.markdown}\n"


__all__ = [
    "EMPTY_PLACEHOLDER",
    "playbook_to_markdown",
    "summary_to_markdown",
    "transcript_to_markdown",
]
