from __future__ import annotations

import hashlib
from typing import Any

import chromadb
import httpx
from google import genai

from app.config import Settings
from app.schemas import SearchResult


class RagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.chroma = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        self.collection = self.chroma.get_or_create_collection(name=settings.chroma_collection)
        self.genai = genai.Client(api_key=settings.google_api_key) if settings.google_api_key else None

    def heartbeat(self) -> int:
        return self.chroma.heartbeat()

    def ingest(self, filename: str, content: bytes, text_chunks: list[str]) -> str:
        document_id = hashlib.sha256(content).hexdigest()
        ids = [f"{document_id}:{index}" for index in range(len(text_chunks))]
        metadatas = [
            {"document_id": document_id, "filename": filename, "chunk_index": index}
            for index in range(len(text_chunks))
        ]
        self.collection.upsert(ids=ids, documents=text_chunks, metadatas=metadatas)
        return document_id

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        result: dict[str, Any] = self.collection.query(
            query_texts=[query],
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
