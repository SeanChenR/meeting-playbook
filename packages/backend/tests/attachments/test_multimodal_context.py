"""MultimodalContextBuilder tests — slice-20c task 3.1.

Per spec design `TDD 四條主路徑 table-driven`:
  - no_attachments → snapshot_hash == canonical empty-set hash
  - input order invariant
  - input content change → hash changes
  - mixed kinds → Parts list has images first, then combined text

Plus the explicit `EMPTY_SET_SNAPSHOT_HASH` constant equals SHA-256('') for
parity with the standalone helper.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from meeting_playbook.attachments.multimodal_context import (
    EMPTY_SET_SNAPSHOT_HASH,
    MultimodalContextBuilder,
    compute_attachment_snapshot_hash,
)
from meeting_playbook.attachments.processor import AttachmentProcessor


@dataclass(frozen=True)
class _Ref:
    """Minimal AttachmentRef stand-in for tests."""

    id: str
    kind: str
    file_path: str
    original_name: str


def _png(tmp_path: Path, name: str, payload: bytes) -> _Ref:
    p = tmp_path / name
    p.write_bytes(bytes.fromhex("89504E470D0A1A0A") + payload)
    return _Ref(id=f"att_{name}", kind="image", file_path=str(p), original_name=name)


def _text(tmp_path: Path, name: str, body: str) -> _Ref:
    p = tmp_path / name
    p.write_text(body)
    return _Ref(id=f"att_{name}", kind="text", file_path=str(p), original_name=name)


def test_empty_set_snapshot_hash_matches_sha256_of_empty_string() -> None:
    """The canonical empty-set hash MUST equal SHA-256 of the empty string.

    Tests that compare snapshots against the constant catch any future
    accidental change to the constant.
    """
    assert hashlib.sha256(b"").hexdigest() == EMPTY_SET_SNAPSHOT_HASH


def test_no_attachments_returns_canonical_empty_set_hash(tmp_path: Path) -> None:
    builder = MultimodalContextBuilder(AttachmentProcessor())
    out = builder.build(text_context="meeting context", attachments=[])
    assert out.snapshot_hash == EMPTY_SET_SNAPSHOT_HASH
    assert out.skipped_attachment_ids == []


def test_compute_helper_matches_builder_hash(tmp_path: Path) -> None:
    """The standalone helper produces the same hash as the builder."""
    refs = [_png(tmp_path, "a.png", b"\x00" * 32), _text(tmp_path, "b.txt", "hello")]
    helper_hash = compute_attachment_snapshot_hash(refs)

    builder = MultimodalContextBuilder(AttachmentProcessor())
    out = builder.build(text_context="ignored for snapshot", attachments=refs)
    assert out.snapshot_hash == helper_hash


def test_hash_is_invariant_under_input_order(tmp_path: Path) -> None:
    a = _png(tmp_path, "a.png", b"\x00" * 32)
    b = _text(tmp_path, "b.txt", "hello")
    h1 = compute_attachment_snapshot_hash([a, b])
    h2 = compute_attachment_snapshot_hash([b, a])
    assert h1 == h2


def test_hash_changes_when_attachment_content_changes(tmp_path: Path) -> None:
    a = _text(tmp_path, "a.txt", "first")
    h1 = compute_attachment_snapshot_hash([a])
    # rewrite the file in place — same id but different bytes
    Path(a.file_path).write_text("second")
    h2 = compute_attachment_snapshot_hash([a])
    assert h1 != h2


def test_skipped_ids_reported_for_corrupt_attachment(tmp_path: Path) -> None:
    """A corrupt PDF in the input set is logged + skipped, not raised."""
    ok = _text(tmp_path, "ok.md", "# notes")
    bad = _Ref(
        id="att_bad",
        kind="pdf",
        file_path=str(tmp_path / "missing.pdf"),  # file doesn't exist → OSError
        original_name="missing.pdf",
    )
    builder = MultimodalContextBuilder(AttachmentProcessor())
    out = builder.build(text_context="ctx", attachments=[ok, bad])
    assert "att_bad" in out.skipped_attachment_ids
    # snapshot reflects ONLY the ok attachment
    expected = compute_attachment_snapshot_hash([ok])
    assert out.snapshot_hash == expected
