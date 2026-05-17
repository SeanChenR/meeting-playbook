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


# ─── Slice-24: per-user staging quota (10 files / 60 MiB) ─────────────


def test_validate_staging_upload_accepts_within_quota():
    """Within the per-user staging quota (<10 files, <60 MiB total)."""
    from meeting_playbook.attachments.validation import validate_staging_upload

    kind = validate_staging_upload(
        content_type="application/pdf",
        filename="ok.pdf",
        declared_bytes=1024,
        staged_count=3,
        staged_bytes=10 * 1024 * 1024,  # 10 MiB so far
    )
    assert kind == "pdf"


def test_validate_staging_upload_rejects_eleventh_file():
    """The 11th staged file is rejected with attachment.staging_quota_exceeded."""
    from meeting_playbook.attachments.validation import (
        AttachmentValidationError,
        validate_staging_upload,
    )

    with pytest.raises(AttachmentValidationError) as exc_info:
        validate_staging_upload(
            content_type="application/pdf",
            filename="eleventh.pdf",
            declared_bytes=1024,
            staged_count=10,
            staged_bytes=1024,
        )
    assert exc_info.value.error_code == "attachment.staging_quota_exceeded"


def test_validate_staging_upload_rejects_over_60_mib_total():
    """Sum of existing staged + new > 60 MiB → staging_quota_exceeded."""
    from meeting_playbook.attachments.validation import (
        AttachmentValidationError,
        validate_staging_upload,
    )

    with pytest.raises(AttachmentValidationError) as exc_info:
        validate_staging_upload(
            content_type="application/pdf",
            filename="big.pdf",
            declared_bytes=5 * 1024 * 1024,  # +5 MiB on top of 58 MiB → 63 MiB
            staged_count=5,
            staged_bytes=58 * 1024 * 1024,
        )
    assert exc_info.value.error_code == "attachment.staging_quota_exceeded"


def test_validate_staging_upload_quota_boundary_exactly_60_mib_accepted():
    """Sum exactly equal to 60 MiB is accepted (boundary)."""
    from meeting_playbook.attachments.validation import validate_staging_upload

    kind = validate_staging_upload(
        content_type="application/pdf",
        filename="boundary.pdf",
        declared_bytes=20 * 1024 * 1024,  # +20 MiB on top of 40 MiB → exactly 60 MiB
        staged_count=4,
        staged_bytes=40 * 1024 * 1024,
    )
    assert kind == "pdf"


def test_validate_staging_upload_rejects_unsupported_mime():
    """Whitelist check runs BEFORE quota check; non-whitelisted MIME still rejects."""
    from meeting_playbook.attachments.validation import (
        AttachmentValidationError,
        validate_staging_upload,
    )

    with pytest.raises(AttachmentValidationError) as exc_info:
        validate_staging_upload(
            content_type="application/zip",
            filename="weird.zip",
            declared_bytes=100,
            staged_count=0,
            staged_bytes=0,
        )
    assert exc_info.value.error_code == "attachment.unsupported_format"


def test_validate_staging_upload_rejects_single_file_over_30_mib():
    """Per-file size cap (30 MiB) still applies to staging uploads."""
    from meeting_playbook.attachments.validation import (
        AttachmentValidationError,
        validate_staging_upload,
    )

    with pytest.raises(AttachmentValidationError) as exc_info:
        validate_staging_upload(
            content_type="application/pdf",
            filename="huge.pdf",
            declared_bytes=31 * 1024 * 1024,
            staged_count=0,
            staged_bytes=0,
        )
    # Per-file cap reuses the existing per-meeting quota_exceeded code so
    # the frontend's "file too large" message stays consistent.
    assert exc_info.value.error_code == "attachment.quota_exceeded"
