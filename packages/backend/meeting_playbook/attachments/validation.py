"""Meeting attachment upload validation — slice-20a task 2.1.

Per spec meeting-attachment ADDED requirement
"Upload validation enforces whitelist, per-meeting file count, and per-meeting
byte quota":

  (1) Content-Type ∉ mime whitelist AND extension ∉ extension whitelist
      → AttachmentValidationError("attachment.unsupported_format").
  (2) ≥ 10 active rows for this meeting → "attachment.too_many".
  (3) sum(existing bytes) + new bytes > 60 MiB → "attachment.quota_exceeded".

The 10 / 60 MiB caps were aligned with the per-user staging quota in slice-24
(design D12) — see openspec/specs/meeting-attachment/spec.md "Upload validation"
for the requirement text. Earlier values were 5 / 30 MiB (slice-20a).

When validation passes, the function returns the inferred `kind`:
  - mime first (per content_type whitelist mapping)
  - extension fallback when mime not in whitelist
"""

from __future__ import annotations

from os.path import splitext
from typing import Final, Literal, Protocol

AttachmentKind = Literal["image", "pdf", "docx", "text", "markdown"]


MAX_ATTACHMENTS_PER_MEETING: Final[int] = 10
MAX_BYTES_PER_MEETING: Final[int] = 60 * 1024 * 1024  # 60 MiB
# Slice-24 design D12: per-user staging quota equals the per-meeting cap
# so users see a consistent "10 / 60 MiB" mental model across both dropzones.
# Single-file size cap stays the same (MAX_BYTES_PER_MEETING) so a single
# 61 MiB file is rejected regardless of cumulative budget headroom.
MAX_STAGED_ATTACHMENTS_PER_USER: Final[int] = 10
MAX_STAGED_BYTES_PER_USER: Final[int] = 60 * 1024 * 1024  # 60 MiB


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


def validate_staging_upload(
    *,
    content_type: str,
    filename: str,
    declared_bytes: int,
    staged_count: int,
    staged_bytes: int,
) -> AttachmentKind:
    """Validate a per-user staging upload; return the inferred kind or raise.

    Same whitelist + MIME → kind mapping as `validate_upload`, but the
    quota check is per-user (slice-24 design D6 — 10 files / 60 MiB)
    rather than per-meeting. A single file still cannot exceed
    `MAX_BYTES_PER_MEETING` (60 MiB; aligned with per-meeting by D12).

    `staged_count` and `staged_bytes` are the user's current active
    staged totals BEFORE this upload — the handler should call
    `AttachmentRepository.count_staged_for_user` to source them.
    """
    kind = infer_kind(content_type, filename)
    if kind is None:
        raise AttachmentValidationError(
            "attachment.unsupported_format",
            f"Unsupported format: content_type={content_type!r}, filename={filename!r}",
        )

    # Per-file cap reuses the per-meeting byte limit so the frontend's
    # "file too large" message stays consistent across both upload paths.
    if int(declared_bytes) > MAX_BYTES_PER_MEETING:
        raise AttachmentValidationError(
            "attachment.quota_exceeded",
            f"Single-file size exceeds {MAX_BYTES_PER_MEETING} bytes (got {int(declared_bytes)}).",
        )

    if staged_count >= MAX_STAGED_ATTACHMENTS_PER_USER:
        raise AttachmentValidationError(
            "attachment.staging_quota_exceeded",
            f"Per-user staging file count limit ({MAX_STAGED_ATTACHMENTS_PER_USER}) reached.",
        )

    total = int(staged_bytes) + int(declared_bytes)
    if total > MAX_STAGED_BYTES_PER_USER:
        raise AttachmentValidationError(
            "attachment.staging_quota_exceeded",
            f"Per-user staging byte quota exceeded ({total} > {MAX_STAGED_BYTES_PER_USER}).",
        )

    return kind


__all__ = [
    "MAX_ATTACHMENTS_PER_MEETING",
    "MAX_BYTES_PER_MEETING",
    "MAX_STAGED_ATTACHMENTS_PER_USER",
    "MAX_STAGED_BYTES_PER_USER",
    "AttachmentKind",
    "AttachmentValidationError",
    "canonical_extension",
    "infer_kind",
    "validate_staging_upload",
    "validate_upload",
]
