from __future__ import annotations

import httpx
from google import genai

from app.config import Settings
from app.schemas import SearchResult, StoredDocument
from app.services.object_storage import DocumentDownload, ObjectStorage
from app.services.vector_stores import VectorStoreManager


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

    def chat(self, question: str, sources: list[SearchResult]) -> str:
        context = "\n\n".join(
            f"Source {index + 1} ({source.metadata.get('filename', 'unknown')}):\n{source.text}"
            for index, source in enumerate(sources)
        )
        prompt = (
            "Answer the question using only the supplied context. "
            "If the answer is not present, say that you do not know based on the indexed documents.\n\n"
            f"Context:\n{context or '[No relevant context found]'}\n\nQuestion: {question}"
        )

        if self.settings.chat_provider == "ollama":
            return self._chat_with_ollama(prompt)
        return self._chat_with_gemini(prompt)

    def _chat_with_gemini(self, prompt: str) -> str:
        if self.genai is None:
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        response = self.genai.models.generate_content(model=self.settings.gemini_model, contents=prompt)
        return response.text or "The model returned an empty response."

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
