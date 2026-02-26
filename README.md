# LLM Router & Playground

An extensible agentic LLM router and playground with a React + TypeScript frontend and Python FastAPI backend.

## Features

- **Multi-provider support**: OpenAI, Anthropic, Google Gemini, Mistral, Groq, Together, Azure OpenAI, and any OpenAI-compatible local endpoint (vLLM, Ollama, LM Studio)
- **Streaming output** via Server-Sent Events
- **Run history** with SQLite persistence, pagination, and JSON export
- **Normalized responses** across all providers
- **Extensible architecture** with stubbed tool calling, memory stores, and trace support for future agentic features

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+
- npm

## Quick Start

### 1. Backend Setup

```bash
cd backend

# Copy env file and add your API keys
cp .env.example .env
# Edit .env with your keys (at minimum set OPENAI_API_KEY or ANTHROPIC_API_KEY)

# Install dependencies
uv sync

# Run the server
uv run uvicorn app.main:app --reload --port 8000
```

The backend auto-creates the SQLite database on first startup.

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Open http://localhost:5173 in your browser.

### 3. Run Tests

```bash
cd backend
uv run pytest -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check + available providers |
| `POST` | `/api/chat` | Non-streaming chat completion |
| `POST` | `/api/chat/stream` | Streaming chat via SSE |
| `GET` | `/api/runs?page=1&per_page=20` | List runs (paginated) |
| `GET` | `/api/runs/{id}` | Run detail |
| `DELETE` | `/api/runs/{id}` | Delete a run |

## Sample curl Commands

### Health check
```bash
curl http://localhost:8000/health
```

### Non-streaming chat
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "system", "content": "You are helpful."},
      {"role": "user", "content": "Say hello in 3 languages."}
    ],
    "temperature": 0.7,
    "max_tokens": 256
  }'
```

### Streaming chat
```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Count to 10 slowly."}],
    "temperature": 0.5,
    "max_tokens": 256
  }'
```

### List runs
```bash
curl http://localhost:8000/api/runs
```

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, middleware
│   │   ├── config.py            # Pydantic settings from .env
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── models.py            # SQLAlchemy Run model
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── chat.py          # POST /api/chat, /api/chat/stream
│   │   │   ├── runs.py         # GET/DELETE /api/runs
│   │   │   └── health.py       # GET /health
│   │   ├── adapters/
│   │   │   ├── base.py         # ProviderAdapter ABC
│   │   │   ├── registry.py    # Auto-discovery + registration
│   │   │   ├── openai_adapter.py
│   │   │   ├── anthropic_adapter.py
│   │   │   ├── openai_compatible_adapter.py  # For local models
│   │   │   ├── google_adapter.py
│   │   │   ├── mistral_adapter.py
│   │   │   ├── groq_adapter.py
│   │   │   ├── together_adapter.py
│   │   │   └── azure_openai_adapter.py
│   │   ├── middleware/
│   │   │   └── request_logging.py  # Request ID + structured logging
│   │   └── agentic/
│   │       ├── tools.py        # Tool registry stub
│   │       ├── memory.py       # Memory store interface stub
│   │       └── traces.py      # Trace context stub
│   ├── tests/
│   ├── migrations/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── .env.example
│
└── frontend/
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css            # Global styles (dark theme)
        ├── api/
        │   ├── client.ts        # Typed fetch wrapper
        │   └── types.ts         # TypeScript interfaces
        ├── hooks/
        │   └── useStream.ts     # SSE streaming hook
        ├── pages/
        │   ├── Playground.tsx   # Main playground UI
        │   ├── History.tsx     # Run history table
        │   └── RunDetail.tsx   # Single run detail + export
        └── components/
            ├── Layout.tsx      # App shell with nav
            ├── StreamOutput.tsx # Streaming text display
            └── MetadataPanel.tsx # Response metadata grid
```

## Adding a New Provider

1. Create `backend/app/adapters/my_provider_adapter.py` implementing `ProviderAdapter`
2. Add the config key to `backend/app/config.py`
3. Import and add to `_ALL_ADAPTERS` in `backend/app/adapters/registry.py`
4. Add the env var to `.env.example`
5. Add the provider option to the frontend's `ALL_PROVIDERS` array in `Playground.tsx`

## Architecture Notes (v2 Roadmap)

- **Tool calling**: `agentic/tools.py` defines `Tool` + `ToolRegistry`. Wire into adapters that support function calling.
- **Multi-step traces**: `Run.trace_id` and `Run.parent_run_id` enable tree-structured runs.
- **Memory**: `agentic/memory.py` defines a pluggable `MemoryStore` interface.
- **Background jobs**: Add Celery/ARQ for long-running multi-step agent loops.
- **Auth**: Add middleware + user model; schema already avoids multi-tenant blockers.

## License

MIT
