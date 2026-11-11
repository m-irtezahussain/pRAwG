from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers.documents import router as documents_router
from app.routers.vector_stores import router as vector_stores_router
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.object_storage import ObjectStorageError
from app.services.rag import RagService
from app.services.vector_stores import VectorStoreConnectionError

logger = logging.getLogger("uvicorn.error.prawg.chat")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rag = RagService(get_settings())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    api = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    api.include_router(vector_stores_router)
    api.include_router(documents_router)

    @api.exception_handler(VectorStoreConnectionError)
    async def vector_store_error(_: Request, exc: VectorStoreConnectionError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(exc)},
        )

    @api.exception_handler(ObjectStorageError)
    async def object_storage_error(_: Request, exc: ObjectStorageError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(exc)},
        )

    @api.get("/health/live", response_model=HealthResponse, tags=["health"])
    def live() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.get("/health/ready", response_model=HealthResponse, tags=["health"])
    def ready(request: Request) -> HealthResponse:
        try:
            _rag(request).heartbeat()
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vector store is unavailable") from exc
        return HealthResponse(status="ready")

    @api.post("/api/v1/search", response_model=SearchResponse, tags=["rag"])
    def search(request: Request, body: SearchRequest) -> SearchResponse:
        return SearchResponse(results=_rag(request).search(body.query, body.top_k))

    @api.post("/api/v1/chat", response_model=ChatResponse, tags=["rag"])
    def chat(request: Request, response: Response, body: ChatRequest) -> ChatResponse:
        request_id = uuid4().hex[:12]
        response.headers["X-Request-ID"] = request_id
        started_at = perf_counter()
        logger.info(
            "chat.request_started request_id=%s top_k=%d history_messages=%d question_chars=%d",
            request_id,
            body.top_k,
            len(body.history),
            len(body.question),
        )
        service = _rag(request)
        try:
            sources = service.search(body.question, body.top_k)
        except Exception as exc:
            logger.error(
                "chat.retrieval_failed request_id=%s exception_type=%s elapsed_ms=%.1f",
                request_id,
                type(exc).__name__,
                (perf_counter() - started_at) * 1000,
            )
            raise
        logger.info(
            "chat.retrieval_completed request_id=%s sources=%d elapsed_ms=%.1f",
            request_id,
            len(sources),
            (perf_counter() - started_at) * 1000,
        )
        try:
            chat_response = service.chat(body.question, sources, body.history, request_id=request_id)
        except RuntimeError as exc:
            logger.warning(
                "chat.request_failed request_id=%s reason=%s elapsed_ms=%.1f",
                request_id,
                str(exc),
                (perf_counter() - started_at) * 1000,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{exc} (request ID: {request_id})",
            ) from exc
        logger.info(
            "chat.request_completed request_id=%s answer_chars=%d sources=%d elapsed_ms=%.1f",
            request_id,
            len(chat_response.answer),
            len(chat_response.sources),
            (perf_counter() - started_at) * 1000,
        )
        return chat_response

    return api


def _rag(request: Request) -> RagService:
    return request.app.state.rag


app = create_app()
