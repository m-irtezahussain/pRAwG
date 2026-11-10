from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError

from app.routers.vector_stores import router
from app.schemas import (
    CollectionSearchResponse,
    DeleteChunkResponse,
    SelfHostedChromaConnection,
    VectorChunk,
    VectorChunkPage,
    VectorCollectionListResponse,
    VectorCollectionSummary,
    VectorStoreConnection,
    VectorStoreConnectionResponse,
)
from app.services import vector_stores
from app.services.vector_stores import (
    TextEmbedder,
    VectorStore,
    VectorStoreConnectionError,
    VectorStoreManager,
)

connection_adapter = TypeAdapter(VectorStoreConnection)


def test_ollama_embedder_uses_configured_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        assert b'"model":"installed-model"' in request.content
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})

    embedder = TextEmbedder("http://ollama:11434", "installed-model")
    embedder.client.close()
    embedder.client = httpx.Client(
        base_url="http://ollama:11434",
        transport=httpx.MockTransport(handler),
    )

    assert embedder.embed(["hello"]) == [[0.1, 0.2, 0.3]]
    assert embedder.dimension == 3


def test_ollama_embedder_rejects_invalid_response() -> None:
    embedder = TextEmbedder("http://ollama:11434", "installed-model")
    embedder.client.close()
    embedder.client = httpx.Client(
        base_url="http://ollama:11434",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"embeddings": []})),
    )

    with pytest.raises(VectorStoreConnectionError, match="invalid embedding response"):
        embedder.embed(["hello"])


@pytest.mark.parametrize(
    "payload",
    [
        {
            "provider": "chroma_self_hosted",
            "endpoint": "http://chroma:8000",
            "collection": "research-notes",
            "tenant": "default_tenant",
            "database": "default_database",
        },
        {
            "provider": "chroma_cloud",
            "api_key": "secret-key",
            "tenant": "tenant-id",
            "database": "database-name",
            "collection": "research-notes",
        },
        {
            "provider": "pinecone_cloud",
            "api_key": "secret-key",
            "index_name": "knowledge-index",
            "namespace": "production",
        },
        {
            "provider": "qdrant_self_hosted",
            "endpoint": "http://qdrant:6333",
            "collection": "research-notes",
        },
        {
            "provider": "qdrant_cloud",
            "endpoint": "https://cluster.us-east.cloud.qdrant.io:6333",
            "api_key": "secret-key",
            "collection": "research-notes",
        },
    ],
)
def test_accepts_supported_connection_shapes(payload: dict[str, str]) -> None:
    connection = connection_adapter.validate_python(payload)
    assert connection.provider == payload["provider"]


def test_rejects_non_qdrant_cloud_host() -> None:
    with pytest.raises(ValidationError, match="cloud.qdrant.io"):
        connection_adapter.validate_python(
            {
                "provider": "qdrant_cloud",
                "endpoint": "https://example.com",
                "api_key": "secret-key",
                "collection": "research-notes",
            }
        )


def test_rejects_unknown_connection_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        connection_adapter.validate_python(
            {
                "provider": "chroma_self_hosted",
                "endpoint": "http://chroma:8000",
                "collection": "research-notes",
                "unexpected": "value",
            }
        )


def test_secret_is_redacted_from_serialized_model() -> None:
    connection = connection_adapter.validate_python(
        {
            "provider": "pinecone_cloud",
            "api_key": "do-not-leak",
            "index_name": "knowledge-index",
        }
    )
    assert "do-not-leak" not in connection.model_dump_json()


class FakeStore(VectorStore):
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.closed = False
        self.ingested_metadata: dict[str, str] | None = None

    def heartbeat(self) -> None:
        if self.fails:
            raise VectorStoreConnectionError("Unable to connect to test store")

    def ingest(
        self,
        filename: str,
        content: bytes,
        text_chunks: list[str],
        metadata: dict[str, str],
    ) -> str:
        self.ingested_metadata = metadata
        return "document-id"

    def search(self, query: str, top_k: int) -> list[Any]:
        return []

    def list_collections(self) -> list[VectorCollectionSummary]:
        return [
            VectorCollectionSummary(
                name="research-notes",
                kind="collection",
                records=12,
                active=True,
            )
        ]

    def list_chunks(self, collection: str, limit: int, cursor: str | None) -> VectorChunkPage:
        pages = {
            None: VectorChunkPage(
                collection=collection,
                chunks=[VectorChunk(id="chunk-1", text="First passage", metadata={"filename": "one.md"})],
                total=2,
                next_cursor="second",
            ),
            "second": VectorChunkPage(
                collection=collection,
                chunks=[VectorChunk(id="chunk-2", text="Needle in later page", metadata={"page": 2})],
                total=2,
                next_cursor=None,
            ),
        }
        return pages[cursor]

    def similarity_search(self, collection: str, query: str, limit: int) -> list[VectorChunk]:
        return [VectorChunk(id="chunk-2", text="Semantic match", metadata={}, score=0.92)]

    def delete_chunk(self, collection: str, chunk_id: str) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class SearchFailureStore(FakeStore):
    def search(self, query: str, top_k: int) -> list[Any]:
        raise RuntimeError("internal provider detail")


def _manager() -> tuple[VectorStoreManager, FakeStore]:
    original = FakeStore()
    status = VectorStoreConnectionResponse(
        provider="chroma_self_hosted",
        label="Self-hosted Chroma",
        collection="original",
        connected=True,
    )
    return VectorStoreManager(original, status, TextEmbedder("http://ollama:11434", "test-model")), original


