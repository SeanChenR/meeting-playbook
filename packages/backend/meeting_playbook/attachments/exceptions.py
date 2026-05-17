"""Attachment processing exceptions — slice-20c task 2.2.

Surfaces a single `AttachmentProcessingError` carrying a stable
`error_code` so callers (PlaybookGenerator / VertexProSummarizer) can
log + skip a single bad attachment without aborting the whole multimodal
LLM call.
"""

from __future__ import annotations


class AttachmentProcessingError(Exception):
    """Raised by `AttachmentProcessor.process(...)` on a per-attachment failure.

    `error_code` is one of `"attachment.extraction_failed"` /
    `"attachment.extraction_timeout"`. Callers should log a structured
    warning containing the attachment id + `error_code` and skip the row.
    """

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
