import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from app.config import Settings
from app.main import create_app
from app.schemas import (
    ChatHistoryMessage,
    ChatResponse,
    GroundedModelResponse,
    SearchResult,
)
from app.services.rag import RagService


def _ollama_service() -> RagService:
    service = RagService.__new__(RagService)
    service.settings = Settings(
        chat_provider="ollama",
        ollama_base_url="http://ollama:11434",
        ollama_model="gemma3:1b",
    )
    service.genai = None
    return service


def test_chat_uses_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        assert url == "http://ollama:11434/api/chat"
        json_body = kwargs["json"]
        assert isinstance(json_body, dict)
        assert json_body["model"] == "gemma3:1b"
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Local answer"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    source = SearchResult(id="1", text="Context", metadata={"filename": "notes.txt"})

    response = _ollama_service().chat("Question?", [source])

    assert response.answer == "Local answer"
    assert response.sources == [source]


def test_chat_explains_how_to_install_missing_ollama_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **_: object) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(RuntimeError, match="docker compose exec ollama ollama pull gemma3:1b"):
        _ollama_service().chat("Question?", [])


class FakeModels:
    def __init__(
        self,
        text: str | None = "Gemini answer",
        cited_source_numbers: list[int] | None = None,
    ) -> None:
        self.text = text
        self.cited_source_numbers = cited_source_numbers or []
        self.prompt = ""

    def generate_content(self, *, model: str, contents: str, config: object) -> object:
        assert model == "gemini-3.8-flash"
        assert config is not None
        self.prompt = contents
        parsed = None
        if self.text is not None:
            parsed = {
                "answer": self.text,
                "cited_source_numbers": self.cited_source_numbers,
            }
        return type("Response", (), {"text": self.text, "parsed": parsed})()


def _gemini_service(models: FakeModels) -> RagService:
    service = RagService.__new__(RagService)
    service.settings = Settings(chat_provider="gemini", google_api_key="test-key")
    service.genai = type("FakeClient", (), {"models": models})()
    return service


def test_chat_uses_gemini_with_context_and_bounded_history() -> None:
    models = FakeModels(cited_source_numbers=[1])
    source = SearchResult(id="1", text="Grounded fact", metadata={"filename": "notes.txt"})
    history = [ChatHistoryMessage(role="user", content="Earlier question")]

    response = _gemini_service(models).chat("Follow-up?", [source], history)

    assert response.answer == "Gemini answer"
    assert response.sources == [source]
    assert "Grounded fact" in models.prompt
    assert "User: Earlier question" in models.prompt
    assert "Latest question: Follow-up?" in models.prompt


def test_chat_logs_gemini_client_failures_without_exposing_api_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingModels(FakeModels):
        def generate_content(self, *, model: str, contents: str, config: object) -> object:
            raise ValueError("transport failed using test-key")

    with (
        caplog.at_level("ERROR", logger="uvicorn.error.prawg.chat"),
        pytest.raises(RuntimeError, match="Google Gemini is unavailable"),
    ):
        _gemini_service(FailingModels()).chat("Question?", [], request_id="request-123")

    assert "gemini.unexpected_error request_id=request-123" in caplog.text
    assert "exception_type=ValueError" in caplog.text
    assert "error=transport failed using [REDACTED]" in caplog.text
    assert "test-key" not in caplog.text


@pytest.mark.parametrize(
    ("code", "expected_message"),
    [
        (403, "Google Gemini rejected the configured API key"),
        (404, "Google Gemini model 'gemini-3.8-flash' is unavailable"),
        (429, "Google Gemini rate limit or quota was exceeded"),
        (500, "Google Gemini is unavailable"),
    ],
)
def test_chat_maps_gemini_api_failures(code: int, expected_message: str) -> None:
    class FailingModels(FakeModels):
        def generate_content(self, *, model: str, contents: str, config: object) -> object:
            raise genai_errors.APIError(code, {"error": {"code": code, "status": "ERROR"}})

    with pytest.raises(RuntimeError, match=expected_message):
        _gemini_service(FailingModels()).chat("Question?", [])


def test_chat_rejects_empty_gemini_response() -> None:
    with pytest.raises(RuntimeError, match="Google Gemini returned an empty response"):
        _gemini_service(FakeModels(text=None)).chat("Question?", [])


def test_chat_returns_only_cited_document_and_deduplicates_its_chunks() -> None:
    sources = [
        SearchResult(id="a-1", text="Candidate A", metadata={"document_id": "a", "filename": "a.pdf"}),
        SearchResult(id="b-1", text="Supporting fact", metadata={"document_id": "b", "filename": "b.pdf"}),
        SearchResult(id="b-2", text="More support", metadata={"document_id": "b", "filename": "b.pdf"}),
    ]

    response = _gemini_service(FakeModels(cited_source_numbers=[2, 3, 99])).chat("Question?", sources)

    assert [source.id for source in response.sources] == ["b-1"]


def test_gemini_response_schema_avoids_unsupported_additional_properties() -> None:
    assert "additionalProperties" not in GroundedModelResponse.model_json_schema()


def test_chat_endpoint_passes_validated_history_to_rag_service() -> None:
    class FakeRag:
        def search(self, query: str, top_k: int) -> list[SearchResult]:
            assert query == "What changed?"
            assert top_k == 3
            return [SearchResult(id="source-1", text="Context", metadata={"filename": "notes.txt"})]

        def chat(
            self,
            question: str,
            sources: list[SearchResult],
            history: list[ChatHistoryMessage],
            request_id: str,
        ) -> ChatResponse:
            assert question == "What changed?"
            assert sources[0].id == "source-1"
            assert history == [ChatHistoryMessage(role="user", content="Summarize it")]
            assert request_id
            return ChatResponse(answer="Grounded answer", sources=[sources[0]])

    api = create_app()
    api.state.rag = FakeRag()
    response = TestClient(api).post(
        "/api/v1/chat",
        json={
            "question": "What changed?",
            "top_k": 3,
            "history": [{"role": "user", "content": "Summarize it"}],
        },
    )

    assert response.status_code == 200
    assert len(response.headers["x-request-id"]) == 12
    assert response.json()["answer"] == "Grounded answer"
    assert response.json()["sources"][0]["id"] == "source-1"


def test_chat_endpoint_rejects_more_than_twenty_history_messages() -> None:
    response = TestClient(create_app()).post(
        "/api/v1/chat",
        json={
            "question": "Question?",
            "history": [{"role": "user", "content": "Earlier"}] * 21,
        },
    )

    assert response.status_code == 422
