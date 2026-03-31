# Schema Context Builder for NL-to-SQL

## Context

The QueryLab NL-to-SQL feature currently requires users to manually paste their entire seed SQL script (~400+ lines of T-SQL DDL with DROP/IF EXISTS/GO/IDENTITY/indexes) into a textarea. This is token-wasteful, includes irrelevant noise, and there's a bug where the pasted text replaces the entire prompt template (including JSON response format instructions, SQL rules, and dialect guidance) instead of being inserted into the `{schema_context}` placeholder.

**Goal:** Build an auto-populate pipeline that introspects a live database, formats the schema into a token-efficient representation, and slots it into the prompt template properly — while keeping the manual paste option for power users.

---

## Phase 1: Schema Context Models & Formatters

Create `backend/app/nl2sql/schema_context/` module.

### 1a. Models (`backend/app/nl2sql/schema_context/models.py`)

New Pydantic models:

- `ForeignKeyInfo`: `column`, `references_schema`, `references_table`, `references_column`
- `ColumnDetail`: `name`, `data_type`, `nullable`, `default`, `is_primary_key`, `is_unique`, `description` (optional, for future annotations)
- `TableDetail`: `name`, `schema_name`, `columns: list[ColumnDetail]`, `foreign_keys: list[ForeignKeyInfo]`, `description` (optional)
- `SchemaCatalog`: `backend: DatabaseBackend`, `tables: list[TableDetail]`
- `SchemaContextFormat`: StrEnum — `compact_ddl`, `structured_catalog`, `concise_notation`
- `SchemaContextResponse`: `format`, `schema_text`, `table_count`, `estimated_tokens`

### 1b. Formatters (`backend/app/nl2sql/schema_context/formatters.py`)

Three formatter functions, each taking `SchemaCatalog` → `str`:

**`compact_ddl`** (default) — Clean CREATE TABLE statements. No DROP, IF EXISTS, IDENTITY, GO, indexes. Include PKs, FKs, NOT NULL, UNIQUE. Append a `## Relationships` summary.

Example output:
```sql
CREATE TABLE hr.employees (
  id INT PRIMARY KEY,
  first_name NVARCHAR(50) NOT NULL,
  email NVARCHAR(150) NOT NULL UNIQUE,
  department_id INT NOT NULL REFERENCES hr.departments(id),
  manager_id INT NULL REFERENCES hr.employees(id),
  hire_date DATE NOT NULL
);

-- Relationships:
-- hr.employees.department_id -> hr.departments.id
-- hr.employees.manager_id -> hr.employees.id (self-referencing)
```

**Why this is the best default:** LLMs are heavily trained on DDL. It's the format used in NL-to-SQL benchmarks (Spider, BIRD, WikiSQL). Unambiguous grammar for types, nullability, FKs, and constraints. For ~20 tables this uses ~2,000-3,000 tokens — modest for modern 128K+ context models.

**`structured_catalog`** — Markdown tables with columns: Column, Type, PK, FK, Nullable. Append relationships summary.

Example output:
```
## hr.employees
| Column | Type | PK | FK | Nullable |
|--------|------|----|----|----------|
| id | INT | PK | | NO |
| first_name | NVARCHAR(50) | | | NO |
| department_id | INT | | → hr.departments.id | NO |
| manager_id | INT | | → hr.employees.id | YES |
```

**When to use:** ~30% more token-efficient than DDL. Easy to extend with description columns. Good when you want to attach semantic annotations (column descriptions, business glossary) alongside structural metadata.

**`concise_notation`** — One-line-per-table. Append relationships summary.

Example output:
```
hr.departments(id PK, name NVARCHAR(100), budget DECIMAL(15,2), manager_employee_id FK→hr.employees.id)
hr.employees(id PK, first_name NVARCHAR(50), department_id FK→hr.departments.id, manager_id FK→hr.employees.id)
```

**When to use:** ~50-60% more token-efficient than DDL. Best for very large schemas (100+ tables) where token budget is the primary constraint. Slight accuracy penalty on complex multi-join queries since LLMs haven't seen this custom format in training data.

A `format_schema_context(catalog, format)` dispatcher function selects the right formatter.

### 1c. Tests (`backend/tests/test_schema_context_formatters.py`)

Build a `SchemaCatalog` fixture (3-4 tables with FKs). Verify each formatter output contains expected elements and excludes noise.

---

## Phase 2: DB Introspection with FK/PK Support

