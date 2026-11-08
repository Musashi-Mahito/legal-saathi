"""Upload validation, in-memory text extraction and chunking.

Uploaded files are processed from bytes in memory and never written to disk.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import config
from checks import scan_injection

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".txt"})
MIN_PDF_CHARS = 200
MAX_FILENAME_CHARS = 120

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SENTENCE_RE = re.compile(r"(?<=[.!?\u0964])\s+")


class DocError(Exception):
    """A document could not be accepted or read."""

    code = "bad_request"


class FileTooLarge(DocError):
    """The upload is larger than ``MAX_UPLOAD_MB``."""

    code = "file_too_large"


class UnsupportedType(DocError):
    """The upload is not a supported, matching file type."""

    code = "unsupported_type"


class EmptyDocument(DocError):
    """No text could be extracted."""

    code = "empty_document"


class ScannedPdfUnsupported(DocError):
    """The PDF looks like a scan with almost no text layer."""

    code = "scanned_pdf_unsupported"


@dataclass
class ExtractResult:
    """Text pulled out of an upload, plus what the user should know."""

    text: str
    pages: int | None
    truncated: bool
    warnings: list[str] = field(default_factory=list)


def sanitize_filename(name: str) -> str:
    """Return a display-only filename with no path or control characters."""
    base = (name or "document").replace("\\", "/").split("/")[-1]
    base = _CONTROL_RE.sub("", base).strip() or "document"
    return base[:MAX_FILENAME_CHARS]


def _check_magic(ext: str, data: bytes) -> None:
    """Reject files whose bytes do not match their extension."""
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise UnsupportedType("This file is not a valid PDF.")
    if ext == ".docx" and not (data.startswith(b"PK") and b"word/document.xml" in data):
        raise UnsupportedType("This file is not a valid DOCX document.")
    if ext == ".txt" and b"\x00" in data[:2048]:
        raise UnsupportedType("This file is not a plain text file.")


def _decode_text(data: bytes) -> str:
    """Decode an uploaded text file, trying the encodings we support."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnsupportedType("This text file could not be read.")


def validate_upload(filename: str, data: bytes) -> str:
    """Validate an upload and return its extension."""
    ext = ("." + (filename or "").rsplit(".", 1)[-1].lower()) if "." in (filename or "") else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedType("Only PDF, DOCX and TXT files are supported.")
    if not data:
        raise EmptyDocument("The file is empty.")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise FileTooLarge(f"Files must be {config.MAX_UPLOAD_MB} MB or smaller.")
    _check_magic(ext, data)
    return ext


def clean_text(text: str) -> str:
    """Normalize line endings, drop control characters and squeeze blank lines."""
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = _CONTROL_RE.sub("", normalized)
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _extract_pdf(data: bytes) -> ExtractResult:
    """Extract text from a PDF with page markers."""
    import pdfplumber

    warnings: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            total_pages = len(pdf.pages)
            pages = pdf.pages[: config.MAX_PDF_PAGES]
            parts = []
            for index, page in enumerate(pages, start=1):
                parts.append(f"\n[Page {index}]\n{(page.extract_text() or '').strip()}")
    except Exception as exc:
        raise UnsupportedType("This PDF could not be read.") from exc
    truncated = total_pages > config.MAX_PDF_PAGES
    if truncated:
        warnings.append("only_the_first_pages_were_read")
    text = clean_text("\n".join(parts))
    if len(text) < MIN_PDF_CHARS:
        raise ScannedPdfUnsupported(
            "This PDF has almost no selectable text. Scanned PDFs and photos are not supported."
        )
    return ExtractResult(text=text, pages=min(total_pages, config.MAX_PDF_PAGES),
                         truncated=truncated, warnings=warnings)


def _extract_docx(data: bytes) -> ExtractResult:
    """Extract paragraphs and table cells from a DOCX file."""
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise UnsupportedType("This DOCX file could not be read.") from exc
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return ExtractResult(text=clean_text("\n".join(parts)), pages=None, truncated=False)


def extract_text(data: bytes, ext: str) -> ExtractResult:
    """Extract readable text from validated upload bytes."""
    if ext == ".pdf":
        result = _extract_pdf(data)
    elif ext == ".docx":
        result = _extract_docx(data)
    else:
        result = ExtractResult(text=clean_text(_decode_text(data)), pages=None, truncated=False)
    if not result.text:
        raise EmptyDocument("No readable text was found in this file.")
    if len(result.text) > config.MAX_DOC_CHARS:
        result.text = result.text[: config.MAX_DOC_CHARS]
        result.truncated = True
        result.warnings.append("text_was_truncated")
    return result


def _split_units(paragraph: str, size: int) -> list[str]:
    """Split one oversized paragraph into units no longer than ``size``."""
    if len(paragraph) <= size:
        return [paragraph]
    units: list[str] = []
    for sentence in _SENTENCE_RE.split(paragraph):
        candidate = sentence
        while len(candidate) > size:
            units.append(candidate[:size])
            candidate = candidate[size:]
        if candidate.strip():
            units.append(candidate)
    return units


def chunk_text(
    text: str,
    size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks that keep page markers intact."""
    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text or ""):
        stripped = paragraph.strip()
        if stripped:
            units.extend(_split_units(stripped, size))
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        prefix = chunks[-1][-overlap:] if chunks and overlap > 0 else ""
        current = f"{prefix}\n{unit}" if prefix else unit
    if current:
        chunks.append(current)
    return chunks


def injection_flags(text: str) -> list[str]:
    """Flag text that looks like an instruction aimed at the assistant."""
    return ["possible_prompt_injection"] if scan_injection(text) else []
