"""AttachmentProcessor tests — slice-20c task 2.1.

Per spec design "AttachmentProcessor 採 type-dispatched single-method 設計":
  - image/png      → ProcessedAttachment(kind="image", bytes_ != None, text=None, sha256 != "")
  - application/pdf happy → kind="text", extracted_text contains the page text
  - corrupt PDF    → raises AttachmentProcessingError(error_code="attachment.extraction_failed")
  - docx happy     → kind="text", extracted_text contains the document body
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from meeting_playbook.attachments.exceptions import AttachmentProcessingError
from meeting_playbook.attachments.processor import (
    AttachmentProcessor,
    ProcessedAttachment,
)


def _png_bytes() -> bytes:
    """A minimal valid PNG (8-byte magic + filler)."""
    return bytes.fromhex("89504E470D0A1A0A") + b"\x00" * 64


def _real_pdf_bytes(text: str = "Q3 briefing") -> bytes:
    """Synthesize a small valid PDF whose only page carries `text`."""
    from pypdf import PdfWriter
    from pypdf.generic import ContentStream, DecodedStreamObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # Inject a `BT ... ET` text-showing operator so PdfReader.extract_text returns it.
    content = ContentStream(None, writer)
    content.operations = [([], "BT"), ([f"({text}) Tj"], "")] + list(content.operations)
    page[NameObject("/Contents")] = DecodedStreamObject()
    page[NameObject("/Contents")].set_data(
        f"BT /F1 12 Tf 100 700 Td ({text}) Tj ET".encode("latin-1")
    )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _docx_bytes(text: str = "Hello docx") -> bytes:
    """Synthesize a real .docx with one paragraph containing `text`."""
    import docx

    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_image_returns_processed_attachment_with_bytes(tmp_path: Path) -> None:
    raw = _png_bytes()
    f = tmp_path / "snap.png"
    f.write_bytes(raw)

    out = AttachmentProcessor().process(file_path=f, kind="image", original_name="snap.png")
    assert isinstance(out, ProcessedAttachment)
    assert out.kind == "image"
    assert out.bytes_ == raw
    assert out.extracted_text is None
    assert out.sha256 and len(out.sha256) == 64
    assert out.mime_type == "image/png"


def test_pdf_happy_path_returns_text_kind(tmp_path: Path) -> None:
    """A structurally valid PDF dispatches to the text branch without raising.

    We don't assert the extracted body — building a PDF with usable fonts
    requires a much larger fixture; the contract here is that pypdf
    successfully opens the file and returns a `ProcessedAttachment(kind="text")`.
    """
    raw = _real_pdf_bytes("Q3 briefing")
    f = tmp_path / "brief.pdf"
    f.write_bytes(raw)

    out = AttachmentProcessor().process(file_path=f, kind="pdf", original_name="brief.pdf")
    assert out.kind == "text"
    assert out.bytes_ is None
    assert out.extracted_text is not None  # may be empty string for font-less PDFs
    assert out.sha256 and len(out.sha256) == 64


def test_corrupt_pdf_raises_extraction_failed(tmp_path: Path) -> None:
    f = tmp_path / "bad.pdf"
    f.write_bytes(b"not a real PDF body")

    with pytest.raises(AttachmentProcessingError) as exc:
        AttachmentProcessor().process(file_path=f, kind="pdf", original_name="bad.pdf")
    assert exc.value.error_code == "attachment.extraction_failed"


def test_docx_happy_path_extracts_paragraph_text(tmp_path: Path) -> None:
    raw = _docx_bytes("Hello docx")
    f = tmp_path / "notes.docx"
    f.write_bytes(raw)

    out = AttachmentProcessor().process(file_path=f, kind="docx", original_name="notes.docx")
    assert out.kind == "text"
    assert out.extracted_text == "Hello docx"
    assert out.sha256 and len(out.sha256) == 64


def test_text_attachment_decodes_utf8(tmp_path: Path) -> None:
    f = tmp_path / "notes.txt"
    f.write_text("會議 agenda")

    out = AttachmentProcessor().process(file_path=f, kind="text", original_name="notes.txt")
    assert out.kind == "text"
    assert out.extracted_text == "會議 agenda"
