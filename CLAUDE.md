# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **LLM Router & Playground** — a full-stack app that routes chat requests to multiple LLM providers (OpenAI, Anthropic, Google, Mistral, Groq, etc.) through a unified API, with a React frontend for interactive testing and run history.

## Development Commands

### Backend

```bash
cd backend
uv sync                                              # Install dependencies
uv run uvicorn app.main:app --reload --port 8000     # Dev server
uv run pytest -v                                     # Run all tests
uv run pytest -v tests/test_api.py                  # Run a single test file
uv run pytest -v tests/test_api.py::test_name       # Run a single test
uv run ruff check .                                  # Lint
uv run ruff format .                                 # Format
```

### Frontend

```bash
cd frontend
npm install
npm run dev       # Dev server on http://localhost:5173
npm run build     # Production build
npm run lint      # ESLint
npm run format    # Prettier
```

### Docker (both services)

```bash
docker-compose up
```

## Environment Setup

Copy `backend/.env.example` to `backend/.env` and fill in API keys. All provider keys are optional — adapters auto-disable if credentials are missing:

```
OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, MISTRAL_API_KEY,
GROQ_API_KEY, TOGETHER_API_KEY, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT
LOCAL_OPENAI_BASE_URL=http://localhost:11434/v1   # for Ollama/vLLM/LM Studio
DATABASE_URL=sqlite+aiosqlite:///./llm_router.db
CORS_ORIGINS=["http://localhost:5173"]
```

The SQLite database is auto-created on first startup (no manual migration needed in dev).

## Architecture

### Request Flow

Frontend (`:5173`) → Vite proxy → Backend FastAPI (`:8000`) → Provider Adapter → LLM API

Streaming uses Server-Sent Events (SSE). Every request (streaming or not) is persisted as a `Run` record in SQLite.

### Backend (`backend/app/`)

- **`main.py`** — App entrypoint. Lifespan creates DB tables and initializes the adapter registry. Includes CORS and request-logging middleware.
- **`adapters/`** — Core extension point. Each provider implements the `ProviderAdapter` ABC (`base.py`): `is_available()`, `chat()`, `stream_chat()`, `list_models()`. `registry.py` auto-discovers and registers all adapters whose credentials are present. Currently fully implemented: OpenAI, Anthropic, OpenAI-compatible (Ollama/vLLM). Stubs exist for: Google, Mistral, Groq, Together, Azure OpenAI.
- **`routers/`** — Three routers: `chat.py` (`/api/chat`, `/api/chat/stream`), `health.py` (`/health`, `/api/providers/{provider}/models`), `runs.py` (CRUD for run history).
- **`models.py` / `schemas.py`** — SQLAlchemy `Run` ORM model; Pydantic schemas for `ChatRequest`, `NormalizedChatResponse`, and SSE events (`DeltaEvent`, `MetaEvent`, `FinalEvent`, `ErrorEvent`).
- **`agentic/`** — Stubs for v2 agentic features: `tools.py` (ToolRegistry/Tool ABC), `memory.py` (MemoryStore ABC + InMemoryStore), `traces.py` (TraceContext). The `Run` model already has `trace_id` and `parent_run_id` fields for multi-step tracing.

### Frontend (`frontend/src/`)

- **`api/client.ts`** — Typed fetch wrapper for all backend endpoints. `api/types.ts` mirrors backend Pydantic schemas.
- **`hooks/useStream.ts`** — Manages SSE connection; parses `delta`/`meta`/`final`/`error` events.
- **Routes:** `/` (Playground), `/history` (paginated run table), `/runs/:id` (run detail + JSON export).
- **Vite proxy** (`vite.config.ts`) forwards `/api` and `/health` to `http://localhost:8000`.

### Adding a New Provider

1. Create `backend/app/adapters/{provider}_adapter.py` implementing `ProviderAdapter`
2. Add env var(s) to `.env.example` and `config.py`
3. Register in `adapters/registry.py`
4. Add the provider option to the frontend's provider selector in `Playground.tsx`

## Key Conventions

- **Async-first:** All DB and provider calls use `async/await`. Use `AsyncSession` from `database.py`.
- **Normalized responses:** All providers must return `NormalizedChatResponse` — never expose provider-specific response shapes to the router layer.
- **SSE stream format:** Yield `data: <json>\n\n` with typed event objects. The frontend's `useStream.ts` expects `delta`, `meta`, `final`, and `error` event types.
- **Package manager:** Backend uses `uv` (not pip/poetry). Frontend uses `npm`.
- **Linting:** Backend uses `ruff` (not black/flake8). Frontend uses ESLint + Prettier.
- **Tests:** `asyncio_mode = "auto"` is set — no need for `@pytest.mark.asyncio`. Use the `client` and `db_session` fixtures from `conftest.py`.
