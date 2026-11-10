from __future__ import annotations

import hashlib
import json
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Literal
from urllib.parse import quote, urlsplit

import chromadb
import httpx

from app.config import Settings
from app.schemas import (
    CloudChromaConnection,
    CloudPineconeConnection,
    CloudQdrantConnection,
    CollectionSearchResponse,
    DeleteChunkResponse,
    SearchResult,
    SelfHostedChromaConnection,
    SelfHostedQdrantConnection,
    VectorChunk,
    VectorChunkPage,
    VectorCollectionListResponse,
    VectorCollectionSummary,
    VectorStoreConnection,
    VectorStoreConnectionResponse,
)

UPSERT_BATCH_SIZE = 100
REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class VectorStoreConnectionError(RuntimeError):
    """A safe-to-display vector store connection failure."""


class VectorStore(ABC):
    @abstractmethod
    def heartbeat(self) -> None: ...

    @abstractmethod
    def ingest(
        self,
        filename: str,
        content: bytes,
        text_chunks: list[str],
        metadata: dict[str, str],
    ) -> str: ...

    @abstractmethod
    def search(self, query: str, top_k: int) -> list[SearchResult]: ...

    @abstractmethod
    def list_collections(self) -> list[VectorCollectionSummary]: ...

    @abstractmethod
    def list_chunks(self, collection: str, limit: int, cursor: str | None) -> VectorChunkPage: ...

    @abstractmethod
    def similarity_search(self, collection: str, query: str, limit: int) -> list[VectorChunk]: ...

    @abstractmethod
    def delete_chunk(self, collection: str, chunk_id: str) -> None: ...

    def close(self) -> None:
        return None


class TextEmbedder:
    def __init__(self, base_url: str, model: str) -> None:
        self.model = model
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(120.0, connect=10.0),
            follow_redirects=False,
        )
        self._dimension: int | None = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            response = self.client.post("/api/embed", json={"model": self.model, "input": list(texts)})
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise VectorStoreConnectionError(
                    f"Ollama embedding model '{self.model}' is not installed"
                ) from exc
            raise VectorStoreConnectionError("Ollama embedding model is unavailable") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise VectorStoreConnectionError("Ollama embedding model is unavailable") from exc
        if not isinstance(payload, dict):
            raise VectorStoreConnectionError("Ollama returned an invalid embedding response")
        raw_embeddings = payload.get("embeddings", [])
        if not isinstance(raw_embeddings, list) or len(raw_embeddings) != len(texts) or not raw_embeddings:
            raise VectorStoreConnectionError("Ollama returned an invalid embedding response")
        try:
            embeddings = [[float(value) for value in embedding] for embedding in raw_embeddings]
        except (TypeError, ValueError) as exc:
            raise VectorStoreConnectionError("Ollama returned an invalid embedding response") from exc
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) != 1 or 0 in dimensions:
            raise VectorStoreConnectionError("Ollama returned inconsistent embedding dimensions")
        dimension = dimensions.pop()
        if self._dimension is not None and dimension != self._dimension:
            raise VectorStoreConnectionError("Ollama embedding dimension changed unexpectedly")
        self._dimension = dimension
        return embeddings

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self.embed(["pRAwG embedding dimension probe"])
        if self._dimension is None:
            raise VectorStoreConnectionError("Unable to determine Ollama embedding dimension")
        return self._dimension


def batches(items: Sequence[str], size: int = UPSERT_BATCH_SIZE) -> list[tuple[int, Sequence[str]]]:
    return [(offset, items[offset : offset + size]) for offset in range(0, len(items), size)]


