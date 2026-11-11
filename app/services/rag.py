from __future__ import annotations

import logging
import traceback
from time import perf_counter

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.config import Settings
from app.schemas import (
    ChatHistoryMessage,
    ChatResponse,
    GroundedModelResponse,
    SearchResult,
    StoredDocument,
)
from app.services.object_storage import DocumentDownload, ObjectStorage
from app.services.vector_stores import VectorStoreManager

logger = logging.getLogger("uvicorn.error.prawg.chat")


class RagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.object_storage = ObjectStorage(settings)
        self.vector_stores = VectorStoreManager.from_settings(settings)
        self.genai = genai.Client(api_key=settings.google_api_key) if settings.google_api_key else None

    def heartbeat(self) -> None:
        self.object_storage.heartbeat()
        self.vector_stores.heartbeat()

    def ingest(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        text_chunks: list[str],
        metadata: dict[str, str],
    ) -> str:
        collection = self.vector_stores.status.collection
        stored_id = self.object_storage.store_document(
            filename,
            content,
            content_type,
            collection,
            len(text_chunks),
            metadata,
        )
        vector_id = self.vector_stores.ingest(filename, content, text_chunks, metadata)
        if stored_id != vector_id:
            raise RuntimeError("Document identifiers did not match")
        return stored_id

    def list_documents(self) -> list[StoredDocument]:
        return self.object_storage.list_documents()

    def get_document(self, document_id: str) -> DocumentDownload:
        return self.object_storage.get_document(document_id)

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        return self.vector_stores.search(query, top_k)

    def chat(
        self,
        question: str,
        sources: list[SearchResult],
        history: list[ChatHistoryMessage] | None = None,
        request_id: str = "untracked",
    ) -> ChatResponse:
        context = "\n\n".join(
            f"Source {index + 1} ({source.metadata.get('filename', 'unknown')}):\n{source.text}"
            for index, source in enumerate(sources)
        )
        conversation = "\n".join(
            f"{message.role.title()}: {message.content}" for message in (history or [])
        )
        prompt = (
            "Answer the latest question using only the supplied document context. "
            "Conversation history is provided only to resolve references in the latest question; "
            "do not treat it as factual source material. "
            "If the answer is not present, say that you do not know based on the indexed documents. "
            "Return the source numbers that directly support the answer. Do not cite a source merely "
            "because it was retrieved, and return no source numbers when the context does not answer "
            "the question.\n\n"
            f"Document context:\n{context or '[No relevant context found]'}\n\n"
            f"Conversation history:\n{conversation or '[No previous messages]'}\n\n"
            f"Latest question: {question}"
        )

        if self.settings.chat_provider == "ollama":
            answer = self._chat_with_ollama(prompt)
            return ChatResponse(answer=answer, sources=_deduplicate_sources(sources))
        grounded = self._chat_with_gemini(prompt, request_id)
        return ChatResponse(
            answer=grounded.answer,
            sources=_select_cited_sources(sources, grounded.cited_source_numbers),
        )

    def _chat_with_gemini(self, prompt: str, request_id: str) -> GroundedModelResponse:
        if self.genai is None:
            logger.error(
                "gemini.configuration_error request_id=%s model=%s reason=missing_api_key",
                request_id,
                self.settings.gemini_model,
            )
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        started_at = perf_counter()
        logger.info(
            "gemini.request_started request_id=%s model=%s prompt_chars=%d",
            request_id,
            self.settings.gemini_model,
            len(prompt),
        )
        try:
            response = self.genai.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GroundedModelResponse,
                ),
            )
        except genai_errors.APIError as exc:
            logger.warning(
                "gemini.api_error request_id=%s model=%s code=%s status=%s elapsed_ms=%.1f",
                request_id,
                self.settings.gemini_model,
                exc.code,
                exc.status,
                (perf_counter() - started_at) * 1000,
            )
            if exc.code in {401, 403}:
                message = "Google Gemini rejected the configured API key"
            elif exc.code == 404:
                message = f"Google Gemini model '{self.settings.gemini_model}' is unavailable"
            elif exc.code == 429:
                message = "Google Gemini rate limit or quota was exceeded"
            elif 400 <= exc.code < 500:
                message = "Google Gemini rejected the request"
            else:
                message = "Google Gemini is unavailable"
            raise RuntimeError(message) from exc
        except Exception as exc:
            logger.error(
                "gemini.unexpected_error request_id=%s model=%s exception_type=%s "
                "error=%s elapsed_ms=%.1f traceback=%s",
                request_id,
                self.settings.gemini_model,
                type(exc).__name__,
                _safe_error_message(exc, self.settings.google_api_key),
                (perf_counter() - started_at) * 1000,
                _safe_traceback(exc),
            )
            raise RuntimeError("Google Gemini is unavailable") from exc
        if not response.text:
            logger.warning(
                "gemini.empty_response request_id=%s model=%s elapsed_ms=%.1f",
                request_id,
                self.settings.gemini_model,
                (perf_counter() - started_at) * 1000,
            )
            raise RuntimeError("Google Gemini returned an empty response")
        try:
            grounded = GroundedModelResponse.model_validate(response.parsed)
        except Exception as exc:
            logger.error(
                "gemini.invalid_response request_id=%s model=%s exception_type=%s elapsed_ms=%.1f",
                request_id,
                self.settings.gemini_model,
                type(exc).__name__,
                (perf_counter() - started_at) * 1000,
            )
            raise RuntimeError("Google Gemini returned an invalid response") from exc
        logger.info(
            "gemini.request_completed request_id=%s model=%s answer_chars=%d citations=%d elapsed_ms=%.1f",
            request_id,
            self.settings.gemini_model,
            len(grounded.answer),
            len(grounded.cited_source_numbers),
            (perf_counter() - started_at) * 1000,
        )
        return grounded

    def _chat_with_ollama(self, prompt: str) -> str:
        try:
            response = httpx.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.settings.ollama_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                timeout=120.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"Ollama model '{self.settings.ollama_model}' is not installed; "
                    f"run: docker compose exec ollama ollama pull {self.settings.ollama_model}"
                ) from exc
            raise RuntimeError(f"Ollama returned HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Ollama is unavailable") from exc

        message = response.json().get("message", {})
        content = message.get("content")
        if not content:
            raise RuntimeError("Ollama returned an empty response")
        return str(content)


def _safe_error_message(exc: Exception, secret: str | None) -> str:
    message = str(exc).replace("\n", " ").replace("\r", " ")
    if secret:
        message = message.replace(secret, "[REDACTED]")
    return message[:500] or "[empty]"


def _select_cited_sources(
    sources: list[SearchResult],
    cited_source_numbers: list[int],
) -> list[SearchResult]:
    cited = [
        sources[source_number - 1]
        for source_number in cited_source_numbers
        if 1 <= source_number <= len(sources)
    ]
    return _deduplicate_sources(cited)


def _deduplicate_sources(sources: list[SearchResult]) -> list[SearchResult]:
    unique: list[SearchResult] = []
    seen: set[str] = set()
    for source in sources:
        identity = str(
            source.metadata.get("document_id")
            or source.metadata.get("filename")
            or source.id
        )
        if identity not in seen:
            unique.append(source)
            seen.add(identity)
    return unique


def _safe_traceback(exc: Exception) -> str:
    frames = traceback.extract_tb(exc.__traceback__)
    return " | ".join(
        f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in frames[-8:]
    ) or "[unavailable]"
