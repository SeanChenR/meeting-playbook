"""Tag palette — slice-17 task 1.2.

Backend white-list of hex colors a tag may carry. Mirrored by the frontend
in `packages/web/src/lib/tag-palette.ts`; the test
`tests/tags/test_palette_parity.py` guarantees the two files stay in sync.

Any `color` value that is not present in `TAG_PALETTE_HEX` SHALL be rejected
by `TagRepository.create` / `.update` (router maps to HTTP 422
`tag.invalid_color`).
"""

from __future__ import annotations

from typing import Final

# Order matches packages/web/src/lib/tag-palette.ts.
TAG_PALETTE_HEX: Final[tuple[str, ...]] = (
    "#DDD6FE",
    "#BFDBFE",
    "#A7F3D0",
    "#FEF3C7",
    "#FBCFE8",
    "#E5E7EB",
    "#7C2D12",
    "#1E3A8A",
)


def is_palette_color(value: str) -> bool:
    """Case-insensitive membership check against the palette."""
    return value.lower() in {c.lower() for c in TAG_PALETTE_HEX}
