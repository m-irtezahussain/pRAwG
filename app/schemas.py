from pydantic import BaseModel, ConfigDict, Field


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
