"""AttachmentProcessor — slice-20c task 2.2.

Type-dispatched single-method deep module that turns an on-disk
attachment (image / PDF / docx / text / markdown) into the canonical
shape that `MultimodalContextBuilder` understands:

  - `image` → keep raw bytes (Gemini consumes binary as `Part.from_bytes`)
  - `pdf` / `docx` → extract text via pypdf / python-docx
  - `text` / `markdown` → read bytes, decode utf-8

Each call returns a `ProcessedAttachment(kind, bytes_, extracted_text,
sha256)` regardless of the input kind. `sha256` is computed over the raw
file bytes so the MultimodalContextBuilder can fold the digest into the
per-call snapshot hash.

PDF / docx extraction is capped by
`Settings.attachment_text_extraction_timeout_seconds` to avoid a single
corrupt file blocking the LLM call indefinitely.

Failures raise `AttachmentProcessingError` with a stable `error_code` so
upstream code can log+skip without tearing down the whole request.
"""

from __future__ import annotations

import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as _FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .exceptions import AttachmentProcessingError

ProcessedKind = Literal["image", "text"]


@dataclass(frozen=True)
class ProcessedAttachment:
    """Canonical shape consumed by `MultimodalContextBuilder`."""

    kind: ProcessedKind
    """`"image"` means treat as binary; `"text"` means feed `extracted_text` to the LLM."""

    bytes_: bytes | None
    """Raw file bytes — populated for images, `None` for text attachments."""

    extracted_text: str | None
    """Extracted UTF-8 text — populated for text attachments, `None` for images."""

    sha256: str
    """Hex digest of the raw file bytes — folded into the per-call snapshot hash."""

    mime_type: str | None = None
    """MIME type for image parts so the LLM can route to the right decoder."""

    source_name: str | None = None
    """Original filename — only used for human-readable headers in text parts."""


_PDF_KIND = "pdf"
_DOCX_KIND = "docx"
_TEXT_KIND = "text"
_MARKDOWN_KIND = "markdown"
_IMAGE_KIND = "image"

_MIME_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class AttachmentProcessor:
    """Extract LLM-ready content from a meeting attachment on disk.

    The class holds no state beyond the configured timeout; instantiate
    once per request (or memoize at module level — both are fine).
    """

    def __init__(self, *, text_extraction_timeout_seconds: int = 15) -> None:
        self._timeout = text_extraction_timeout_seconds

    def process(
        self,
        *,
        file_path: str | Path,
        kind: str,
        original_name: str | None = None,
    ) -> ProcessedAttachment:
        path = Path(file_path)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise AttachmentProcessingError(
                "attachment.extraction_failed",
                f"Failed to read attachment from disk: {exc}",
            ) from exc

        sha256 = hashlib.sha256(raw).hexdigest()

        if kind == _IMAGE_KIND:
            mime = _MIME_BY_EXTENSION.get(path.suffix.lower(), "image/png")
            return ProcessedAttachment(
                kind="image",
                bytes_=raw,
                extracted_text=None,
                sha256=sha256,
                mime_type=mime,
                source_name=original_name or path.name,
            )

        if kind in (_TEXT_KIND, _MARKDOWN_KIND):
            try:
                text = raw.decode("utf-8", errors="replace")
            except Exception as exc:  # pragma: no cover — decode("replace") never throws
                raise AttachmentProcessingError(
                    "attachment.extraction_failed",
                    f"Failed to decode text attachment as UTF-8: {exc}",
                ) from exc
            return ProcessedAttachment(
                kind="text",
                bytes_=None,
                extracted_text=text,
                sha256=sha256,
                source_name=original_name or path.name,
            )

        if kind == _PDF_KIND:
            text = self._extract_with_timeout(_extract_pdf_text, raw)
            return ProcessedAttachment(
                kind="text",
                bytes_=None,
                extracted_text=text,
                sha256=sha256,
                source_name=original_name or path.name,
            )

        if kind == _DOCX_KIND:
            text = self._extract_with_timeout(_extract_docx_text, raw)
            return ProcessedAttachment(
                kind="text",
                bytes_=None,
                extracted_text=text,
                sha256=sha256,
                source_name=original_name or path.name,
            )

        raise AttachmentProcessingError(
            "attachment.extraction_failed",
            f"Unsupported attachment kind: {kind!r}",
        )

    def _extract_with_timeout(self, fn, raw: bytes) -> str:
        """Run `fn(raw)` on a worker thread; raise on timeout / failure."""
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn, raw)
            try:
                return future.result(timeout=self._timeout)
            except _FutureTimeoutError as exc:
                future.cancel()
                raise AttachmentProcessingError(
                    "attachment.extraction_timeout",
                    f"Text extraction exceeded {self._timeout}s timeout",
                ) from exc
            except AttachmentProcessingError:
                raise
            except Exception as exc:
                raise AttachmentProcessingError(
                    "attachment.extraction_failed",
                    f"Text extraction failed: {exc}",
                ) from exc


def _extract_pdf_text(raw: bytes) -> str:
    """Pull text from every page of a PDF; concatenated with blank lines."""
    try:
        from pypdf import PdfReader  # imported lazily so the dep is optional in tests
    except ImportError as exc:  # pragma: no cover
        raise AttachmentProcessingError(
            "attachment.extraction_failed",
            "pypdf is not installed",
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(raw))
        parts = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p.strip() for p in parts if p.strip())
    except Exception as exc:
        raise AttachmentProcessingError(
            "attachment.extraction_failed",
            f"PDF text extraction failed: {exc}",
        ) from exc


def _extract_docx_text(raw: bytes) -> str:
    """Pull paragraph text from a .docx file via python-docx."""
    try:
        import docx  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover
        raise AttachmentProcessingError(
            "attachment.extraction_failed",
            "python-docx is not installed",
        ) from exc

    try:
        document = docx.Document(io.BytesIO(raw))
        return "\n".join(p.text for p in document.paragraphs if p.text.strip())
    except Exception as exc:
        raise AttachmentProcessingError(
            "attachment.extraction_failed",
            f"docx text extraction failed: {exc}",
        ) from exc