class ChromaVectorStore(VectorStore):
    def __init__(self, client: Any, collection_name: str, embedder: TextEmbedder) -> None:
        self.client = client
        self.collection_name = collection_name
        self.embedder = embedder
        self.collection = client.get_or_create_collection(name=collection_name)

    @classmethod
    def self_hosted(cls, config: SelfHostedChromaConnection, embedder: TextEmbedder) -> ChromaVectorStore:
        endpoint = urlsplit(str(config.endpoint))
        headers = None
        if config.auth_token is not None:
            headers = {"Authorization": f"Bearer {config.auth_token.get_secret_value()}"}
        client = chromadb.HttpClient(
            host=endpoint.hostname or "localhost",
            port=endpoint.port or (443 if endpoint.scheme == "https" else 80),
            ssl=endpoint.scheme == "https",
            headers=headers,
            tenant=config.tenant,
            database=config.database,
        )
        return cls(client, config.collection, embedder)

    @classmethod
    def cloud(cls, config: CloudChromaConnection, embedder: TextEmbedder) -> ChromaVectorStore:
        client = chromadb.CloudClient(
            api_key=config.api_key.get_secret_value(),
            tenant=config.tenant,
            database=config.database,
        )
        return cls(client, config.collection, embedder)

    def heartbeat(self) -> None:
        self.client.heartbeat()
        probe = self.embedder.embed(["pRAwG connection probe"])[0]
        if self.collection.count() > 0:
            self.collection.query(query_embeddings=[probe], n_results=1)

    def ingest(
        self,
        filename: str,
        content: bytes,
        text_chunks: list[str],
        metadata: dict[str, str],
    ) -> str:
        document_id = hashlib.sha256(content).hexdigest()
        for offset, chunk_batch in batches(text_chunks):
            embeddings = self.embedder.embed(chunk_batch)
            ids = [f"{document_id}:{offset + index}" for index in range(len(chunk_batch))]
            metadatas = [
                {
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": offset + index,
                    **metadata,
                }
                for index in range(len(chunk_batch))
            ]
            self.collection.upsert(
                ids=ids,
                documents=list(chunk_batch),
                embeddings=embeddings,
                metadatas=metadatas,
            )
        return document_id

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        query_embedding = self.embedder.embed([query])[0]
        result: dict[str, Any] = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            SearchResult(
                id=item_id,
                text=documents[index] or "",
                metadata=metadatas[index] or {},
                distance=distances[index] if index < len(distances) else None,
            )
            for index, item_id in enumerate(ids)
        ]

    def list_collections(self) -> list[VectorCollectionSummary]:
        summaries: list[VectorCollectionSummary] = []
        for collection in self.client.list_collections():
            name = collection.name if hasattr(collection, "name") else str(collection)
            count = self.client.get_collection(name=name).count()
            summaries.append(
                VectorCollectionSummary(
                    name=name,
                    kind="collection",
                    records=count,
                    active=name == self.collection_name,
                )
            )
        return sorted(summaries, key=lambda item: item.name.lower())

    def list_chunks(self, collection: str, limit: int, cursor: str | None) -> VectorChunkPage:
        try:
            offset = int(cursor or "0")
            if offset < 0:
                raise ValueError
            target = self.client.get_collection(name=collection)
            total = target.count()
            result: dict[str, Any] = target.get(
                limit=limit,
                offset=offset,
                include=["documents", "metadatas"],
            )
        except (TypeError, ValueError) as exc:
            raise VectorStoreConnectionError("Invalid collection page cursor") from exc
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        chunks = [
            VectorChunk(
                id=str(item_id),
                text=str(documents[index] or "") if index < len(documents) else "",
                metadata=metadatas[index] or {} if index < len(metadatas) else {},
            )
            for index, item_id in enumerate(ids)
        ]
        next_offset = offset + len(chunks)
        return VectorChunkPage(
            collection=collection,
            chunks=chunks,
            total=total,
            next_cursor=str(next_offset) if next_offset < total else None,
        )

    def similarity_search(self, collection: str, query: str, limit: int) -> list[VectorChunk]:
        target = self.client.get_collection(name=collection)
        count = target.count()
        if count == 0:
            return []
        result: dict[str, Any] = target.query(
            query_embeddings=[self.embedder.embed([query])[0]],
            n_results=min(limit, count),
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            VectorChunk(
                id=str(item_id),
                text=str(documents[index] or "") if index < len(documents) else "",
                metadata=metadatas[index] or {} if index < len(metadatas) else {},
                score=1.0 - float(distances[index]) if index < len(distances) else None,
            )
            for index, item_id in enumerate(ids)
        ]

    def delete_chunk(self, collection: str, chunk_id: str) -> None:
        self.client.get_collection(name=collection).delete(ids=[chunk_id])