### 2a. Add FK + PK introspection SQL to `backend/app/devdb/dialects.py`

New functions:

**`foreign_keys_sql(backend, table_name, schema_name)`** — returns dialect-specific FK query:

- SQLite: `PRAGMA foreign_key_list("{table}")`
- PostgreSQL:
  ```sql
  SELECT kcu.column_name,
         ccu.table_schema AS foreign_table_schema,
         ccu.table_name AS foreign_table_name,
         ccu.column_name AS foreign_column_name
  FROM information_schema.table_constraints AS tc
  JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
  JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
  WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_name = :table_name AND tc.table_schema = :schema_name
  ```
- MSSQL:
  ```sql
  SELECT col.name AS column_name,
         ref_schema.name AS foreign_table_schema,
         ref_tab.name AS foreign_table_name,
         ref_col.name AS foreign_column_name
  FROM sys.foreign_key_columns AS fkc
  JOIN sys.columns AS col ON fkc.parent_object_id = col.object_id AND fkc.parent_column_id = col.column_id
  JOIN sys.tables AS ref_tab ON fkc.referenced_object_id = ref_tab.object_id
  JOIN sys.schemas AS ref_schema ON ref_tab.schema_id = ref_schema.schema_id
  JOIN sys.columns AS ref_col ON fkc.referenced_object_id = ref_col.object_id AND fkc.referenced_column_id = ref_col.column_id
  JOIN sys.tables AS parent_tab ON fkc.parent_object_id = parent_tab.object_id
  JOIN sys.schemas AS parent_schema ON parent_tab.schema_id = parent_schema.schema_id
  WHERE parent_tab.name = :table_name AND parent_schema.name = :schema_name
  ```

**`primary_keys_sql(backend, table_name, schema_name)`** — fixes the bug where `is_primary_key` is always `False` for non-SQLite backends:

- PostgreSQL: `information_schema.table_constraints` + `key_column_usage` WHERE `constraint_type = 'PRIMARY KEY'`
- MSSQL: `sys.indexes` + `sys.index_columns` WHERE `is_primary_key = 1`

### 2b. Introspector (`backend/app/nl2sql/schema_context/introspector.py`)

`SchemaIntrospector` class:

1. Uses `DevDBService.list_tables()` for the table list
2. For each table: `DevDBService.describe_table()` for columns + new PK/FK queries
3. Bounded concurrency via `asyncio.Semaphore(10)` for parallel table introspection
4. Builds and returns a `SchemaCatalog`
5. Accepts optional `table_filter: list[str]` to limit which tables are introspected

### 2c. Tests (`backend/tests/test_schema_context_introspector.py`)

SQLite in-memory DB with tables that have PKs and FKs. Verify `ForeignKeyInfo` and `is_primary_key` are correctly populated.

---

## Phase 3: Service & API Endpoint

### 3a. Service (`backend/app/nl2sql/schema_context/service.py`)

```python
class SchemaContextService:
    async def generate(
        self,
        *,
        connection_string: str | None = None,
        format: SchemaContextFormat = SchemaContextFormat.compact_ddl,
        table_filter: list[str] | None = None,
    ) -> SchemaContextResponse:
```

Composes `SchemaIntrospector` + `format_schema_context`. Returns formatted text + token estimate (`len(text) // 4`).

### 3b. API Endpoint — add to `backend/app/routers/dev_db.py`

```
GET /api/dev/db/schema-context?format=compact_ddl&tables=hr.employees,hr.departments
```

Gated behind `DEV_DB_TOOLS_ENABLED` (reuse existing `_ensure_dev_db_enabled` guard). Returns `SchemaContextResponse`.

### 3c. Tests (`backend/tests/test_schema_context_api.py`)

Integration test: seed SQLite DB → hit endpoint → verify response shape and format.

---

## Phase 4: Fix Prompt Builder Integration

### 4a. Add `schema_context` field to `NL2SQLRequest` (`backend/app/nl2sql/schemas.py`)

```python
schema_context: str | None = Field(
    None,
    description="Token-efficient schema context (auto-generated or manual). "
                "Inserted into the default prompt template's {schema_context} placeholder.",
)
```

Existing `system_prompt` field stays — it remains the full-override for power users.

### 4b. Fix `_build_chat_request` in `backend/app/nl2sql/service.py`

**The bug:** Currently passes `request.system_prompt` as `custom_prompt`, which replaces the entire template (including JSON format instructions, SQL rules, dialect guidance).

