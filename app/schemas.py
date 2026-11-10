import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: str


class IngestResponse(StrictModel):
    document_id: str
    filename: str
    chunks: int
    characters: int
    ocr_used: bool
    stored: bool
    metadata: dict[str, str]


MetadataKey = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")]
MetadataValue = Annotated[str, Field(min_length=1, max_length=500)]


class DocumentMetadata(StrictModel):
    values: dict[MetadataKey, MetadataValue] = Field(default_factory=dict, max_length=20)

    @model_validator(mode="after")
    def validate_metadata(self) -> "DocumentMetadata":
        reserved = {"document_id", "filename", "chunk_index", "source_id", "text"}
        normalized_keys = [key.lower() for key in self.values]
        if reserved.intersection(normalized_keys):
            raise ValueError("Custom metadata uses a reserved key")
        if len(normalized_keys) != len(set(normalized_keys)):
            raise ValueError("Custom metadata keys must be unique")
        serialized = json.dumps(self.values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(serialized) > 1024:
            raise ValueError("Custom metadata is too large")
        return self


class StoredDocument(StrictModel):
    document_id: str
    filename: str
    size: int = Field(ge=0)
    content_type: str
    collection: str
    chunks: int = Field(ge=0)
    uploaded_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)


class StoredDocumentListResponse(StrictModel):
    documents: list[StoredDocument]


class SearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=25)


class SearchResult(StrictModel):
    id: str
    text: str
    distance: float | None = None
    metadata: dict[str, str | int | float | bool]


class SearchResponse(StrictModel):
    results: list[SearchResult]


class ChatRequest(StrictModel):
    question: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=25)


class ChatResponse(StrictModel):
    answer: str
    sources: list[SearchResult]


CollectionName = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]


class SelfHostedChromaConnection(StrictModel):
    provider: Literal["chroma_self_hosted"]
    endpoint: AnyHttpUrl
    collection: CollectionName
    tenant: str = Field(default="default_tenant", min_length=1, max_length=128)
    database: str = Field(default="default_database", min_length=1, max_length=128)
    auth_token: SecretStr | None = None


class CloudChromaConnection(StrictModel):
    provider: Literal["chroma_cloud"]
    api_key: SecretStr = Field(min_length=1, max_length=2048)
    tenant: str = Field(min_length=1, max_length=128)
    database: str = Field(min_length=1, max_length=128)
    collection: CollectionName


class CloudPineconeConnection(StrictModel):
    provider: Literal["pinecone_cloud"]
    api_key: SecretStr = Field(min_length=1, max_length=2048)
    index_name: str = Field(min_length=1, max_length=45, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
    namespace: str = Field(default="", max_length=128)


class SelfHostedQdrantConnection(StrictModel):
    provider: Literal["qdrant_self_hosted"]
    endpoint: AnyHttpUrl
    collection: CollectionName
    api_key: SecretStr | None = None


class CloudQdrantConnection(StrictModel):
    provider: Literal["qdrant_cloud"]
    endpoint: AnyHttpUrl
    api_key: SecretStr = Field(min_length=1, max_length=2048)
    collection: CollectionName

    @model_validator(mode="after")
    def validate_cloud_endpoint(self) -> "CloudQdrantConnection":
        hostname = self.endpoint.host or ""
        if self.endpoint.scheme != "https" or not hostname.endswith(".cloud.qdrant.io"):
            raise ValueError("Cloud Qdrant endpoint must be an HTTPS cloud.qdrant.io URL")
        return self


VectorStoreConnection = Annotated[
    SelfHostedChromaConnection
    | CloudChromaConnection
    | CloudPineconeConnection
    | SelfHostedQdrantConnection
    | CloudQdrantConnection,
    Field(discriminator="provider"),
]


class VectorStoreConnectionResponse(StrictModel):
    provider: Literal[
        "chroma_self_hosted",
        "chroma_cloud",
        "pinecone_cloud",
        "qdrant_self_hosted",
        "qdrant_cloud",
    ]
    label: str
    collection: str
    connected: bool


class VectorCollectionSummary(StrictModel):
    name: str
    kind: Literal["collection", "namespace"]
    records: int | None = Field(default=None, ge=0)
    active: bool


class VectorCollectionListResponse(StrictModel):
    provider: Literal[
        "chroma_self_hosted",
        "chroma_cloud",
        "pinecone_cloud",
        "qdrant_self_hosted",
        "qdrant_cloud",
    ]
    collections: list[VectorCollectionSummary]


class VectorChunk(StrictModel):
    id: str
    text: str
    metadata: dict[str, JsonValue]
    score: float | None = None


class VectorChunkPage(StrictModel):
    collection: str
    chunks: list[VectorChunk]
    total: int | None = Field(default=None, ge=0)
    next_cursor: str | None = None


class CollectionSearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=10_000)
    mode: Literal["similarity", "text"]
    limit: int = Field(default=25, ge=1, le=100)


class CollectionSearchResponse(StrictModel):
    collection: str
    mode: Literal["similarity", "text"]
    chunks: list[VectorChunk]


class DeleteChunkResponse(StrictModel):
    deleted: bool
    chunk_id: str
