"""Palette parity — slice-17 task 1.2.

The frontend `packages/web/src/lib/tag-palette.ts` and backend
`packages/backend/meeting_playbook/tags/colors.py` must hold the SAME hex
white-list so the server can validate `tag.color` values posted by the
client. This test reads both files and asserts the two lists are equal.
"""

from __future__ import annotations

import re
from pathlib import Path

from meeting_playbook.tags.colors import TAG_PALETTE_HEX


_REPO_ROOT = Path(__file__).resolve().parents[4]
_FRONTEND_PALETTE_FILE = _REPO_ROOT / "packages/web/src/lib/tag-palette.ts"


def _parse_frontend_palette() -> list[str]:
    """Extract the hex strings from the TypeScript palette array literal."""
    src = _FRONTEND_PALETTE_FILE.read_text(encoding="utf-8")
    block_match = re.search(
        r"TAG_PALETTE.*?=\s*\[(.+?)\]\s*as const",
        src,
        re.DOTALL,
    )
    assert block_match, "Could not locate TAG_PALETTE block in tag-palette.ts"
    block = block_match.group(1)
    return re.findall(r'"(#[0-9A-Fa-f]{6})"', block)


def test_frontend_and_backend_palettes_match() -> None:
    frontend = _parse_frontend_palette()
    assert len(frontend) == 8, f"Frontend palette must have 8 entries, got {len(frontend)}"
    assert frontend == list(TAG_PALETTE_HEX), (
        "tag-palette.ts and meeting_playbook/tags/colors.py drifted; keep them in sync"
    )
