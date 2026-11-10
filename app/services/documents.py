from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

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


CONTENT_TYPES = {
    ".csv": "text/csv; charset=utf-8",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}

SUPPORTED_FILE_TYPES = "PDF, DOCX, XLSX, CSV, TXT, and Markdown"
MAX_XLSX_FILES = 5_000
MAX_XLSX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_XLSX_ENTRY_BYTES = 32 * 1024 * 1024
MAX_SPREADSHEET_ROWS = 100_000
MAX_SPREADSHEET_CELLS = 1_000_000


def sanitize_filename(filename: str) -> str:
    name = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    name = "".join(character for character in name if character >= " " and character != "\x7f").strip()
    if not name:
        raise DocumentExtractionError("The document filename is invalid")
    return name[:255]


def document_content_type(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise DocumentExtractionError("The file content does not match the PDF extension")
    if suffix in {".docx", ".xlsx"} and not zipfile.is_zipfile(io.BytesIO(content)):
        label = suffix.removeprefix(".").upper()
        raise DocumentExtractionError(f"The file content does not match the {label} extension")
    try:
        return CONTENT_TYPES[suffix]
    except KeyError as exc:
        raise DocumentExtractionError(f"Supported file types are {SUPPORTED_FILE_TYPES}") from exc


def extract_document(filename: str, content: bytes) -> ExtractedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(content)
    if suffix == ".docx":
        return _extract_docx(content)
    if suffix == ".xlsx":
        return _extract_xlsx(content)
    if suffix == ".csv":
        return _extract_csv(content)
    if suffix in {".txt", ".md"}:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError("Text files must use UTF-8 encoding") from exc
        return _finalize(text, ocr_used=False)
    raise DocumentExtractionError(f"Supported file types are {SUPPORTED_FILE_TYPES}")


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


def _extract_csv(content: bytes) -> ExtractedDocument:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DocumentExtractionError("CSV files must use UTF-8 encoding") from exc
    if "\x00" in text:
        raise DocumentExtractionError("The CSV file contains invalid null bytes")

    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    rows: list[str] = []
    cell_count = 0
    try:
        for row_number, row in enumerate(csv.reader(io.StringIO(text), dialect), start=1):
            if row_number > MAX_SPREADSHEET_ROWS:
                raise DocumentExtractionError("The spreadsheet contains too many rows")
            cell_count += len(row)
            if cell_count > MAX_SPREADSHEET_CELLS:
                raise DocumentExtractionError("The spreadsheet contains too many cells")
            rows.append("\t".join(_normalize_cell(value) for value in row))
    except csv.Error as exc:
        raise DocumentExtractionError("The CSV file could not be read") from exc
    return _finalize("\n".join(rows), ocr_used=False)


def _extract_xlsx(content: bytes) -> ExtractedDocument:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as workbook:
            names = _validate_xlsx_archive(workbook)
            if "xl/workbook.xml" not in names or "[Content_Types].xml" not in names:
                raise DocumentExtractionError("The XLSX workbook structure is invalid")
            content_types = _parse_xlsx_xml(workbook, "[Content_Types].xml")
            workbook_root = _parse_xlsx_xml(workbook, "xl/workbook.xml")
            if _xml_name(content_types.tag) != "Types" or _xml_name(workbook_root.tag) != "workbook":
                raise DocumentExtractionError("The XLSX workbook structure is invalid")

            shared_strings = _xlsx_shared_strings(workbook, names)
            sheet_names = sorted(
                name for name in names if name.startswith("xl/worksheets/") and name.endswith(".xml")
            )
            if not sheet_names:
                raise DocumentExtractionError("The XLSX workbook does not contain any worksheets")

            sections: list[str] = []
            row_count = 0
            cell_count = 0
            for sheet_number, sheet_name in enumerate(sheet_names, start=1):
                root = _parse_xlsx_xml(workbook, sheet_name)
                sheet_rows: list[str] = []
                for row in (element for element in root.iter() if _xml_name(element.tag) == "row"):
                    row_count += 1
                    if row_count > MAX_SPREADSHEET_ROWS:
                        raise DocumentExtractionError("The spreadsheet contains too many rows")
                    values: list[str] = []
                    for cell in (element for element in row if _xml_name(element.tag) == "c"):
                        cell_count += 1
                        if cell_count > MAX_SPREADSHEET_CELLS:
                            raise DocumentExtractionError("The spreadsheet contains too many cells")
                        column = _xlsx_column_index(cell.attrib.get("r", ""))
                        if column is not None:
                            values.extend("" for _ in range(max(0, column - len(values))))
                        values.append(_xlsx_cell_value(cell, shared_strings))
                    if any(values):
                        sheet_rows.append("\t".join(values))
                if sheet_rows:
                    sections.append(f"Sheet {sheet_number}\n" + "\n".join(sheet_rows))
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocumentExtractionError("The XLSX file could not be read") from exc
    return _finalize("\n\n".join(sections), ocr_used=False)


def _validate_xlsx_archive(workbook: zipfile.ZipFile) -> set[str]:
    entries = workbook.infolist()
    if len(entries) > MAX_XLSX_FILES:
        raise DocumentExtractionError("The XLSX workbook contains too many files")

    total_size = 0
    names: set[str] = set()
    for entry in entries:
        parts = Path(entry.filename.replace("\\", "/")).parts
        if entry.filename.startswith(("/", "\\")) or ".." in parts or entry.flag_bits & 0x1:
            raise DocumentExtractionError("The XLSX workbook contains an unsafe archive entry")
        if entry.file_size > MAX_XLSX_ENTRY_BYTES:
            raise DocumentExtractionError("The XLSX workbook contains an oversized file")
        total_size += entry.file_size
        if total_size > MAX_XLSX_UNCOMPRESSED_BYTES:
            raise DocumentExtractionError("The XLSX workbook expands beyond the allowed size")
        names.add(entry.filename)
    return names


def _xlsx_shared_strings(workbook: zipfile.ZipFile, names: set[str]) -> list[str]:
    if "xl/sharedStrings.xml" not in names:
        return []
    root = _parse_xlsx_xml(workbook, "xl/sharedStrings.xml")
    return [
        _normalize_cell("".join(element.text or "" for element in item.iter() if _xml_name(element.tag) == "t"))
        for item in root
        if _xml_name(item.tag) == "si"
    ]


def _parse_xlsx_xml(workbook: zipfile.ZipFile, name: str) -> ElementTree.Element:
    try:
        with workbook.open(name) as source:
            content = source.read(MAX_XLSX_ENTRY_BYTES + 1)
        if len(content) > MAX_XLSX_ENTRY_BYTES:
            raise DocumentExtractionError("The XLSX workbook contains an oversized file")
        return ElementTree.fromstring(content)
    except (KeyError, ElementTree.ParseError, RuntimeError) as exc:
        raise DocumentExtractionError("The XLSX workbook contains invalid XML") from exc


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return _normalize_cell(
            "".join(element.text or "" for element in cell.iter() if _xml_name(element.tag) == "t")
        )

    value = next((element.text or "" for element in cell if _xml_name(element.tag) == "v"), "")
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError) as exc:
            raise DocumentExtractionError("The XLSX workbook has an invalid shared string reference") from exc
    if cell_type == "b":
        return "TRUE" if value == "1" else "FALSE"
    if value:
        return _normalize_cell(value)
    formula = next((element.text or "" for element in cell if _xml_name(element.tag) == "f"), "")
    return _normalize_cell(f"={formula}" if formula else "")


def _xlsx_column_index(reference: str) -> int | None:
    match = re.match(r"^([A-Z]+)", reference.upper())
    if not match:
        return None
    index = 0
    for character in match.group(1):
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def _xml_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _normalize_cell(value: str) -> str:
    return re.sub(r"[\t\r\n]+", " ", value).strip()


def _finalize(text: str, ocr_used: bool) -> ExtractedDocument:
    normalized = re.sub(r"[ \t]+", " ", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        raise DocumentExtractionError("No readable text was found in the document")
    return ExtractedDocument(text=normalized, ocr_used=ocr_used)
