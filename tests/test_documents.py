import io
import zipfile

import pytest

from app.services import documents as document_service
from app.services.documents import (
    DocumentExtractionError,
    chunk_text,
    document_content_type,
    extract_document,
    sanitize_filename,
)


def test_extracts_utf8_text() -> None:
    result = extract_document("notes.txt", b"hello   world\n\n\nsecond line")
    assert result.text == "hello world\n\nsecond line"
    assert result.ocr_used is False


def test_extracts_csv_rows_and_quoted_cells() -> None:
    result = extract_document("customers.csv", b'name,notes\nAda,"First, customer"\nLinus,Maintainer\n')

    assert result.text == "name notes\nAda First, customer\nLinus Maintainer"
    assert document_content_type("customers.csv", b"name,notes\n") == "text/csv; charset=utf-8"


def test_extracts_xlsx_cells() -> None:
    content = _xlsx_bytes(
        """<?xml version="1.0" encoding="UTF-8"?>
        <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
          <sheetData>
            <row r="1"><c r="A1" t="inlineStr"><is><t>Name</t></is></c><c r="B1" t="inlineStr"><is><t>Score</t></is></c></row>
            <row r="2"><c r="A2" t="inlineStr"><is><t>Ada</t></is></c><c r="B2"><v>98</v></c></row>
          </sheetData>
        </worksheet>"""
    )

    result = extract_document("scores.xlsx", content)

    assert result.text == "Sheet 1\nName Score\nAda 98"
    assert document_content_type("scores.xlsx", content) == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_chunks_preserve_all_content() -> None:
    text = " ".join(f"word-{index}" for index in range(100))
    chunks = chunk_text(text, size=120, overlap=20)
    assert len(chunks) > 1
    assert chunks[0].startswith("word-0")
    assert chunks[-1].endswith("word-99")


def test_sanitizes_path_traversal_filename() -> None:
    assert sanitize_filename("../../private/notes.txt") == "notes.txt"
    assert sanitize_filename("..\\private\\notes.txt") == "notes.txt"


def test_rejects_spoofed_pdf_content() -> None:
    with pytest.raises(DocumentExtractionError, match="does not match"):
        document_content_type("report.pdf", b"not a pdf")


def test_rejects_spoofed_xlsx_content() -> None:
    with pytest.raises(DocumentExtractionError, match="does not match"):
        document_content_type("report.xlsx", b"not a workbook")


def test_rejects_xlsx_with_oversized_archive_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(document_service, "MAX_XLSX_ENTRY_BYTES", 64)
    content = _xlsx_bytes("x" * 65)

    with pytest.raises(DocumentExtractionError, match="oversized"):
        extract_document("report.xlsx", content)


def _xlsx_bytes(sheet_xml: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", "<Types/>")
        workbook.writestr("xl/workbook.xml", "<workbook/>")
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()
