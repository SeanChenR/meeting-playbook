"""MultimodalContextBuilder — slice-20c task 3.2.

Turns `(text_context, [Attachment, ...])` into the canonical input shape
that google-genai expects: an ordered list of `Part` objects. Order is
deterministic — **images first**, then a combined text part, then the
trailing system text context — so the LLM sees images before the
language scaffolding that describes them.

The builder also computes a `snapshot_hash` covering:
  - the set of `(attachment_id, sha256)` tuples (sorted to be
    permutation-invariant)
  - the `text_context` string

The hash is later persisted into `playbook.attachment_hash_snapshot` /
`summary.attachment_hash_snapshot` so the frontend can compute a
"changed since the last generation" boolean by comparing the current
attachment set's snapshot against the stored value.

Failures from `AttachmentProcessor.process(...)` are logged with a
structured warning and the offending attachment is skipped — the rest
of the call proceeds, satisfying the slice contract "single corrupt
attachment doesn't block the whole generation".
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .exceptions import AttachmentProcessingError
from .processor import AttachmentProcessor, ProcessedAttachment

_log = logging.getLogger(__name__)


@runtime_checkable
class AttachmentRef(Protocol):
    """Minimal protocol the builder consumes — works for both ORM models and DTOs."""

    @property
    def id(self) -> str: ...

    @property
    def kind(self) -> str: ...

    @property
    def file_path(self) -> str: ...

    @property
    def original_name(self) -> str: ...


@dataclass(frozen=True)
class MultimodalContext:
    """Built context: ordered LLM `parts` + a content-addressable snapshot hash."""

    parts: list[Any]
    """Ordered list of google-genai `Part` objects. Length is at least 1 (text)."""

    snapshot_hash: str
    """SHA-256 hex digest over the canonical (id, sha256) set + text_context."""

    skipped_attachment_ids: list[str] = field(default_factory=list)
    """Ids of attachments whose `AttachmentProcessor.process(...)` raised."""


# Canonical SHA-256 of the empty string — used when no attachments are
# attached so the snapshot hash for "no attachments + same text" is
# stable across calls.
EMPTY_SET_SNAPSHOT_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class MultimodalContextBuilder:
    """Builder that flattens attachments into google-genai `Part` lists."""

    def __init__(self, processor: AttachmentProcessor) -> None:
        self._processor = processor

    def build(
        self,
        *,
        text_context: str,
        attachments: list[AttachmentRef] | None = None,
    ) -> MultimodalContext:
        attachments = attachments or []

        processed: list[ProcessedAttachment] = []
        processed_ids: list[str] = []  # parallel array — same length as `processed`
        skipped: list[str] = []

        for att in attachments:
            try:
                pa = self._processor.process(
                    file_path=att.file_path,
                    kind=att.kind,
                    original_name=att.original_name,
                )
                processed.append(pa)
                processed_ids.append(att.id)
            except AttachmentProcessingError as exc:
                _log.warning(
                    "attachment_processing_skipped",
                    extra={
                        "attachment_id": att.id,
                        "error_code": exc.error_code,
                        "exc_message": str(exc),
                    },
                )
                skipped.append(att.id)
                continue

        parts = self._compose_parts(processed=processed, text_context=text_context)

        # Snapshot hash covers ONLY the attachment set — not `text_context`.
        # Spec scenario "empty set → canonical empty-set hash" requires the
        # digest to fall back to SHA-256('') when there are no processable
        # attachments, regardless of text changes.
        pairs = [(att_id, pa.sha256) for att_id, pa in zip(processed_ids, processed, strict=True)]
        snapshot_hash = (
            EMPTY_SET_SNAPSHOT_HASH
            if not pairs
            else hashlib.sha256(self._snapshot_input(pairs).encode("utf-8")).hexdigest()
        )

        return MultimodalContext(
            parts=parts,
            snapshot_hash=snapshot_hash,
            skipped_attachment_ids=skipped,
        )

    @staticmethod
    def _compose_parts(*, processed: list[ProcessedAttachment], text_context: str) -> list[Any]:
        """Materialize google-genai `Part`s in spec order (images → text → trailing text_context).

        Importing `google.genai.types` lazily so unit tests that mock the
        builder do not need the real SDK.
        """
        from google.genai import types  # imported lazily — see docstring

        parts: list[Any] = []

        # Image binary parts first — Gemini consumes them as `Part.from_bytes`.
        text_blocks: list[str] = []
        for pa in processed:
            if pa.kind == "image" and pa.bytes_ is not None:
                parts.append(
                    types.Part.from_bytes(
                        data=pa.bytes_,
                        mime_type=pa.mime_type or "application/octet-stream",
                    )
                )
            elif pa.kind == "text" and pa.extracted_text:
                header = f"[Attachment: {pa.source_name}]" if pa.source_name else "[Attachment]"
                text_blocks.append(f"{header}\n{pa.extracted_text}")

        combined_text = "\n\n".join([*text_blocks, text_context]) if text_blocks else text_context
        parts.append(types.Part.from_text(text=combined_text))
        return parts

    @staticmethod
    def _snapshot_input(attachment_pairs: list[tuple[str, str]]) -> str:
        """Stable string form of the (sorted) attachment set."""
        return "|".join(f"{aid}:{digest}" for aid, digest in sorted(attachment_pairs))


def compute_attachment_snapshot_hash(
    attachments: list[AttachmentRef] | None,
    *,
    processor: AttachmentProcessor | None = None,
) -> str:
    """Compute the canonical snapshot hash for a meeting's attachment set.

    Used by callers (router / generator) that only need the hash and not
    the LLM `parts` payload — for example, when upserting a playbook row
    with the snapshot column but without re-running the LLM.

    Each attachment is hashed by SHA-256 of its on-disk bytes; pairs are
    sorted by attachment id so two equivalent sets in different listing
    orders produce the same digest. Errors from individual attachments
    are swallowed so a single corrupt file doesn't break the hash
    calculation; the matching file is logged-and-skipped, same as during
    a multimodal call.
    """
    if not attachments:
        return EMPTY_SET_SNAPSHOT_HASH

    proc = processor or AttachmentProcessor()
    pairs: list[tuple[str, str]] = []
    for att in attachments:
        try:
            processed = proc.process(
                file_path=att.file_path,
                kind=att.kind,
                original_name=att.original_name,
            )
            pairs.append((att.id, processed.sha256))
        except AttachmentProcessingError as exc:
            _log.warning(
                "attachment_snapshot_skipped",
                extra={
                    "attachment_id": att.id,
                    "error_code": exc.error_code,
                    "exc_message": str(exc),
                },
            )
            continue
    if not pairs:
        return EMPTY_SET_SNAPSHOT_HASH
    sorted_pairs = sorted(pairs)
    blob = "|".join(f"{aid}:{digest}" for aid, digest in sorted_pairs)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
