# pRAwG

A container-first personalized retrieval-augmented generation (RAG) API. The
starter stack contains:

- FastAPI for document ingestion, semantic search, and chat
- A switchable vector-store layer for self-hosted or cloud Chroma, Pinecone,
  and self-hosted or cloud Qdrant
- PDF, DOCX, XLSX, CSV, Markdown, and plain-text extraction
- OCR for scanned PDFs with Tesseract inside the Linux API container
- MinIO object storage for durable original-document retrieval
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

4. Open the frontend at <http://127.0.0.1:3000> and the API docs at
   <http://127.0.0.1:8080/docs>.

Chroma is available to the host at <http://127.0.0.1:8000>, MinIO's S3 API at
<http://127.0.0.1:9000>, the MinIO console at <http://127.0.0.1:9001>, and
Ollama at <http://127.0.0.1:11434>. All published ports bind only to loopback.
The local MinIO login is configured by `MINIO_ROOT_USER` and
`MINIO_ROOT_PASSWORD` in `.env`; replace the development defaults outside a
local environment.

The default chat provider is Ollama with `gemma3:1b`. To use Gemini instead,
set these values in `.env` and restart the API:

```dotenv
CHAT_PROVIDER=gemini
GOOGLE_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
```

Embeddings are generated through Ollama. The default expects the existing
`nomic-embed-text-v2-moe:latest` model; override it when needed:

```dotenv
OLLAMA_EMBEDDING_MODEL=your-embedding-model
```

## API

- `GET /health/live` - process liveness
- `GET /health/ready` - active vector-store and object-storage connectivity
- `GET /api/v1/vector-store/connection` - sanitized active connection status
- `POST /api/v1/vector-store/connections` - test and activate a vector-store connection
- `POST /api/v1/documents` - store and ingest a PDF, DOCX, XLSX, CSV, TXT, or Markdown document
- `GET /api/v1/documents` - list stored original documents
- `GET /api/v1/documents/{document_id}/content` - download an original document
- `POST /api/v1/search` - return relevant chunks
- `POST /api/v1/chat` - retrieve context and ask the configured chat provider

Example ingestion:

```bash
curl \
  -F 'file=@./document.pdf' \
  -F 'filename=research-summary.pdf' \
  -F 'metadata={"author":"Ada","project":"Knowledge base"}' \
  http://127.0.0.1:8080/api/v1/documents
```

The management screen opens a metadata dialog after file selection. Users can
rename the file without changing its extension and add up to 20 custom key/value
fields. Custom metadata is stored with the MinIO object and copied onto every
indexed vector chunk, making it visible and searchable in the collection explorer.

Example chat:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"What are the main points?","top_k":5}'
```

Vector-store credentials submitted from the management screen are kept only in
API process memory and are never returned by the API or saved to browser
storage. The default self-hosted Chroma connection is restored after an API
restart. Existing Pinecone and Qdrant indexes must match the configured Ollama
model's embedding dimension; new Qdrant collections are created with that
dimension and cosine distance.

Accepted uploads are validated, stored in the private MinIO bucket under their
SHA-256 content identifier, and then indexed in the active vector database.
The Cloud screen reads this stored-document catalog and provides download links
for the original files. MinIO object metadata is the current catalog; a future
multi-user deployment should add authenticated ownership records and malware
scanning before making uploads broadly available.

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

Frontend and API source changes are synchronized into their containers by
Compose Watch. Changes to dependency files or Dockerfiles trigger an image
rebuild.

Data is kept in the `chroma-data` named volume, original documents in
`minio-data`, and the local embedding-model cache in `embedding-cache`. Ollama
models are kept in `ollama-data`.
`docker compose down` keeps these volumes; `docker compose down -v`
permanently deletes them.

The upstream MinIO Community repository no longer publishes its historical
binary container image. This project therefore builds MinIO from a pinned
official source commit in `docker/minio/Dockerfile`, making builds reproducible
while retaining MinIO's standard S3-compatible API and console.

## Ollama on macOS

The Ollama container works on Docker Desktop for macOS, but Linux containers do
not get direct access to Apple's Metal acceleration. For substantially faster
local inference on Apple Silicon, run Ollama natively on macOS and set
`OLLAMA_BASE_URL` for the API to a host-reachable address. The containerized
service is retained here for portability and isolation.
