# AGENTS.md

## Project Overview

**pRAwG** is a container-first personalized Retrieval-Augmented Generation (RAG) system. It enables users to:
- Ingest and add various document formats (PDF, DOCX, TXT, Markdown, and scanned PDFs via OCR) into personalized RAG collections.
- Manage their data, collections, and contextual knowledge base.
- Perform semantic vector searches using Chroma.
- Query their knowledge base using conversational AI powered by Google Gemini.

---

## Code Style & Architecture

### Backend (FastAPI & Python)
- **Layered Architecture**:
  - **Routers**: Maintain clean and dedicated FastAPI `APIRouter` files separated by domain/feature (e.g., documents, search, chat, collections).
  - **Managers**: Use manager classes/modules for orchestrating complex business flows, lifecycle handling, or coordinating across multiple components.
  - **Services**: Encapsulate concrete logic (e.g., text extraction, chunking, embedding generation, Chroma DB interactions, LLM calls) into dedicated service files.
- **Schemas & Responses**:
  - Always define explicit Pydantic schemas for requests, responses, and internal models.
  - Ensure every endpoint returns strongly-typed, well-structured responses with appropriate HTTP status codes.
- **Security Best Practices**:
  - Keep security at the forefront at all times.
  - Validate and sanitize all user input and uploaded file contents (prevent directory traversal, file bombs, shell injection).
  - Never log or expose sensitive credentials, tokens, or environment secrets.
  - Ensure proper error handling that prevents leaking stack traces or internal implementation details.

### Frontend (Next.js & TypeScript)
- **Layered Architecture**:
  - **App Router & Pages (`src/app/`)**: Keep page components and route layouts thin, focusing on page-level composition and layout structure.
  - **Managers & Hooks**: Use dedicated custom hooks and manager/context providers for complex business flows, lifecycle coordination, and client-side state management.
  - **Services & API Clients**: Encapsulate all API calls (e.g., document ingestion, search queries, chat streams) into dedicated typed service functions and API client modules.
  - **Components**: Build modular, reusable components separated into clean UI/presentational components and feature-specific container components.
- **Types & Schemas**:
  - Strictly type all models, props, and API request/response payloads using TypeScript interfaces and types matching backend schemas.
  - Avoid `any` or loose typing; ensure type safety across props, state, and async operations.
- **Security Best Practices**:
  - Never expose secrets or server-only credentials in client code; restrict client env vars strictly to `NEXT_PUBLIC_` prefixes where intended.
  - Sanitize all rendered user/LLM content against XSS (especially when rendering Markdown, chat messages, or document previews).
  - Validate and restrict client-side file uploads (e.g., MIME type checks, size limits) before dispatching to backend endpoints.

---

## Testing & Quality

- **Behavior Changes**: Add or update automated tests for every behavior change or new feature (both backend and frontend).
- **Verification**: Always run the relevant test suites (`pytest`, frontend tests) and linters (`npm run lint` / `eslint`) before declaring any task done.
- **Coverage**: Include unit and integration tests covering edge cases, invalid inputs, and failure scenarios.

---

## Workflow Rules

- **Minimal Diffs**: Make the smallest change that completely solves the task; do not refactor unrelated code.
- **Dependencies**: Do not add new external libraries or dependencies without explicit user permission.
- **Protected Files**: Never edit files in `/generated` or commit secrets / `.env` files.
- **Clarification**: If requirements are unclear, ask one clarifying question before beginning implementation.

---

## Communication

- **Concise Summaries**: Summarize what you changed and why in a few concise lines.
- **Transparency**: Clearly flag anything you were unsure about, assumptions made, or anything that could not be fully tested.

