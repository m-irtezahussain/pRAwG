from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from docx import Document
from pdf2image import convert_from_bytes
from pypdf import PdfReader


class DocumentExtractionError(ValueError):
    pass


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    ocr_used: bool


def extract_document(filename: str, content: bytes) -> ExtractedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(content)
    if suffix == ".docx":
        return _extract_docx(content)
    if suffix in {".txt", ".md"}:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError("Text files must use UTF-8 encoding") from exc
        return _finalize(text, ocr_used=False)
    raise DocumentExtractionError("Supported file types are PDF, DOCX, TXT, and Markdown")


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _extract_pdf(content: bytes) -> ExtractedDocument:
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise DocumentExtractionError("The PDF could not be read") from exc

    pages: list[str] = []
    ocr_used = False
    for page_number, page in enumerate(reader.pages, start=1):
        extracted = (page.extract_text() or "").strip()
        if len(extracted) < 20:
            try:
                images = convert_from_bytes(
                    content,
                    dpi=200,
                    first_page=page_number,
                    last_page=page_number,
                    fmt="png",
                    thread_count=1,
                )
                extracted = "\n".join(pytesseract.image_to_string(image) for image in images).strip()
                ocr_used = True
            except Exception as exc:
                raise DocumentExtractionError(f"OCR failed for PDF page {page_number}") from exc
        if extracted:
            pages.append(extracted)

    return _finalize("\n\n".join(pages), ocr_used=ocr_used)


def _extract_docx(content: bytes) -> ExtractedDocument:
    try:
        document = Document(io.BytesIO(content))
    except Exception as exc:
        raise DocumentExtractionError("The DOCX file could not be read") from exc
    text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    return _finalize(text, ocr_used=False)


def _finalize(text: str, ocr_used: bool) -> ExtractedDocument:
    normalized = re.sub(r"[ \t]+", " ", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        raise DocumentExtractionError("No readable text was found in the document")
    return ExtractedDocument(text=normalized, ocr_used=ocr_used)
