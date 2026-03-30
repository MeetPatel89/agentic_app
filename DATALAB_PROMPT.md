# DataLab — Greenfield Build Prompt

Build a full-stack application called **DataLab** — a natural language to SQL interface that lets users describe questions in plain English and get production-quality SQL queries back. The app routes requests to multiple LLM providers (OpenAI, Anthropic, Google, etc.) through a unified adapter pattern, validates generated SQL, and optionally executes it against a connected database.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async), Pydantic v2, uvicorn |
| Frontend | React 19, TypeScript (strict), Vite, React Router v7 |
| Database | SQLite (dev default), PostgreSQL, or Azure SQL via async drivers |
| SQL Parsing | sqlglot (syntax validation, transpilation, sandbox execution) |
| LLM SDKs | openai, anthropic (async clients) |
| Streaming | Server-Sent Events (SSE) over HTTP |
| Package Mgmt | Backend: uv · Frontend: npm |
| Linting | Backend: ruff · Frontend: ESLint + Prettier |
| CSS | Custom CSS variables (no Tailwind) with dark/light/blue themes |

---

## Project Structure

```
datalab/
├── backend/
│   ├── app/
│   │   ├── adapters/          # LLM provider implementations
│   │   │   ├── __init__.py
│   │   │   ├── base.py        # ProviderAdapter ABC + stream event types
│   │   │   ├── registry.py    # Auto-discover & register available adapters
│   │   │   ├── openai_adapter.py
│   │   │   └── anthropic_adapter.py
│   │   ├── nl2sql/            # Core NL-to-SQL module
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py     # Request/response Pydantic models
│   │   │   ├── prompts.py     # System prompt templates & dialect guidance
│   │   │   ├── service.py     # Generation logic, LLM response parsing
│   │   │   ├── sandbox.py     # SQL validation & in-memory SQLite sandbox
│   │   │   ├── executor.py    # Execute SQL against the app database
│   │   │   └── router.py      # FastAPI route handlers
│   │   ├── main.py            # App entrypoint, lifespan, middleware
│   │   ├── config.py          # pydantic-settings environment config
│   │   ├── database.py        # Async engine, session factory, get_db dependency
│   │   ├── models.py          # SQLAlchemy ORM models (Run)
│   │   └── schemas.py         # Shared Pydantic schemas (ChatRequest, stream events)
│   ├── tests/
│   │   ├── conftest.py        # Fixtures: in-memory DB, async test client
│   │   ├── test_nl2sql_api.py # Route-level tests
│   │   └── test_nl2sql_service.py  # Service logic + parsing tests
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── migrations/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts      # Typed fetch wrapper for all endpoints
│   │   │   └── types.ts       # TypeScript mirrors of backend schemas
│   │   ├── components/
│   │   │   ├── Layout.tsx      # App chrome: header, nav, theme selector
│   │   │   ├── DialectSelector.tsx
│   │   │   ├── SchemaPromptEditor.tsx
│   │   │   ├── SQLOutput.tsx
│   │   │   ├── ValidationPanel.tsx
│   │   │   ├── ResultsTable.tsx
│   │   │   └── ConnectionConfig.tsx
│   │   ├── hooks/
│   │   │   └── useTheme.ts    # Theme persistence (localStorage)
│   │   ├── pages/
│   │   │   └── DataLab.tsx    # Main page: orchestrates entire NL2SQL flow
│   │   ├── App.tsx            # Route setup
│   │   ├── main.tsx           # React entrypoint
│   │   └── index.css          # Global styles + CSS variable themes
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── docker-compose.yml
└── README.md
```

---

## 1. Backend Specification

### 1.1 Adapter Pattern — Multi-Provider LLM Support

All LLM providers implement a common abstract base class. This is the core extension point.

**`adapters/base.py`** — Abstract base class and stream event types:

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

@dataclass
class StreamDelta:
    type: str = "delta"
    text: str = ""

@dataclass
class StreamMeta:
    type: str = "meta"
    provider: str = ""
    model: str = ""

@dataclass
class StreamFinal:
    type: str = "final"
    response: "NormalizedChatResponse | None" = None

@dataclass
class StreamError:
    type: str = "error"
    message: str = ""

StreamEvent = StreamDelta | StreamMeta | StreamFinal | StreamError