class HttpVectorStore(VectorStore):
    def __init__(self, base_url: str, api_key: str | None, embedder: TextEmbedder) -> None:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if api_key:
            headers["api-key"] = api_key
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,
        )
        self.embedder = embedder

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _raise_connection_error(provider: str, exc: Exception) -> None:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403}:
            raise VectorStoreConnectionError(f"{provider} rejected the supplied credentials") from exc
        raise VectorStoreConnectionError(f"Unable to connect to {provider}") from exc


class QdrantVectorStore(HttpVectorStore):
    def __init__(self, endpoint: str, collection: str, api_key: str | None, embedder: TextEmbedder) -> None:
        super().__init__(endpoint, api_key, embedder)
        self.collection = collection
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        path = f"/collections/{quote(self.collection, safe='')}"
        try:
            response = self.client.get(path)
            if response.status_code == 404:
                response = self.client.put(
                    path,
                    json={"vectors": {"size": self.embedder.dimension, "distance": "Cosine"}},
                )
                response.raise_for_status()
                response = self.client.get(path)
            response.raise_for_status()
            payload = response.json()
            vector_config = payload.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
            configured_size = vector_config.get("size") if isinstance(vector_config, dict) else None
            if configured_size is None:
                raise VectorStoreConnectionError("Qdrant collection must use a single unnamed dense vector")
            if configured_size != self.embedder.dimension:
                raise VectorStoreConnectionError(
                    f"Qdrant collection must use {self.embedder.dimension}-dimensional vectors"
                )
        except VectorStoreConnectionError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_connection_error("Qdrant", exc)

    def heartbeat(self) -> None:
        try:
            self.client.get(f"/collections/{quote(self.collection, safe='')}").raise_for_status()
        except httpx.HTTPError as exc:
            self._raise_connection_error("Qdrant", exc)

    def ingest(
        self,
        filename: str,
        content: bytes,
        text_chunks: list[str],
        metadata: dict[str, str],
    ) -> str:
        document_id = hashlib.sha256(content).hexdigest()
        for offset, chunk_batch in batches(text_chunks):
            embeddings = self.embedder.embed(chunk_batch)
            points = [
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{offset + index}")),
                    "vector": embeddings[index],
                    "payload": {
                        "source_id": f"{document_id}:{offset + index}",
                        "document_id": document_id,
                        "filename": filename,
                        "chunk_index": offset + index,
                        "text": text,
                        **metadata,
                    },
                }
                for index, text in enumerate(chunk_batch)
            ]
            try:
                response = self.client.put(
                    f"/collections/{quote(self.collection, safe='')}/points",
                    params={"wait": "true"},
                    json={"points": points},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                self._raise_connection_error("Qdrant", exc)
        return document_id

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        vector = self.embedder.embed([query])[0]
        try:
            response = self.client.post(
                f"/collections/{quote(self.collection, safe='')}/points/search",
                json={"vector": vector, "limit": top_k, "with_payload": True, "with_vector": False},
            )
            response.raise_for_status()
            points = response.json().get("result", [])
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_connection_error("Qdrant", exc)
        return [
            SearchResult(
                id=str(point.get("payload", {}).get("source_id") or point.get("id", "")),
                text=str(point.get("payload", {}).get("text", "")),
                metadata={
                    key: value
                    for key, value in point.get("payload", {}).items()
                    if key != "text" and isinstance(value, (str, int, float, bool))
                },
                distance=None,
            )
            for point in points
        ]

    def list_collections(self) -> list[VectorCollectionSummary]:
        try:
            response = self.client.get("/collections")
            response.raise_for_status()
            collections = response.json().get("result", {}).get("collections", [])
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_connection_error("Qdrant", exc)

        summaries: list[VectorCollectionSummary] = []
        for collection in collections:
            name = str(collection.get("name", ""))
            if not name:
                continue
            records: int | None = None
            try:
                detail = self.client.get(f"/collections/{quote(name, safe='')}")
                detail.raise_for_status()
                raw_count = detail.json().get("result", {}).get("points_count")
                records = int(raw_count) if raw_count is not None else None
            except (httpx.HTTPError, TypeError, ValueError):
                records = None
            summaries.append(
                VectorCollectionSummary(
                    name=name,
                    kind="collection",
                    records=records,
                    active=name == self.collection,
                )
            )
        return sorted(summaries, key=lambda item: item.name.lower())

    def list_chunks(self, collection: str, limit: int, cursor: str | None) -> VectorChunkPage:
        path = f"/collections/{quote(collection, safe='')}"
        try:
            offset: str | int | None = None
            if cursor is not None:
                parsed_cursor = json.loads(cursor)
                if not isinstance(parsed_cursor, (str, int)):
                    raise ValueError
                offset = parsed_cursor
            detail = self.client.get(path)
            detail.raise_for_status()
            total_value = detail.json().get("result", {}).get("points_count")
            response = self.client.post(
                f"{path}/points/scroll",
                json={
                    "limit": limit,
                    "offset": offset,
                    "with_payload": True,
                    "with_vector": False,
                },
            )
            response.raise_for_status()
            result = response.json().get("result", {})
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            self._raise_connection_error("Qdrant", exc)
        points = result.get("points", [])
        chunks = [self._point_to_chunk(point) for point in points]
        next_offset = result.get("next_page_offset")
        return VectorChunkPage(
            collection=collection,
            chunks=chunks,
            total=int(total_value) if total_value is not None else None,
            next_cursor=json.dumps(next_offset) if next_offset is not None else None,
        )

    def similarity_search(self, collection: str, query: str, limit: int) -> list[VectorChunk]:
        try:
            response = self.client.post(
                f"/collections/{quote(collection, safe='')}/points/search",
                json={
                    "vector": self.embedder.embed([query])[0],
                    "limit": limit,
                    "with_payload": True,
                    "with_vector": False,
                },
            )
            response.raise_for_status()
            points = response.json().get("result", [])
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_connection_error("Qdrant", exc)
        return [self._point_to_chunk(point, score=point.get("score")) for point in points]

    def delete_chunk(self, collection: str, chunk_id: str) -> None:
        try:
            response = self.client.post(
                f"/collections/{quote(collection, safe='')}/points/delete",
                params={"wait": "true"},
                json={"points": [chunk_id]},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._raise_connection_error("Qdrant", exc)

    @staticmethod
    def _point_to_chunk(point: dict[str, Any], score: Any = None) -> VectorChunk:
        payload = point.get("payload") if isinstance(point.get("payload"), dict) else {}
        return VectorChunk(
            id=str(point.get("id", "")),
            text=str(payload.get("text", "")),
            metadata={key: value for key, value in payload.items() if key != "text"},
            score=float(score) if isinstance(score, (int, float)) else None,
        )


class PineconeVectorStore(HttpVectorStore):
    API_VERSION = "2025-10"

    def __init__(self, config: CloudPineconeConnection, embedder: TextEmbedder) -> None:
        api_key = config.api_key.get_secret_value()
        try:
            response = httpx.get(
                f"https://api.pinecone.io/indexes/{quote(config.index_name, safe='')}",
                headers={"Api-Key": api_key, "X-Pinecone-Api-Version": self.API_VERSION, "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
                follow_redirects=False,
            )
            response.raise_for_status()
            description = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_connection_error("Pinecone", exc)
        host = str(description.get("host", ""))
        if not host.endswith(".pinecone.io") or "/" in host:
            raise VectorStoreConnectionError("Pinecone returned an invalid index host")
        if description.get("dimension") != embedder.dimension:
            raise VectorStoreConnectionError(
                f"Pinecone index must use {embedder.dimension}-dimensional vectors"
            )
        if not description.get("status", {}).get("ready", False):
            raise VectorStoreConnectionError("Pinecone index is not ready")
        super().__init__(f"https://{host}", api_key, embedder)
        self.namespace = config.namespace

    def heartbeat(self) -> None:
        try:
            self.client.post("/describe_index_stats", json={}).raise_for_status()
        except httpx.HTTPError as exc:
            self._raise_connection_error("Pinecone", exc)

    def ingest(
        self,
        filename: str,
        content: bytes,
        text_chunks: list[str],
        metadata: dict[str, str],
    ) -> str:
        document_id = hashlib.sha256(content).hexdigest()
        for offset, chunk_batch in batches(text_chunks):
            embeddings = self.embedder.embed(chunk_batch)
            vectors = [
                {
                    "id": f"{document_id}:{offset + index}",
                    "values": embeddings[index],
                    "metadata": {
                        "document_id": document_id,
                        "filename": filename,
                        "chunk_index": offset + index,
                        "text": text,
                        **metadata,
                    },
                }
                for index, text in enumerate(chunk_batch)
            ]
            try:
                response = self.client.post(
                    "/vectors/upsert",
                    json={"vectors": vectors, "namespace": self.namespace},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                self._raise_connection_error("Pinecone", exc)
        return document_id

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        vector = self.embedder.embed([query])[0]
        try:
            response = self.client.post(
                "/query",
                json={
                    "vector": vector,
                    "topK": top_k,
                    "namespace": self.namespace,
                    "includeMetadata": True,
                    "includeValues": False,
                },
            )
            response.raise_for_status()
            matches = response.json().get("matches", [])
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_connection_error("Pinecone", exc)
        return [
            SearchResult(
                id=str(match.get("id", "")),
                text=str(match.get("metadata", {}).get("text", "")),
                metadata={
                    key: value
                    for key, value in match.get("metadata", {}).items()
                    if key != "text" and isinstance(value, (str, int, float, bool))
                },
                distance=None,
            )
            for match in matches
        ]

    def list_collections(self) -> list[VectorCollectionSummary]:
        try:
            response = self.client.post("/describe_index_stats", json={})
            response.raise_for_status()
            namespaces = response.json().get("namespaces", {})
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_connection_error("Pinecone", exc)
        if not isinstance(namespaces, dict):
            raise VectorStoreConnectionError("Pinecone returned invalid namespace data")

        summaries = [
            VectorCollectionSummary(
                name=namespace or "Default namespace",
                kind="namespace",
                records=int(details.get("vectorCount", 0)),
                active=namespace == self.namespace,
            )
            for namespace, details in namespaces.items()
            if isinstance(details, dict)
        ]
        if not summaries:
            summaries.append(
                VectorCollectionSummary(
                    name=self.namespace or "Default namespace",
                    kind="namespace",
                    records=0,
                    active=True,
                )
            )
        return sorted(summaries, key=lambda item: item.name.lower())

    @staticmethod
    def _namespace(collection: str) -> str:
        return "" if collection == "Default namespace" else collection

    def list_chunks(self, collection: str, limit: int, cursor: str | None) -> VectorChunkPage:
        namespace = self._namespace(collection)
        params: list[tuple[str, str | int]] = [("namespace", namespace), ("limit", limit)]
        if cursor:
            params.append(("paginationToken", cursor))
        try:
            response = self.client.get("/vectors/list", params=params)
            response.raise_for_status()
            payload = response.json()
            vector_ids = [str(item.get("id", "")) for item in payload.get("vectors", []) if item.get("id")]
            chunks = self._fetch_chunks(namespace, vector_ids)
            stats = self.client.post("/describe_index_stats", json={})
            stats.raise_for_status()
            namespace_stats = stats.json().get("namespaces", {}).get(namespace, {})
            total_value = namespace_stats.get("vectorCount")
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            self._raise_connection_error("Pinecone", exc)
        next_cursor = payload.get("pagination", {}).get("next")
        return VectorChunkPage(
            collection=collection,
            chunks=chunks,
            total=int(total_value) if total_value is not None else None,
            next_cursor=str(next_cursor) if next_cursor else None,
        )

    def similarity_search(self, collection: str, query: str, limit: int) -> list[VectorChunk]:
        namespace = self._namespace(collection)
        try:
            response = self.client.post(
                "/query",
                json={
                    "vector": self.embedder.embed([query])[0],
                    "topK": limit,
                    "namespace": namespace,
                    "includeMetadata": True,
                    "includeValues": False,
                },
            )
            response.raise_for_status()
            matches = response.json().get("matches", [])
        except (httpx.HTTPError, ValueError) as exc:
            self._raise_connection_error("Pinecone", exc)
        return [
            VectorChunk(
                id=str(match.get("id", "")),
                text=str(match.get("metadata", {}).get("text", "")),
                metadata={key: value for key, value in match.get("metadata", {}).items() if key != "text"},
                score=float(match["score"]) if isinstance(match.get("score"), (int, float)) else None,
            )
            for match in matches
        ]

    def delete_chunk(self, collection: str, chunk_id: str) -> None:
        try:
            response = self.client.post(
                "/vectors/delete",
                json={"ids": [chunk_id], "namespace": self._namespace(collection)},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._raise_connection_error("Pinecone", exc)

    def _fetch_chunks(self, namespace: str, vector_ids: list[str]) -> list[VectorChunk]:
        if not vector_ids:
            return []
        params: list[tuple[str, str]] = [("namespace", namespace)]
        params.extend(("ids", vector_id) for vector_id in vector_ids)
        response = self.client.get("/vectors/fetch", params=params)
        response.raise_for_status()
        vectors = response.json().get("vectors", {})
        return [
            VectorChunk(
                id=vector_id,
                text=str(vectors.get(vector_id, {}).get("metadata", {}).get("text", "")),
                metadata={
                    key: value
                    for key, value in vectors.get(vector_id, {}).get("metadata", {}).items()
                    if key != "text"
                },
            )
            for vector_id in vector_ids
        ]


def build_vector_store(config: VectorStoreConnection, embedder: TextEmbedder) -> VectorStore:
    if isinstance(config, SelfHostedChromaConnection):
        return ChromaVectorStore.self_hosted(config, embedder)
    if isinstance(config, CloudChromaConnection):
        return ChromaVectorStore.cloud(config, embedder)
    if isinstance(config, CloudPineconeConnection):
        return PineconeVectorStore(config, embedder)
    if isinstance(config, (SelfHostedQdrantConnection, CloudQdrantConnection)):
        api_key = config.api_key.get_secret_value() if config.api_key else None
        return QdrantVectorStore(str(config.endpoint), config.collection, api_key, embedder)
    raise VectorStoreConnectionError("Unsupported vector store provider")


class VectorStoreManager:
    def __init__(self, store: VectorStore, status: VectorStoreConnectionResponse, embedder: TextEmbedder) -> None:
        self._store = store
        self._status = status
        self._embedder = embedder
        self._lock = threading.RLock()

    @classmethod
    def from_settings(cls, settings: Settings) -> VectorStoreManager:
        embedder = TextEmbedder(settings.ollama_base_url, settings.ollama_embedding_model)
        endpoint = f"http://{settings.chroma_host}:{settings.chroma_port}"
        config = SelfHostedChromaConnection(
            provider="chroma_self_hosted",
            endpoint=endpoint,
            collection=settings.chroma_collection,
        )
        store = build_vector_store(config, embedder)
        status = VectorStoreConnectionResponse(
            provider=config.provider,
            label="Self-hosted Chroma",
            collection=config.collection,
            connected=True,
        )
        return cls(store, status, embedder)

    def connect(self, config: VectorStoreConnection) -> VectorStoreConnectionResponse:
        try:
            candidate = build_vector_store(config, self._embedder)
            candidate.heartbeat()
        except VectorStoreConnectionError:
            raise
        except Exception as exc:
            raise VectorStoreConnectionError("Unable to connect to the vector store") from exc

        labels = {
            "chroma_self_hosted": "Self-hosted Chroma",
            "chroma_cloud": "Chroma Cloud",
            "pinecone_cloud": "Pinecone Cloud",
            "qdrant_self_hosted": "Self-hosted Qdrant",
            "qdrant_cloud": "Qdrant Cloud",
        }
        collection = config.index_name if isinstance(config, CloudPineconeConnection) else config.collection
        status = VectorStoreConnectionResponse(
            provider=config.provider,
            label=labels[config.provider],
            collection=collection,
            connected=True,
        )
        with self._lock:
            previous = self._store
            self._store = candidate
            self._status = status
        previous.close()
        return status

    @property
    def store(self) -> VectorStore:
        with self._lock:
            return self._store

    def heartbeat(self) -> None:
        with self._lock:
            try:
                self._store.heartbeat()
            except VectorStoreConnectionError:
                raise
            except Exception as exc:
                raise VectorStoreConnectionError("Vector store health check failed") from exc

    def ingest(
        self,
        filename: str,
        content: bytes,
        text_chunks: list[str],
        metadata: dict[str, str],
    ) -> str:
        with self._lock:
            try:
                return self._store.ingest(filename, content, text_chunks, metadata)
            except VectorStoreConnectionError:
                raise
            except Exception as exc:
                raise VectorStoreConnectionError("Vector store ingestion failed") from exc

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        with self._lock:
            try:
                return self._store.search(query, top_k)
            except VectorStoreConnectionError:
                raise
            except Exception as exc:
                raise VectorStoreConnectionError("Vector store search failed") from exc

    def list_collections(self) -> VectorCollectionListResponse:
        with self._lock:
            try:
                collections = self._store.list_collections()
            except VectorStoreConnectionError:
                raise
            except Exception as exc:
                raise VectorStoreConnectionError("Unable to list vector store collections") from exc
            return VectorCollectionListResponse(
                provider=self._status.provider,
                collections=collections,
            )

    def list_chunks(self, collection: str, limit: int, cursor: str | None) -> VectorChunkPage:
        with self._lock:
            try:
                return self._store.list_chunks(collection, limit, cursor)
            except VectorStoreConnectionError:
                raise
            except Exception as exc:
                raise VectorStoreConnectionError("Unable to load collection chunks") from exc

    def search_collection(
        self,
        collection: str,
        query: str,
        mode: Literal["similarity", "text"],
        limit: int,
    ) -> CollectionSearchResponse:
        with self._lock:
            try:
                if mode == "similarity":
                    chunks = self._store.similarity_search(collection, query, limit)
                else:
                    chunks = self._string_search(collection, query, limit)
            except VectorStoreConnectionError:
                raise
            except Exception as exc:
                raise VectorStoreConnectionError("Unable to search collection chunks") from exc
        return CollectionSearchResponse(
            collection=collection,
            mode=mode,
            chunks=chunks,
        )

    def _string_search(self, collection: str, query: str, limit: int) -> list[VectorChunk]:
        needle = query.casefold()
        matches: list[VectorChunk] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        while True:
            page = self._store.list_chunks(collection, 100, cursor)
            for chunk in page.chunks:
                searchable = f"{chunk.id}\n{chunk.text}\n{json.dumps(chunk.metadata, ensure_ascii=False)}".casefold()
                if needle in searchable and len(matches) < limit:
                    matches.append(chunk)
            cursor = page.next_cursor
            if cursor is None:
                return matches
            if cursor in seen_cursors:
                raise VectorStoreConnectionError("Vector store returned an invalid page cursor")
            seen_cursors.add(cursor)

    def delete_chunk(self, collection: str, chunk_id: str) -> DeleteChunkResponse:
        with self._lock:
            try:
                self._store.delete_chunk(collection, chunk_id)
            except VectorStoreConnectionError:
                raise
            except Exception as exc:
                raise VectorStoreConnectionError("Unable to delete collection chunk") from exc
        return DeleteChunkResponse(deleted=True, chunk_id=chunk_id)

    @property
    def status(self) -> VectorStoreConnectionResponse:
        with self._lock:
            return self._status.model_copy()