Change from:
```python
system_prompt = build_system_prompt(dialect=request.dialect, custom_prompt=request.system_prompt)
```

To:
```python
system_prompt = build_system_prompt(
    dialect=request.dialect,
    schema_context=request.schema_context,
    custom_prompt=request.system_prompt,
)
```

Now:
- `schema_context` alone → slots into the template, **preserving** JSON format instructions + SQL rules + dialect guidance
- `system_prompt` alone → full override (backward-compatible)
- Both provided → `system_prompt` wins (existing `build_system_prompt` behavior)
- Neither → "(No schema provided)" fallback

### 4c. Update NL2SQL tests

Verify `schema_context` flows into the template correctly, and that `system_prompt` still overrides.

---

## Phase 5: Frontend Changes

### 5a. Update types (`frontend/src/api/types.ts`)

- Add `SchemaContextFormat` type, `SchemaContextResponse` interface
- Add `schema_context?: string` to `NL2SQLRequest`

### 5b. Update API client (`frontend/src/api/client.ts`)

Add `getSchemaContext(format, tables?)` → calls `GET /api/dev/db/schema-context`.

### 5c. Update `SchemaPromptEditor.tsx`

Transform into a component with two modes:

- **Auto-populate mode**: Format selector dropdown (DDL / Catalog / Concise) + "Load from Database" button + token estimate badge + read-only preview. An "Edit" button copies auto-generated text into manual mode for customization.
- **Manual mode**: Existing textarea behavior (unchanged)

Emits `schema_context` (for auto-populated content) separately from `system_prompt` (for manual override).

### 5d. Update `QueryLab.tsx`

- Add `schemaContext` state alongside `systemPrompt`
- Pass `schema_context` as its own field in the request body
- Only pass `system_prompt` when the user has manually typed in override mode

---

## Verification Checklist

1. **Unit tests**: `uv run pytest -v tests/test_schema_context_formatters.py tests/test_schema_context_introspector.py`
2. **API test**: `uv run pytest -v tests/test_schema_context_api.py`
3. **Manual API test**: Start backend with `DEV_DB_TOOLS_ENABLED=true`, hit `GET /api/dev/db/schema-context`, verify compact DDL output
4. **End-to-end**: Open QueryLab → click "Load from Database" → verify schema populates → submit NL query → verify system message contains template with schema inserted (check via `raw_llm_output`)
5. **Regression**: `uv run pytest -v` — ensure all existing NL2SQL tests pass with the `_build_chat_request` fix

---

## Key Files Summary

| File | Change |
|------|--------|
| `backend/app/nl2sql/schema_context/__init__.py` | New — public exports |
| `backend/app/nl2sql/schema_context/models.py` | New — Pydantic models |
| `backend/app/nl2sql/schema_context/formatters.py` | New — 3 formatters + dispatcher |
| `backend/app/nl2sql/schema_context/introspector.py` | New — DB introspection with FK/PK |
| `backend/app/nl2sql/schema_context/service.py` | New — orchestration service |
| `backend/app/devdb/dialects.py` | Modify — add FK/PK SQL helpers |
| `backend/app/nl2sql/schemas.py` | Modify — add `schema_context` field to `NL2SQLRequest` |
| `backend/app/nl2sql/service.py` | Modify — fix `_build_chat_request` to pass `schema_context` |
| `backend/app/routers/dev_db.py` | Modify — add `/schema-context` endpoint |
| `frontend/src/api/types.ts` | Modify — add types |
| `frontend/src/api/client.ts` | Modify — add API call |
| `frontend/src/components/querylab/SchemaPromptEditor.tsx` | Modify — add auto-populate mode |
| `frontend/src/pages/QueryLab.tsx` | Modify — wire up `schemaContext` state |
| `backend/tests/test_schema_context_formatters.py` | New — formatter tests |
| `backend/tests/test_schema_context_introspector.py` | New — introspector tests |
| `backend/tests/test_schema_context_api.py` | New — API integration tests |

---

## Future Considerations (Not In Scope)

- **Layered/filtered context**: The `table_filter` parameter enables a future two-pass approach where the first LLM call selects relevant tables, then a second call generates SQL with only those tables' schema
- **Semantic annotations**: The `description` fields on `TableDetail` and `ColumnDetail` provide hooks for a future business glossary feature (could be stored in JSON, a DB table, or fetched from SQL Server extended properties)
- **Caching**: `SchemaContextService` could cache `SchemaCatalog` per connection string with a TTL to avoid repeated introspection
