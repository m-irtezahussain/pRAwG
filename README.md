# pRAwG

A container-first personalized retrieval-augmented generation (RAG) API. The
starter stack contains:

- FastAPI for document ingestion, semantic search, and chat
- Chroma in its own persistent container
- PDF, DOCX, Markdown, and plain-text extraction
- OCR for scanned PDFs with Tesseract inside the Linux API container
- Ollama as a persistent local-model microservice
- Selectable Ollama or Google Gemini chat generation

## Quick start

1. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

2. Build and start the stack:

   ```bash
   docker compose up --build --watch
   ```

3. Pull the default Ollama model once:

   ```bash
   docker compose exec ollama ollama pull gemma3:1b
   ```

4. Open the API docs at <http://127.0.0.1:8080/docs>.

Chroma is available to the host at <http://127.0.0.1:8000> and Ollama at
<http://127.0.0.1:11434>. All published ports bind only to loopback.

The default chat provider is Ollama with `gemma3:1b`. To use Gemini instead,
set these values in `.env` and restart the API:

```dotenv
CHAT_PROVIDER=gemini
GOOGLE_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
```

## API

- `GET /health/live` - process liveness
- `GET /health/ready` - Chroma connectivity
- `POST /api/v1/documents` - ingest a PDF, DOCX, TXT, or Markdown document
- `POST /api/v1/search` - return relevant chunks
- `POST /api/v1/chat` - retrieve context and ask the configured chat provider

Example ingestion:

```bash
curl -F 'file=@./document.pdf' http://127.0.0.1:8080/api/v1/documents
```

Example chat:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"What are the main points?","top_k":5}'
```

## OCR and Apple Vision

Apple Vision OCR cannot run inside this Docker stack. Docker Desktop runs Linux
containers in a Linux VM, while Vision is a macOS-only framework and is not
present in Linux images. This stack therefore uses Tesseract for scanned PDF
pages inside the container. The extraction code is isolated in
`app/services/documents.py`, so a future macOS host-side Vision service can be
added without changing the API contract.

## Development

```bash
docker compose run --rm api pytest
docker compose run --rm --no-deps api ruff check --no-cache app tests
docker compose config --quiet
```

Application source changes are synchronized into the API container by Compose
Watch. Changes to dependency files or the Dockerfile trigger an image rebuild.

Data is kept in the `chroma-data` named volume and the local embedding-model
cache in `embedding-cache`. Ollama models are kept in `ollama-data`.
`docker compose down` keeps these volumes; `docker compose down -v`
permanently deletes them.

## Ollama on macOS

The Ollama container works on Docker Desktop for macOS, but Linux containers do
not get direct access to Apple's Metal acceleration. For substantially faster
local inference on Apple Silicon, run Ollama natively on macOS and set
`OLLAMA_BASE_URL` for the API to a host-reachable address. The containerized
service is retained here for portability and isolation.
