import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi import Path as ApiPath
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.schemas import DocumentMetadata, IngestResponse, StoredDocumentListResponse
from app.services.documents import (
    DocumentExtractionError,
    chunk_text,
    document_content_type,
    extract_document,
    sanitize_filename,
)
from app.services.object_storage import (
    ObjectStorageError,
    StoredDocumentNotFoundError,
    attachment_disposition,
)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
MAX_METADATA_JSON_BYTES = 8 * 1024


@router.post("", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_document(
    request: Request,
    file: Annotated[UploadFile, File()],
    filename: Annotated[str | None, Form(max_length=255)] = None,
    metadata: Annotated[str, Form(max_length=MAX_METADATA_JSON_BYTES)] = "{}",
) -> IngestResponse:
    service = request.app.state.rag
    original_filename = sanitize_filename(file.filename or "upload")
    filename = sanitize_filename(filename or original_filename)
    if Path(filename).suffix.lower() != Path(original_filename).suffix.lower():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The file extension cannot be changed",
        )
    custom_metadata = _parse_metadata(metadata)
    content = _read_limited(file, service.settings.max_upload_mb * 1024 * 1024)
    try:
        document = extract_document(filename, content)
        content_type = document_content_type(filename, content)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    chunks = chunk_text(document.text, service.settings.chunk_size, service.settings.chunk_overlap)
    document_id = service.ingest(filename, content, content_type, chunks, custom_metadata)
    return IngestResponse(
        document_id=document_id,
        filename=filename,
        chunks=len(chunks),
        characters=len(document.text),
        ocr_used=document.ocr_used,
        stored=True,
        metadata=custom_metadata,
    )


@router.get("", response_model=StoredDocumentListResponse)
def list_documents(request: Request) -> StoredDocumentListResponse:
    return StoredDocumentListResponse(documents=request.app.state.rag.list_documents())


@router.get("/{document_id}/content", response_class=StreamingResponse)
def download_document(
    request: Request,
    document_id: Annotated[str, ApiPath(pattern=r"^[a-f0-9]{64}$")],
) -> StreamingResponse:
    try:
        download = request.app.state.rag.get_document(document_id)
    except StoredDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ObjectStorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StreamingResponse(
        download.chunks(),
        media_type=download.content_type,
        headers={
            "Content-Disposition": attachment_disposition(download.filename),
            "Content-Length": str(download.size),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Cache-Control": "private, no-store",
        },
    )


def _read_limited(file: UploadFile, limit: int) -> bytes:
    content = file.file.read(limit + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty")
    if len(content) > limit:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The uploaded file is too large")
    return content


def _parse_metadata(raw_metadata: str) -> dict[str, str]:
    if len(raw_metadata.encode("utf-8")) > MAX_METADATA_JSON_BYTES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Custom metadata is too large")
    try:
        payload = json.loads(raw_metadata)
        if not isinstance(payload, dict):
            raise TypeError
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in payload.items()):
            raise TypeError
        normalized = {
            key.strip(): value.strip()
            for key, value in payload.items()
            if key.strip() or value.strip()
        }
        parsed = DocumentMetadata(values=normalized)
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Custom metadata must contain up to 20 valid key and value pairs",
        ) from exc
    return parsed.values
