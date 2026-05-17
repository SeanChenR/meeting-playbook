"""Meeting attachment upload validation — slice-20a task 2.1.

Per spec meeting-attachment ADDED requirement
"Upload validation enforces whitelist, per-meeting file count, and per-meeting
byte quota":

  (1) Content-Type ∉ mime whitelist AND extension ∉ extension whitelist
      → AttachmentValidationError("attachment.unsupported_format").
  (2) ≥ 5 active rows for this meeting → "attachment.too_many".
  (3) sum(existing bytes) + new bytes > 30 MiB → "attachment.quota_exceeded".

When validation passes, the function returns the inferred `kind`:
  - mime first (per content_type whitelist mapping)
  - extension fallback when mime not in whitelist
"""

from __future__ import annotations

from os.path import splitext
from typing import Final, Literal, Protocol

AttachmentKind = Literal["image", "pdf", "docx", "text", "markdown"]


MAX_ATTACHMENTS_PER_MEETING: Final[int] = 5
MAX_BYTES_PER_MEETING: Final[int] = 30 * 1024 * 1024  # 30 MiB


_MIME_TO_KIND: Final[dict[str, AttachmentKind]] = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "text",
    "text/markdown": "markdown",
}

_EXTENSION_TO_KIND: Final[dict[str, AttachmentKind]] = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
}


_KIND_TO_CANONICAL_EXTENSION: Final[dict[AttachmentKind, str]] = {
    "image": ".bin",  # filled in dynamically based on the actual mime / ext
    "pdf": ".pdf",
    "docx": ".docx",
    "text": ".txt",
    "markdown": ".md",
}


class _BytesCarrier(Protocol):
    """Anything carrying a `bytes` attribute (int) — typically `MeetingAttachment`.

    The validator only needs `.bytes` from each existing row to enforce
    the cumulative quota, so we keep the contract minimal.
    """

    bytes: int


class AttachmentValidationError(Exception):
    """Raised when an upload fails validation.

    Carries `error_code` (one of `attachment.unsupported_format`,
    `attachment.too_many`, `attachment.quota_exceeded`) so the HTTP layer
    can map it to a stable 422 envelope.
    """

    def __init__(self, error_code: str, message: str = "") -> None:
        self.error_code = error_code
        super().__init__(message or error_code)


def infer_kind(content_type: str, filename: str) -> AttachmentKind | None:
    """Return the inferred kind, or None when neither mime nor extension match.

    Pure function — no I/O, no side effects. Mime check runs first (case-
    insensitive, parameters stripped); on miss, falls back to extension.
    """
    mime = (content_type or "").lower().split(";")[0].strip()
    if mime in _MIME_TO_KIND:
        return _MIME_TO_KIND[mime]
    ext = splitext(filename or "")[1].lower()
    return _EXTENSION_TO_KIND.get(ext)


def canonical_extension(kind: AttachmentKind, filename: str, content_type: str) -> str:
    """Return the canonical on-disk extension for a given kind.

    `image` defers to the original extension (.jpg / .png / .webp) so the
    persisted file mime-sniffs the same way the browser would. Other kinds
    have a single canonical form.
    """
    if kind == "image":
        ext = splitext(filename or "")[1].lower()
        if ext in {".jpg", ".jpeg", ".png", ".webp"}:
            return ext
        # Fall back to mime → extension
        mime = (content_type or "").lower().split(";")[0].strip()
        if mime == "image/jpeg":
            return ".jpg"
        if mime == "image/png":
            return ".png"
        if mime == "image/webp":
            return ".webp"
        return ".bin"  # unreachable for whitelist-validated uploads
    return _KIND_TO_CANONICAL_EXTENSION[kind]


def validate_upload(
    *,
    content_type: str,
    filename: str,
    declared_bytes: int,
    existing_attachments: list[_BytesCarrier],
) -> AttachmentKind:
    """Validate an incoming upload; return the inferred kind or raise.

    `existing_attachments` should be the meeting's active rows (those with
    `deleted_at IS NULL`) so both per-meeting count and per-meeting byte
    quota checks compare against the correct slice of the table.
    """
    kind = infer_kind(content_type, filename)
    if kind is None:
        raise AttachmentValidationError(
            "attachment.unsupported_format",
            f"Unsupported format: content_type={content_type!r}, filename={filename!r}",
        )

    if len(existing_attachments) >= MAX_ATTACHMENTS_PER_MEETING:
        raise AttachmentValidationError(
            "attachment.too_many",
            f"Per-meeting attachment limit ({MAX_ATTACHMENTS_PER_MEETING}) reached.",
        )

    total = sum(int(a.bytes) for a in existing_attachments) + int(declared_bytes)
    if total > MAX_BYTES_PER_MEETING:
        raise AttachmentValidationError(
            "attachment.quota_exceeded",
            f"Per-meeting byte quota exceeded ({total} > {MAX_BYTES_PER_MEETING}).",
        )

    return kind


__all__ = [
    "AttachmentKind",
    "AttachmentValidationError",
    "MAX_ATTACHMENTS_PER_MEETING",
    "MAX_BYTES_PER_MEETING",
    "canonical_extension",
    "infer_kind",
    "validate_upload",
]
