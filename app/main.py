from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
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


app = create_app()