class ProviderAdapter(ABC):
    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if provider credentials are configured."""

    @abstractmethod
    async def chat(self, req: "ChatRequest") -> "NormalizedChatResponse":
        """Non-streaming chat completion."""

    @abstractmethod
    def stream_chat(self, req: "ChatRequest") -> AsyncIterator[StreamEvent]:
        """Yield streaming events: delta → meta → final (or error)."""

    async def list_models(self) -> list[str]:
        return []
```

**`adapters/registry.py`** — Auto-discovers and registers adapters whose credentials are present:

- On startup (`init_registry()`), instantiate all adapter classes and register those where `is_available()` returns True.
- Expose `get_adapter(name)`, `list_providers()`, `all_provider_names()`.

**Adapter implementations:**

- **OpenAI** (`openai_adapter.py`): Uses `AsyncOpenAI` client. Detects reasoning models (`/^(o\d|gpt-5)/i`) and disables `temperature` for them. Supports `response_format` with JSON schema for structured output. Streams via `client.chat.completions.create(stream=True)`.
- **Anthropic** (`anthropic_adapter.py`): Uses `AsyncAnthropic` client. Splits system prompt from messages (Anthropic API requires system as a separate parameter). Streams via `client.messages.stream()` async context manager.

Both adapters must return `NormalizedChatResponse` — never expose provider-specific response shapes.

### 1.2 Core Schemas

**`schemas.py`** — Shared Pydantic models for the chat layer:

```python
class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] | None = None

class ChatRequest(BaseModel):
    provider: str
    model: str
    messages: list[Message]
    temperature: float | None = 0.7
    max_tokens: int = 2048
    tools: list[dict] | None = None
    tool_choice: str | None = None
    provider_options: dict[str, Any] = {}

class UsageInfo(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

class NormalizedChatResponse(BaseModel):
    output_text: str
    finish_reason: str | None = None
    provider_response_id: str | None = None
    usage: UsageInfo | None = None
    tool_calls: list[ToolCall] | None = None
    raw: dict[str, Any] | None = None
```

### 1.3 NL2SQL Module

This is the heart of DataLab.

#### `nl2sql/schemas.py` — NL2SQL-specific types:

```python
class SQLDialect(StrEnum):
    postgresql = "postgresql"
    tsql = "tsql"
    mysql = "mysql"
    sqlite = "sqlite"
    bigquery = "bigquery"
    snowflake = "snowflake"

class NL2SQLRequest(BaseModel):
    provider: str
    model: str
    natural_language: str  # min_length=1
    dialect: SQLDialect = SQLDialect.postgresql
    system_prompt: str | None = None   # Schema context, few-shot examples
    temperature: float | None = 0.7
    max_tokens: int = 2048
    sandbox_ddl: str | None = None     # DDL for in-memory validation
    conversation_history: list[NL2SQLHistoryMessage] | None = None
    provider_options: dict[str, Any] = {}

class NL2SQLHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class SQLQuery(BaseModel):
    title: str
    sql: str
    explanation: str

class NL2SQLResponse(BaseModel):
    generated_sql: str        # SQL from recommended query
    explanation: str           # Explanation from recommended query
    queries: list[SQLQuery]    # All generated variants
    recommended_index: int     # 0-based index of recommended query
    assumptions: list[str]     # Assumptions made about schema/data
    dialect: SQLDialect
    validation: SQLValidationResult
    usage: dict[str, int | None] = {}
    run_id: str | None = None
    latency_ms: float | None = None
    raw_llm_output: str | None = None

class SQLValidationResult(BaseModel):
    is_valid: bool
    syntax_errors: list[str] = []
    transpiled_sql: str | None = None
    sandbox_execution_success: bool | None = None
    sandbox_error: str | None = None

class SQLValidateRequest(BaseModel):
    sql: str
    dialect: SQLDialect
    sandbox_ddl: str | None = None

class SQLExecuteRequest(BaseModel):
    sql: str
    dialect: SQLDialect
    timeout_seconds: int = 30    # range 1-300
    max_rows: int = 1000         # range 1-50000
    read_only: bool = True       # always enforced server-side

class SQLExecuteResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool
```

#### `nl2sql/prompts.py` — Prompt engineering:

The system prompt is critical. It instructs the LLM to return a structured JSON response with multiple query variants.

**Dialect-specific guidance** — a dict mapping each `SQLDialect` to a paragraph of dialect-specific SQL rules:

| Dialect | Key guidance |
|---------|-------------|
| PostgreSQL | Double-quoted identifiers, ILIKE, generate_series, arrays, CTEs |
| T-SQL | Square brackets, TOP instead of LIMIT, GETDATE(), ISNULL(), # temp tables |
| MySQL | Backticks, LIMIT, IFNULL(), DATE_FORMAT, STR_TO_DATE |
| SQLite | TEXT/INTEGER/REAL/BLOB types, no ALTER COLUMN, \|\| concat, strftime() |
| BigQuery | Backticks for project.dataset.table, STRUCT, ARRAY, SAFE_ functions |
| Snowflake | Double-quoted case-sensitive identifiers, FLATTEN, QUALIFY, TRY_ functions |

**Default system prompt template:**

```
You are an expert SQL engineer. Your task is to convert natural language questions
into precise, production-quality SQL queries.

## Database Schema
{schema_context}

## SQL Dialect
{dialect_guidance}

## Instructions
- Generate one or more SQL query approaches for the given question.
- When the question has multiple valid interpretations or approaches (e.g., with/without
  handling ties, different performance tradeoffs, strict vs. lenient matching), provide each
  as a separate query.
- For straightforward questions with one clear answer, a single query is fine.
- Set `recommended_index` to the 0-based index of the query you recommend most.
- List any assumptions you made about the schema or data in `assumptions`.

## SQL Rules
- Use meaningful table aliases.
- Prefer explicit JOINs over implicit comma-joins.
- Always qualify column names with table aliases when the query involves multiple tables.
- Use parameterized-style placeholders ($1, :param, or ?) only if the question implies user input.
- Avoid SELECT * in production queries — select only needed columns.
- Use CTEs (WITH clauses) for complex multi-step queries for readability.
- Add appropriate WHERE clauses for safety on UPDATE/DELETE statements.

## Response Format
You MUST respond with a JSON object and nothing else. No markdown fences, no commentary
outside the JSON. The JSON must match this exact structure:

{
  "queries": [
    {
      "title": "Short descriptive title for this approach",
      "sql": "The SQL query text",
      "explanation": "Brief explanation of what this query does and any tradeoffs"
    }
  ],
  "recommended_index": 0,
  "assumptions": ["Any assumptions made about the schema, data, or ambiguous terms"]
}

Rules for the JSON response:
- `queries` must contain at least one entry.
- Each `sql` value must be a single, complete SQL statement.
- `recommended_index` must be a valid index into the `queries` array.
- `assumptions` may be an empty array if no assumptions were needed.
```

**JSON Schema for structured output** (used with OpenAI-family `response_format`):

```python
NL2SQL_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "sql": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["title", "sql", "explanation"],
                "additionalProperties": False,
            },
        },
        "recommended_index": {"type": "integer"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["queries", "recommended_index", "assumptions"],
    "additionalProperties": False,
}
```

Only these providers support the JSON schema response_format: `{"openai", "local_openai_compatible", "azure_openai"}`.

**`build_system_prompt()`** function:
- If `custom_prompt` provided (from the user's system_prompt field), use it as-is but append dialect guidance if `{dialect_guidance}` placeholder isn't present.
- Otherwise, fill `DEFAULT_TEMPLATE` with `schema_context` and `dialect_guidance`.

#### `nl2sql/service.py` — Core generation logic:

**`generate_sql(adapter, request)`** async function:
1. Build `ChatRequest` via `_build_chat_request()` — constructs system prompt, converts conversation history to Message objects, adds `response_format` JSON schema option for OpenAI-family providers.
2. Call `adapter.chat(req)` to get LLM response.
3. Parse response via `_parse_llm_response()`.
4. Validate via `_run_validation()`.
5. Return `NL2SQLResponse`.

**`stream_generate_sql(adapter, request)`** async generator:
1. Consume `adapter.stream_chat()` events.
2. Collect `StreamDelta` tokens into `full_text` (does NOT forward deltas to the client — the final parsed result is sent as a single SSE event).
3. On `StreamFinal`, parse collected text and yield `NL2SQLStreamFinal` with validation.
4. On exceptions, yield `StreamError`.

**`_parse_llm_response(text)`** — Multi-strategy parser:
1. Try direct `json.loads(text)`.
2. Fall back to extracting JSON from markdown fences (` ```json ... ``` `).
3. Final fallback: treat entire output as a single SQL statement (wrap in the expected structure with title="Query").
4. Normalize via `_normalize_parsed()` — ensures all fields exist, clamps `recommended_index` to valid range, converts assumptions to strings.

**`_build_chat_request(request)`**:
- Builds system prompt via `build_system_prompt()`.
- Converts `NL2SQLHistoryMessage` items to `Message` objects for conversation context.
- For OpenAI/Azure/local_openai providers, adds the JSON schema to `provider_options.response_format`.
- Returns `ChatRequest`.

#### `nl2sql/sandbox.py` — SQL validation and transpilation:

Uses `sqlglot` for all SQL parsing.

**`validate_syntax(sql, dialect)`**:
- Parse with `sqlglot.parse(sql, read=dialect)`.
- Transpile to pretty-printed SQL for the same dialect.
- Return `SQLValidationResult` with any syntax errors.

**`validate_with_sandbox(sql, dialect, sandbox_ddl)`**:
1. Run syntax check first.
2. Transpile user-provided DDL to SQLite dialect.
3. Create in-memory `sqlite3.connect(":memory:")`.
4. Execute DDL statements (non-fatal if they fail).
5. Try `EXPLAIN QUERY PLAN <transpiled_query>` for quick semantic check.
6. Fall back to full execution if EXPLAIN fails.
7. Return `SQLValidationResult` with `sandbox_execution_success` and `sandbox_error`.

**`transpile_sql(sql, source_dialect, target_dialect)`**: Cross-dialect transpilation.

**`_transpile_ddl(ddl, source_dialect)`**: Transpile DDL to SQLite, with line-by-line fallback if batch transpilation fails.

**Dialect mapping** (`SQLDialect` → sqlglot dialect string):
```
postgresql → "postgres", tsql → "tsql", mysql → "mysql",
sqlite → "sqlite", bigquery → "bigquery", snowflake → "snowflake"
```

#### `nl2sql/executor.py` — SQL execution against the app database:

**`execute_sql(request, settings)`** async function:
1. Validate request via `_validate_execute_request()`.
2. Create async engine from app settings database URL (bounded `pool_size=1`).
3. Execute query with timeout.
4. Collect columns and rows (truncate at `max_rows`).
5. Return `SQLExecuteResponse` with `execution_time_ms`.
6. Clean up engine in `finally` block.

**`_validate_execute_request(request)`**:
- Parse SQL with sqlglot for the given dialect.
- Enforce: exactly ONE statement allowed.
- In read_only mode (always true): only allow SELECT, UNION, WITH (CTEs).
- Reject INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, TRUNCATE, etc.

#### `nl2sql/router.py` — FastAPI routes:

Mount at prefix `/api/datalab`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/datalab/generate` | Non-streaming NL2SQL generation |
| POST | `/api/datalab/generate/stream` | SSE streaming generation |
| POST | `/api/datalab/validate` | SQL syntax validation (+ optional sandbox) |
| POST | `/api/datalab/execute` | Execute SQL against app database |

**POST `/api/datalab/generate`**:
- Input: `NL2SQLRequest`
- Gets adapter via registry, calls `service.generate_sql()`.
- Persists `Run` to database (request JSON, response JSON, status, latency, token counts, tags="datalab").
- Returns `NL2SQLResponse` with `run_id`.

**POST `/api/datalab/generate/stream`**:
- Returns `StreamingResponse` with `text/event-stream` media type.
- Event generator collects events from `service.stream_generate_sql()`.
- Yields SSE: `event: datalab_final\ndata: {json}\n\n` or `event: error\ndata: {json}\n\n`.
- Persists run in `finally` block.
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

**POST `/api/datalab/validate`**:
- Input: `SQLValidateRequest`
- Calls `validate_with_sandbox()` if DDL provided, else `validate_syntax()`.
- Returns `SQLValidationResult`.

**POST `/api/datalab/execute`**:
- Input: `SQLExecuteRequest`
- Validates (single statement, read-only).
- Calls `executor.execute_sql()`.
- Returns `SQLExecuteResponse`.

### 1.4 Database Layer

**`models.py`** — SQLAlchemy ORM:

```python
class Run(Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    provider: Mapped[str]
    model: Mapped[str]
    request_json: Mapped[str]               # Full request serialized as JSON
    normalized_response_json: Mapped[str | None]
    raw_response_json: Mapped[str | None]
    status: Mapped[str]                     # "pending" | "success" | "error"
    error_message: Mapped[str | None]
    latency_ms: Mapped[float | None]
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]
    total_tokens: Mapped[int | None]
    tags: Mapped[str | None]                # e.g., "datalab"
```

**`database.py`** — Async engine + session factory:

```python
engine = create_async_engine(settings.resolved_database_url, **engine_kwargs)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

Engine kwargs vary by backend:
- SQLite: `connect_args={"timeout": 30}`
- Networked DBs: `pool_pre_ping=True, pool_size=5, max_overflow=10, pool_timeout=30`

### 1.5 Configuration

**`config.py`** — Pydantic-settings:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite+aiosqlite:///./datalab.db"
    auto_create_schema: bool = True

    # CORS
    cors_origins: str = '["http://localhost:5173"]'

    # Logging
    log_level: str = "INFO"

    # Provider keys (all optional — adapters auto-disable)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    mistral_api_key: str | None = None
    groq_api_key: str | None = None
    together_api_key: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    local_openai_base_url: str | None = None
    local_openai_api_key: str | None = None
```

### 1.6 App Entrypoint

**`main.py`**:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging
    # Create schema if auto_create_schema=True
    # Initialize adapter registry
    yield

app = FastAPI(title="DataLab", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(RequestLoggingMiddleware)  # Logs method, path, status, latency with request ID
app.include_router(health_router)
app.include_router(nl2sql_router)
```

Health endpoints: `GET /health` (liveness), `GET /api/providers` (list available providers), `GET /api/providers/{provider}/models` (list models for a provider).

---

## 2. Frontend Specification

### 2.1 Main Page — `DataLab.tsx`

This is the core page component that orchestrates the entire NL2SQL user flow. It is a single-page interface (not a multi-page app — just one main route plus a simple history/about page if desired).

**State management** — all state lives in the page component via `useState`/`useRef`:

| State group | Variables |
|-------------|-----------|
| Provider & Model | `provider`, `model`, `availableProviders`, `availableModels`, `modelsLoading` |
| Settings | `dialect` (SQLDialect), `systemPrompt`, `sandboxDDL`, `temperature` (default 0.3), `maxTokens` (default 2048), `mode` ("generate" \| "generate_and_execute") |
| Conversation | `turns` (completed turns array), `currentQuery`, `naturalLanguage` (raw input), `lastResult` (NL2SQLResponse), `executeResult` (SQLExecuteResponse), `selectedQueryIndex` |
| UI flags | `isStreaming`, `isGenerating`, `isExecuting`, `error`, `showSettings` |
| Refs | `abortRef` (AbortController for cancellation), `threadEndRef` (auto-scroll) |

**Derived values:**
- `isReasoning`: computed from model name matching `/^(o\d|gpt-5)/i` — disables temperature slider.
- `conversationHistory`: flattened from completed turns to build context for multi-turn API calls.
- `activeQuery`: currently selected query from multi-query variants.

**User flow:**

1. **Configure** — Select provider, model, dialect; paste database schema into system prompt; optionally provide sandbox DDL for validation.
2. **Choose mode** — "Generate Only" or "Generate & Execute".
3. **Ask** — Type natural language question in textarea at bottom, press Enter or click Send.
4. **Stream** — Frontend calls `POST /api/datalab/generate/stream` via direct `fetch()` with manual SSE parsing. Collects `event: datalab_final` with the full parsed response.
5. **Review variants** — If LLM returned multiple queries, tabs appear to switch between them. Recommended query is pre-selected.
6. **Execute** — If mode is "generate_and_execute" and SQL is valid, auto-execute occurs. Otherwise user clicks Execute manually.
7. **Results** — Table displays columns, rows, execution time, truncation notice.
8. **Refine** — Previous turns are stored and displayed above; user can ask follow-up questions with full conversation context.
9. **Reset** — "New Conversation" button clears all state.

**SSE parsing** — The page implements manual Server-Sent Events parsing (NOT the useStream hook, which is designed for a different chat endpoint). It:
- Creates `fetch()` with `AbortController`.
- Reads chunks from `response.body.getReader()`.
- Parses `event: datalab_final` and `event: error` lines.
- Extracts JSON from `data: {...}` lines.

**Sub-components rendered by the page:**

```
DataLab.tsx
├── Settings panel (inline, toggleable)
│   ├── Provider/Model selectors
│   ├── DialectSelector
│   ├── SchemaPromptEditor
│   ├── Temperature/MaxTokens sliders
│   ├── Mode toggle (generate / generate_and_execute)
│   └── Sandbox DDL textarea
├── Conversation thread
│   ├── Completed turns (user query + assistant response pairs)
│   │   ├── QueryVariantTabs (if multiple queries)
│   │   ├── SQLOutput
│   │   ├── AssumptionsList
│   │   ├── ValidationPanel
│   │   └── ResultsTable (if executed)
│   └── Current in-progress turn
│       ├── SQLOutput (streaming state)
│       ├── ValidationPanel
│       └── ResultsTable
└── Input area
    ├── Textarea (natural language input)
    └── Send / Stop button
```

### 2.2 UI Components

All components should use `React.memo` to prevent unnecessary re-renders.

**`DialectSelector`** — Dropdown for SQL dialect:
- Props: `value: SQLDialect`, `onChange: (dialect: SQLDialect) => void`
- Options: PostgreSQL, T-SQL (SQL Server), MySQL, SQLite, BigQuery, Snowflake

**`SchemaPromptEditor`** — Expandable textarea for database schema:
- Props: `value: string`, `onChange: (value: string) => void`
- Features: collapsible/expandable, monospace font, 12 rows, placeholder guides user to paste schema and business rules

**`SQLOutput`** — Display generated SQL with explanation:
- Props: `sql: string`, `explanation: string`, `dialect: string`, `isStreaming?: boolean`
- Features: SQL in code block, dialect badge, copy button (hidden during streaming), explanation below, streaming state shows "Generating SQL..." with cursor blink animation

**`ValidationPanel`** — Display validation results:
- Props: `validation: SQLValidationResult | null`
- Features: Valid/Invalid status with color coding, sandbox execution result badge, syntax error list, sandbox error message

**`ResultsTable`** — Display query execution results:
- Props: `result: SQLExecuteResponse | null`
- Features: Table with column headers and rows, row count and execution time, truncated indicator, NULL values in muted text, horizontal scroll, empty state "No rows returned"

**`ConnectionConfig`** — Database connection string input:
- Props: `connectionString: string`, `onChange: (value: string) => void`
- Features: password-masked input, helper text showing supported connection types

**`QueryVariantTabs`** — Tab bar for multiple query options:
- Renders one tab per query variant, highlights recommended index, click to select

**`AssumptionsList`** — Bulleted list of assumptions the LLM made about the schema/data.

**`RawLLMOutput`** — Toggleable panel showing the raw model completion text before parsing.

### 2.3 API Client

**`api/client.ts`** — Typed fetch wrapper:

```typescript
const request = async <T>(path: string, options?: RequestInit): Promise<T> => {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? res.statusText);
  }
  return res.json();
};

export const api = {
  // Health
  health: () => request<{ status: string }>("/health"),
  listProviders: () => request<string[]>("/api/providers"),
  listModels: (provider: string) => request<string[]>(`/api/providers/${provider}/models`),

  // NL2SQL
  generateSQL: (req: NL2SQLRequest) => request<NL2SQLResponse>("/api/datalab/generate", { method: "POST", body: JSON.stringify(req) }),
  validateSQL: (req: SQLValidateRequest) => request<SQLValidationResult>("/api/datalab/validate", { method: "POST", body: JSON.stringify(req) }),
  executeSQL: (req: SQLExecuteRequest) => request<SQLExecuteResponse>("/api/datalab/execute", { method: "POST", body: JSON.stringify(req) }),
};
```

Note: The streaming endpoint (`/api/datalab/generate/stream`) is called directly via `fetch()` in the page component, not through the API client, because it uses SSE parsing.

### 2.4 TypeScript Types

**`api/types.ts`** — Mirror of backend schemas:

```typescript
export type SQLDialect = "postgresql" | "tsql" | "mysql" | "sqlite" | "bigquery" | "snowflake";

export interface NL2SQLRequest {
  provider: string;
  model: string;
  natural_language: string;
  dialect: SQLDialect;
  system_prompt?: string;
  temperature: number | null;
  max_tokens: number;
  sandbox_ddl?: string;
  conversation_history?: NL2SQLHistoryMessage[];
  provider_options: Record<string, unknown>;
}

export interface NL2SQLHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SQLQuery {
  title: string;
  sql: string;
  explanation: string;
}

export interface NL2SQLResponse {
  generated_sql: string;
  explanation: string;
  queries: SQLQuery[];
  recommended_index: number;
  assumptions: string[];
  dialect: SQLDialect;
  validation: SQLValidationResult;
  usage: Record<string, number | null>;
  run_id: string | null;
  latency_ms: number | null;
  raw_llm_output?: string;
}

export interface SQLValidationResult {
  is_valid: boolean;
  syntax_errors: string[];
  transpiled_sql: string | null;
  sandbox_execution_success: boolean | null;
  sandbox_error: string | null;
}

export interface SQLValidateRequest {
  sql: string;
  dialect: SQLDialect;
  sandbox_ddl?: string;
}

export interface SQLExecuteRequest {
  sql: string;
  dialect: SQLDialect;
  timeout_seconds?: number;
  max_rows?: number;
  read_only?: boolean;
}

export interface SQLExecuteResponse {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
}

export interface DataLabStreamFinalEvent {
  type?: string;
  generated_sql: string;
  explanation: string;
  queries: SQLQuery[];
  recommended_index: number;
  assumptions: string[];
  dialect: SQLDialect;
  validation: SQLValidationResult;
  usage: Record<string, number | null>;
  run_id: string | null;
  latency_ms: number | null;
  raw_llm_output?: string;
}
```

### 2.5 CSS Architecture

Use CSS custom properties for theming. No Tailwind — all styles are hand-written.

**Three themes:** dark (default), light, blue. Theme is stored in `localStorage` and applied via `data-theme` attribute on `<html>`.

**CSS variable tokens:**

```css
:root, [data-theme="dark"] {
  color-scheme: dark;
  --bg: #0f1117;
  --bg-card: #1a1d27;
  --bg-input: #232733;
  --border: #2d3140;
  --text: #e4e4e7;
  --text-muted: #8b8d98;
  --accent: #6366f1;
  --accent-hover: #818cf8;
  --success: #22c55e;
  --error: #ef4444;
  --warning: #f59e0b;
  --radius: 8px;
  --font-mono: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
  --th-bg: rgba(255,255,255,0.04);
  --tr-hover: rgba(255,255,255,0.02);
  --code-bg: rgba(255,255,255,0.06);
  --pre-bg: #11141d;
  --badge-success-bg: rgba(34,197,94,0.15);
  --badge-error-bg: rgba(239,68,68,0.15);
  --badge-pending-bg: rgba(245,158,11,0.15);
  --error-box-bg: rgba(239,68,68,0.1);
}
```

Define equivalent tokens for `[data-theme="light"]` and `[data-theme="blue"]`.

**Key utility classes to define:** `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-danger`, `.btn-sm`, `.card`, `.form-grid`, `.form-group`, `.output-panel`, `.data-table`, `.badge`, `.badge-success`, `.badge-error`, `.meta-grid`, `.meta-item`, `.error-box`, `.loading`, `.cursor-blink` (keyframe animation for streaming indicator).

**Font:** System sans-serif stack for UI, monospace variable for code/SQL.

### 2.6 Vite Configuration

```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
```

### 2.7 HTML Template

Minimal `index.html` with:
- `<div id="root"></div>` for React
- Inline script to restore theme from `localStorage` before first render (prevents flash of wrong theme)
- Module entry: `<script type="module" src="/src/main.tsx"></script>`

---

## 3. Engineering Standards

### Router Discipline
- Routers stay thin: validate input, call services/adapters, shape the HTTP response.
- No direct provider SDK calls from routers.
- No raw SQL or DB session orchestration in route handlers.
- Map errors to consistent HTTP status codes.

### Async Safety
- All I/O uses `async/await`. Use `AsyncSession` for DB operations.
- No blocking calls (`time.sleep`, sync HTTP clients).
- Set explicit timeouts on all provider/network operations.
- Use bounded concurrency — no unbounded fan-out.
- Cancellation-safe cleanup for streaming.

### Database Patterns
- Paginate list endpoints with safe default limits.
- No N+1 query patterns.
- Transactions scoped and explicit.
- DB transaction control in service/repository layers, not routers.

### Error Handling
- No bare `except` blocks.
- Structured logs with request/trace identifiers.
- Never log secrets, API keys, tokens.
- No verbose exception details in client responses.

### Security
- Never hardcode credentials. Environment-driven config only.
- Validate all user-provided inputs server-side.
- Redact secrets before logging.
- SQL executor enforces read-only mode server-side (never trust the client).

---

## 4. Testing Requirements

### Fixtures (`conftest.py`)

```python
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

Use `asyncio_mode = "auto"` in pytest config — no need for `@pytest.mark.asyncio`.

### Route Tests (`test_nl2sql_api.py`)

**Generate endpoint:**
- Happy path with DB persistence (mock adapter, verify run_id returned)
- Provider not available → 400
- Missing natural_language → 422
- With conversation_history (multi-turn)

**Validate endpoint:**
- Valid SQL passes syntax check
- Invalid SQL catches errors
- With sandbox DDL — full validation
- Sandbox column mismatch — execution failure

**Execute endpoint:**
- Success with mocked executor
- Invalid SQL → 400
- Missing sql → 422
- Rejects write operations (INSERT/UPDATE/DELETE) in read-only mode → 400
- Rejects multi-statement payloads → 400
- Allows trailing comments after semicolon

### Service Tests (`test_nl2sql_service.py`)

**Parse LLM response:**
- Single query JSON
- Multiple queries with recommended_index and assumptions
- JSON in markdown fences
- Fallback to raw SQL when JSON parse fails
- Invalid JSON triggers fallback
- Missing fields get defaults
- Out-of-bounds recommended_index gets clamped
- Empty queries array gets default

**Generate SQL:**
- Happy path with validation
- Multiple queries with recommended selection
- With sandbox DDL — sandbox validation
- Handles invalid generated SQL (captures syntax errors)
- Adapter called with correct messages
- OpenAI provider gets response_format
- Anthropic provider does NOT get response_format
- Adapter called with conversation history
- Fallback when LLM returns raw SQL

**Stream generate SQL:**
- Collects deltas and yields single final event with raw_llm_output

---

## 5. Docker & Dev Setup

### docker-compose.yml

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    env_file:
      - backend/.env
    command: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - frontend_node_modules:/app/node_modules
    depends_on:
      - backend
    command: npm run dev -- --host

volumes:
  frontend_node_modules:
```

### Environment Variables (`.env.example`)

```env
# Database (SQLite default, or PostgreSQL/Azure SQL)
DATABASE_URL=sqlite+aiosqlite:///./datalab.db
AUTO_CREATE_SCHEMA=true

# CORS
CORS_ORIGINS=["http://localhost:5173"]

# Logging
LOG_LEVEL=INFO

# Provider API keys (all optional — adapters auto-disable if missing)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
MISTRAL_API_KEY=
GROQ_API_KEY=
TOGETHER_API_KEY=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
LOCAL_OPENAI_BASE_URL=http://localhost:11434/v1
LOCAL_OPENAI_API_KEY=
```

### Dev Commands

**Backend:**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run pytest -v
uv run ruff check .
uv run ruff format .
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
npm run format
```

### Backend Dependencies (`pyproject.toml`)

```
fastapi >= 0.115
uvicorn[standard] >= 0.34
pydantic >= 2.10
pydantic-settings >= 2.7
sqlalchemy[asyncio] >= 2.0
aiosqlite >= 0.20
alembic >= 1.14
openai >= 1.60
anthropic >= 0.43
httpx >= 0.28
sse-starlette >= 2.2
sqlglot >= 26
```

Dev: `pytest`, `pytest-asyncio`, `ruff`

### Frontend Dependencies (`package.json`)

```
react: ^19.0.0
react-dom: ^19.0.0
react-router-dom: ^7.1.0
```

Dev: `typescript`, `vite`, `@vitejs/plugin-react`, `eslint`, `prettier`

---

## 6. Key Design Decisions

These decisions are intentional and should be preserved:

1. **Multi-query variants** — The LLM is instructed to return multiple SQL approaches when the question is ambiguous. The UI shows tabs to switch between them, with the recommended one pre-selected.

2. **Sandbox validation via SQLite transpilation** — Generated SQL is transpiled from the target dialect to SQLite and executed against an in-memory database seeded with the user's DDL. This catches semantic errors (wrong column names, missing tables) without needing a real database connection.

3. **Structured output with fallback** — OpenAI-family providers use `response_format` with a JSON schema for guaranteed structure. Other providers rely on prompt instructions with a multi-strategy parser (direct JSON → markdown-fenced JSON → raw SQL fallback).

4. **Streaming collects, then emits** — Unlike chat streaming where tokens are forwarded incrementally, NL2SQL streaming collects all tokens first, then parses and emits a single `datalab_final` event. This is because the response needs to be parsed as JSON before it's useful.

5. **Conversation history for multi-turn refinement** — Users can ask follow-up questions. Previous turns (user query + assistant SQL response) are sent as conversation history, allowing the LLM to refine queries based on prior context.

6. **Read-only execution enforced server-side** — The executor validates that only SELECT/WITH/UNION statements are allowed, regardless of what the client sends. This is a security boundary.

7. **Provider auto-discovery** — Adapters self-report availability based on environment variables. No configuration file needed — just set API keys and restart.

8. **CSS variables over utility classes** — Three themes defined entirely through CSS custom properties. Theme preference persists in localStorage and is restored before first render to prevent flash.