def test_manager_swaps_store_only_after_success(monkeypatch: pytest.MonkeyPatch) -> None:
    manager, original = _manager()
    replacement = FakeStore()
    monkeypatch.setattr(vector_stores, "build_vector_store", lambda _config, _embedder: replacement)
    config = SelfHostedChromaConnection(
        provider="chroma_self_hosted",
        endpoint="http://chroma:8000",
        collection="new-collection",
    )

    result = manager.connect(config)

    assert manager.store is replacement
    assert original.closed is True
    assert result.collection == "new-collection"


def test_manager_keeps_store_when_test_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    manager, original = _manager()
    monkeypatch.setattr(vector_stores, "build_vector_store", lambda _config, _embedder: FakeStore(fails=True))
    config = SelfHostedChromaConnection(
        provider="chroma_self_hosted",
        endpoint="http://chroma:8000",
        collection="unreachable",
    )

    with pytest.raises(VectorStoreConnectionError, match="Unable to connect"):
        manager.connect(config)

    assert manager.store is original
    assert original.closed is False


def test_manager_hides_internal_search_failure() -> None:
    manager = VectorStoreManager(
        SearchFailureStore(),
        VectorStoreConnectionResponse(
            provider="chroma_self_hosted",
            label="Self-hosted Chroma",
            collection="research-notes",
            connected=True,
        ),
        TextEmbedder("http://ollama:11434", "test-model"),
    )

    with pytest.raises(VectorStoreConnectionError, match="Vector store search failed") as error:
        manager.search("question", 5)

    assert "internal provider detail" not in str(error.value)


def test_manager_passes_custom_metadata_to_vector_store() -> None:
    manager, store = _manager()

    manager.ingest("notes.txt", b"content", ["content"], {"author": "Ada"})

    assert store.ingested_metadata == {"author": "Ada"}


def test_string_search_scans_every_collection_page() -> None:
    manager, _ = _manager()

    result = manager.search_collection("research-notes", "needle", "text", 25)

    assert result.chunks[0].id == "chunk-2"


def test_similarity_search_uses_selected_mode() -> None:
    manager, _ = _manager()

    result = manager.search_collection("research-notes", "meaning", "similarity", 25)

    assert result.mode == "similarity"
    assert result.chunks[0].score == 0.92


class FakeManager:
    status = VectorStoreConnectionResponse(
        provider="chroma_self_hosted",
        label="Self-hosted Chroma",
        collection="research-notes",
        connected=True,
    )

    def connect(self, body: VectorStoreConnection) -> VectorStoreConnectionResponse:
        if body.collection == "failure":
            raise VectorStoreConnectionError("Unable to connect to Chroma")
        return self.status

    def list_collections(self) -> VectorCollectionListResponse:
        return VectorCollectionListResponse(
            provider="chroma_self_hosted",
            collections=[
                VectorCollectionSummary(
                    name="research-notes",
                    kind="collection",
                    records=12,
                    active=True,
                )
            ],
        )

    def list_chunks(self, collection: str, limit: int, cursor: str | None) -> VectorChunkPage:
        return VectorChunkPage(
            collection=collection,
            chunks=[VectorChunk(id="chunk-1", text="Indexed content", metadata={"filename": "notes.md"})],
            total=1,
        )

    def search_collection(self, collection: str, query: str, mode: str, limit: int) -> CollectionSearchResponse:
        return CollectionSearchResponse(
            collection=collection,
            mode=mode,
            chunks=[VectorChunk(id="chunk-1", text=query, metadata={}, score=0.8 if mode == "similarity" else None)],
        )

    def delete_chunk(self, collection: str, chunk_id: str) -> DeleteChunkResponse:
        return DeleteChunkResponse(deleted=True, chunk_id=chunk_id)


def _client() -> TestClient:
    api = FastAPI()
    api.include_router(router)
    api.state.rag = SimpleNamespace(vector_stores=FakeManager())
    return TestClient(api)


def test_connection_endpoint_never_returns_credentials() -> None:
    response = _client().post(
        "/api/v1/vector-store/connections",
        json={
            "provider": "chroma_cloud",
            "api_key": "do-not-return",
            "tenant": "tenant-id",
            "database": "database-name",
            "collection": "research-notes",
        },
    )
    assert response.status_code == 200
    assert "do-not-return" not in response.text
    assert response.json()["connected"] is True


def test_connection_endpoint_maps_safe_failure() -> None:
    response = _client().post(
        "/api/v1/vector-store/connections",
        json={
            "provider": "chroma_self_hosted",
            "endpoint": "http://chroma:8000",
            "collection": "failure",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to connect to Chroma"}


def test_collections_endpoint_returns_sanitized_inventory() -> None:
    response = _client().get("/api/v1/vector-store/collections")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "chroma_self_hosted",
        "collections": [
            {
                "name": "research-notes",
                "kind": "collection",
                "records": 12,
                "active": True,
            }
        ],
    }


def test_collection_chunk_endpoints_support_browse_search_and_delete() -> None:
    client = _client()

    browse = client.get("/api/v1/vector-store/collections/research-notes/chunks")
    search = client.post(
        "/api/v1/vector-store/collections/research-notes/chunks/search",
        json={"query": "meaning", "mode": "similarity", "limit": 10},
    )
    deleted = client.delete("/api/v1/vector-store/collections/research-notes/chunks/chunk-1")

    assert browse.status_code == 200
    assert browse.json()["chunks"][0]["metadata"] == {"filename": "notes.md"}
    assert search.status_code == 200
    assert search.json()["mode"] == "similarity"
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "chunk_id": "chunk-1"}
