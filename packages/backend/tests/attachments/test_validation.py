"""Validation tests for slice-20a task 2.1.

Per spec meeting-attachment ADDED requirement
"Upload validation enforces whitelist, per-meeting file count, and per-meeting
byte quota":

  Whitelist + kind inference matrix (11 cases, per Example: table)
    - image/jpeg + proposal.jpg → image (accept)
    - image/png + screenshot.png → image (accept)
    - image/webp + chart.webp → image (accept)
    - image/bmp + legacy.bmp → reject attachment.unsupported_format
    - application/pdf + quote.pdf → pdf (accept)
    - docx mime + contract.docx → docx (accept)
    - application/msword + contract.doc → reject (legacy .doc excluded)
    - text/plain + agenda.txt → text (accept)
    - text/markdown + notes.md → markdown (accept)
    - application/octet-stream + notes.md → markdown (extension fallback)
    - application/octet-stream + data.bin → reject

  Per-meeting quota:
    - 6th attachment → attachment.too_many
    - cumulative bytes > 30 MiB → attachment.quota_exceeded
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class _Existing:
    """Lightweight stand-in for AttachmentRow used in validation tests.

    The real `validate_upload` only needs `.bytes` from each row in the
    cumulative-quota check and len() of the list for the count check, so
    a frozen dataclass keeps the test fixtures simple.
    """

    bytes: int


@pytest.mark.parametrize(
    "content_type,filename,expected_kind",
    [
        ("image/jpeg", "proposal.jpg", "image"),
        ("image/png", "screenshot.png", "image"),
        ("image/webp", "chart.webp", "image"),
        ("application/pdf", "quote.pdf", "pdf"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "contract.docx",
            "docx",
        ),
        ("text/plain", "agenda.txt", "text"),
        ("text/markdown", "notes.md", "markdown"),
        ("application/octet-stream", "notes.md", "markdown"),
    ],
)
def test_validate_upload_accepts_whitelisted_types(content_type, filename, expected_kind):
    """Each accepted (mime, filename) → returns the expected kind."""
    from meeting_playbook.attachments.validation import validate_upload

    kind = validate_upload(
        content_type=content_type,
        filename=filename,
        declared_bytes=1024,
        existing_attachments=[],
    )
    assert kind == expected_kind, f"{content_type} + {filename} should infer {expected_kind!r}"


@pytest.mark.parametrize(
    "content_type,filename",
    [
        ("image/bmp", "legacy.bmp"),
        ("application/msword", "contract.doc"),
        ("application/octet-stream", "data.bin"),
    ],
)
def test_validate_upload_rejects_non_whitelisted(content_type, filename):
    """Non-whitelisted mime + non-whitelisted extension → unsupported_format."""
    from meeting_playbook.attachments.validation import (
        AttachmentValidationError,
        validate_upload,
    )

    with pytest.raises(AttachmentValidationError) as exc_info:
        validate_upload(
            content_type=content_type,
            filename=filename,
            declared_bytes=1024,
            existing_attachments=[],
        )
    assert exc_info.value.error_code == "attachment.unsupported_format"


def test_validate_upload_rejects_sixth_attachment_with_too_many():
    """When the meeting already has 5 active attachments, the 6th is rejected."""
    from meeting_playbook.attachments.validation import (
        AttachmentValidationError,
        validate_upload,
    )

    existing = [_Existing(bytes=1024) for _ in range(5)]
    with pytest.raises(AttachmentValidationError) as exc_info:
        validate_upload(
            content_type="application/pdf",
            filename="sixth.pdf",
            declared_bytes=1024,
            existing_attachments=existing,
        )
    assert exc_info.value.error_code == "attachment.too_many"


def test_validate_upload_rejects_when_cumulative_bytes_exceed_30_mib():
    """Sum of existing + new bytes > 30 MiB → quota_exceeded."""
    from meeting_playbook.attachments.validation import (
        AttachmentValidationError,
        validate_upload,
    )

    # 3 existing rows totalling 28 MiB; new 3 MiB upload pushes to 31 MiB.
    existing = [_Existing(bytes=int(28 * 1024 * 1024 / 3)) for _ in range(3)]
    with pytest.raises(AttachmentValidationError) as exc_info:
        validate_upload(
            content_type="application/pdf",
            filename="big.pdf",
            declared_bytes=3 * 1024 * 1024,
            existing_attachments=existing,
        )
    assert exc_info.value.error_code == "attachment.quota_exceeded"


def test_validate_upload_quota_boundary_exactly_30_mib_accepted():
    """A new file whose total reaches exactly 30 MiB is accepted (boundary)."""
    from meeting_playbook.attachments.validation import validate_upload

    existing = [_Existing(bytes=20 * 1024 * 1024)]  # 20 MiB
    kind = validate_upload(
        content_type="application/pdf",
        filename="boundary.pdf",
        declared_bytes=10 * 1024 * 1024,  # +10 MiB → exactly 30 MiB
        existing_attachments=existing,
    )
    assert kind == "pdf"
