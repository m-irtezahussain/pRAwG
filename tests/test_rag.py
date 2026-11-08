import httpx
import pytest

from app.config import Settings
from app.schemas import SearchResult
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

    assert _ollama_service().chat("Question?", [source]) == "Local answer"


def test_chat_explains_how_to_install_missing_ollama_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **_: object) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(RuntimeError, match="docker compose exec ollama ollama pull gemma3:1b"):
        _ollama_service().chat("Question?", [])
