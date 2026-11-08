from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status

from app.config import get_settings
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IngestResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.documents import DocumentExtractionError, chunk_text, extract_document
from app.services.rag import RagService


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rag = RagService(get_settings())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    @api.get("/health/live", response_model=HealthResponse, tags=["health"])
    def live() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.get("/health/ready", response_model=HealthResponse, tags=["health"])
    def ready(request: Request) -> HealthResponse:
        try:
            _rag(request).heartbeat()
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chroma is unavailable") from exc
        return HealthResponse(status="ready")

    @api.post(
        "/api/v1/documents",
        response_model=IngestResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["rag"],
    )
    def ingest_document(request: Request, file: Annotated[UploadFile, File()]) -> IngestResponse:
        filename = file.filename or "upload"
        content = _read_limited(file, settings.max_upload_mb * 1024 * 1024)
        try:
            document = extract_document(filename, content)
        except DocumentExtractionError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

        chunks = chunk_text(document.text, settings.chunk_size, settings.chunk_overlap)
        document_id = _rag(request).ingest(filename, content, chunks)
        return IngestResponse(
            document_id=document_id,
            filename=filename,
            chunks=len(chunks),
            characters=len(document.text),
            ocr_used=document.ocr_used,
        )

    @api.post("/api/v1/search", response_model=SearchResponse, tags=["rag"])
    def search(request: Request, body: SearchRequest) -> SearchResponse:
        return SearchResponse(results=_rag(request).search(body.query, body.top_k))

    @api.post("/api/v1/chat", response_model=ChatResponse, tags=["rag"])
    def chat(request: Request, body: ChatRequest) -> ChatResponse:
        service = _rag(request)
        sources = service.search(body.question, body.top_k)
        try:
            answer = service.chat(body.question, sources)
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        return ChatResponse(answer=answer, sources=sources)

    return api


def _rag(request: Request) -> RagService:
    return request.app.state.rag


def _read_limited(file: UploadFile, limit: int) -> bytes:
    content = file.file.read(limit + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty")
    if len(content) > limit:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="The uploaded file is too large")
    return content


app = create_app()
