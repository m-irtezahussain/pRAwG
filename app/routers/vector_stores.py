from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from app.schemas import (
    CollectionSearchRequest,
    CollectionSearchResponse,
    DeleteChunkResponse,
    VectorChunkPage,
    VectorCollectionListResponse,
    VectorStoreConnection,
    VectorStoreConnectionResponse,
)
from app.services.vector_stores import VectorStoreConnectionError

router = APIRouter(prefix="/api/v1/vector-store", tags=["vector-store"])


@router.get("/connection", response_model=VectorStoreConnectionResponse)
def get_connection(request: Request) -> VectorStoreConnectionResponse:
    return request.app.state.rag.vector_stores.status


@router.get("/collections", response_model=VectorCollectionListResponse)
def list_collections(request: Request) -> VectorCollectionListResponse:
    try:
        return request.app.state.rag.vector_stores.list_collections()
    except VectorStoreConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/collections/{collection}/chunks", response_model=VectorChunkPage)
def list_collection_chunks(
    request: Request,
    collection: Annotated[str, Path(min_length=1, max_length=128)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
) -> VectorChunkPage:
    try:
        return request.app.state.rag.vector_stores.list_chunks(collection, limit, cursor)
    except VectorStoreConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/collections/{collection}/chunks/search", response_model=CollectionSearchResponse)
def search_collection_chunks(
    body: CollectionSearchRequest,
    request: Request,
    collection: Annotated[str, Path(min_length=1, max_length=128)],
) -> CollectionSearchResponse:
    try:
        return request.app.state.rag.vector_stores.search_collection(
            collection,
            body.query,
            body.mode,
            body.limit,
        )
    except VectorStoreConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.delete("/collections/{collection}/chunks/{chunk_id}", response_model=DeleteChunkResponse)
def delete_collection_chunk(
    request: Request,
    collection: Annotated[str, Path(min_length=1, max_length=128)],
    chunk_id: Annotated[str, Path(min_length=1, max_length=512)],
) -> DeleteChunkResponse:
    try:
        return request.app.state.rag.vector_stores.delete_chunk(collection, chunk_id)
    except VectorStoreConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/connections", response_model=VectorStoreConnectionResponse)
def connect_vector_store(body: VectorStoreConnection, request: Request) -> VectorStoreConnectionResponse:
    try:
        return request.app.state.rag.vector_stores.connect(body)
    except VectorStoreConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
