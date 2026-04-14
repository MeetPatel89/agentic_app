# Schema Context Construction for NL-to-SQL

## Overview

QueryLab converts natural-language questions into production SQL by sending a system prompt to an LLM. The quality of that output is bounded by what we tell the model about the database: its structure, its semantics, its canonical query patterns, and the reality of what values live in it.

This document is the authoritative reference for how we build that context. It covers everything from low-level DDL introspection (already planned) to the semantic annotation layer, few-shot example retrieval, self-repair feedback loop, and token-budget management needed to get correct SQL for moderately-to-severely complex business questions.

**Target dialect:** T-SQL (Azure SQL). Other dialects (PostgreSQL, SQLite, MySQL, BigQuery, Snowflake) are supported by the same pipeline but are secondary.

**App persistence:** Azure SQL (`mssql+aioodbc`) is the production default. SQLite remains supported for local development and automated tests only.

---

## Why Richer Context Matters

A compact DDL dump alone reliably handles:

- Single-table `SELECT`/`WHERE`/`ORDER BY`
- Simple two-table joins with clear FK paths
- Basic aggregations (`COUNT`, `SUM`, `AVG` on well-named columns)

It **does not reliably** handle:

- Multi-hop joins across 3+ tables where the LLM must infer the right path
- Business terms that map to composite SQL (e.g. "active customer", "net revenue", "churn rate")
- Enum-like filters (`status = 'A'` vs `status = 'Active'`) without seeing sample values
- Disambiguation between similarly-named columns (`amount` in `orders` vs `payments`)
- Non-obvious domain rules (soft-deletes, tenant isolation, historical vs current rows)
- Correct use of dialect idioms (`TOP` vs `LIMIT`, window functions, `QUALIFY`)

The gap is *semantic*, not syntactic. Closing it requires layering structured metadata, curated examples, canonical join paths, and execution feedback onto the raw DDL.

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                        NL Question                              │
└───────────────────────────────┬─────────────────────────────────┘
                                ▼
        ┌───────────────────────────────────────────────┐
        │             Context Assembler                 │
        │  (orchestrates the pillars below per request) │
        └───┬──────────┬──────────┬──────────┬──────┬───┘
            ▼          ▼          ▼          ▼      ▼
    ┌──────────┐ ┌──────────┐ ┌───────┐ ┌───────┐ ┌────────┐
    │ Schema   │ │ Semantic │ │ Join  │ │ Few-  │ │ Value  │
    │ Catalog  │ │ Annot'ns │ │ Hints │ │ Shot  │ │ Samples│
    │ (live    │ │ (app DB) │ │ (app  │ │ (app  │ │ (app   │
    │  introsp)│ │          │ │  DB)  │ │  DB)  │ │  DB)   │
    └──────────┘ └──────────┘ └───────┘ └───────┘ └────────┘
            │          │          │          │      │
            └──────────┴──────────┴──────────┴──────┘
                                ▼
              ┌──────────────────────────────────┐
              │   Enhanced Prompt (single str)   │
              └──────────────────────────────────┘
                                ▼
                        ┌───────────────┐
                        │   LLM call    │
                        └───────┬───────┘
                                ▼
              ┌──────────────────────────────────┐
              │  Static validation (sqlglot)     │
              │  + optional dry-run (read-only,  │
              │    TOP 0, timeout)               │
              └───────┬──────────────────┬───────┘
                      │ pass             │ fail
                      ▼                  ▼
                  ┌──────┐        ┌──────────────┐
                  │Return│        │Feed error to │
                  └──────┘        │LLM (1 retry) │
                                  └──────────────┘
```

---

## Pillar 1 — Schema Catalog (Live Introspection)

**Goal:** Token-efficient representation of live tables, columns, PKs, and FKs.

This pillar replaces the current "paste your DDL" workflow, which is token-wasteful (ships DROP/IF EXISTS/IDENTITY/GO/indexes) and bug-prone (pasted text replaces the entire prompt template).

### Module layout

`backend/app/nl2sql/schema_context/`
- `models.py` — Pydantic models: `ForeignKeyInfo`, `ColumnDetail`, `TableDetail`, `SchemaCatalog`, `SchemaContextFormat` (StrEnum: `compact_ddl` | `structured_catalog` | `concise_notation`), `SchemaContextResponse`.
- `formatters.py` — Three formatters + a `format_schema_context(catalog, format)` dispatcher.
- `introspector.py` — `SchemaIntrospector` class. Uses `DevDBService.list_tables()` + `describe_table()`, adds FK/PK queries, fans out with `asyncio.Semaphore(10)`, optional `table_filter: list[str]`.
- `service.py` — `SchemaContextService.generate(...)` composes introspector + formatter.

### Formatters

**`compact_ddl` (default)** — Clean `CREATE TABLE` statements. No `DROP`, `IF EXISTS`, `IDENTITY`, `GO`, or indexes. PKs, FKs, `NOT NULL`, `UNIQUE` preserved. A `-- Relationships:` block follows. ~2,000–3,000 tokens for ~20 tables. Best default because LLMs are heavily trained on DDL (Spider, BIRD, WikiSQL benchmarks use it).

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
-- hr.employees.manager_id    -> hr.employees.id (self-referencing)
```

**`structured_catalog`** — Markdown tables (Column | Type | PK | FK | Nullable). ~30% more token-efficient than DDL. Good when you want to extend with description columns alongside structure.

**`concise_notation`** — One-line-per-table notation. ~50–60% token savings. Best for very large schemas (100+ tables). Slight accuracy penalty on complex joins because LLMs haven't seen this format in training.

### FK/PK Introspection

`backend/app/devdb/dialects.py` gains:

- `foreign_keys_sql(backend, table_name, schema_name)` — T-SQL uses `sys.foreign_key_columns` joined to `sys.tables`/`sys.columns`/`sys.schemas`. PG uses `information_schema.table_constraints` + `key_column_usage` + `constraint_column_usage`. SQLite uses `PRAGMA foreign_key_list("{table}")`.
- `primary_keys_sql(backend, table_name, schema_name)` — fixes the known bug where `ColumnDetail.is_primary_key` is always `False` for non-SQLite backends. T-SQL: `sys.indexes` + `sys.index_columns` where `is_primary_key = 1`. PG: `information_schema.table_constraints` where `constraint_type = 'PRIMARY KEY'`.

### API

`GET /api/dev/db/schema-context?format=compact_ddl&tables=hr.employees,hr.departments&connection_id=...`

Gated behind the existing `_ensure_dev_db_enabled` guard. Returns `SchemaContextResponse { format, schema_text, table_count, estimated_tokens }`. Token estimate is `len(text) // 4` — good enough for budget math.

---

## Pillar 2 — Semantic Annotations

**Goal:** Attach human-authored meaning to tables and columns.

The LLM cannot guess that `cust_stat_cd = 'A'` means "Active customer" or that `sales.orders.is_deleted = 1` is a soft-delete flag. Annotations close that gap.

### Data model (app DB, Azure SQL / T-SQL-first)

New ORM models in `backend/app/metadata/models.py`. All use `String`/`Text`/`DateTime(timezone=True)` per the project pattern. IDs are UUID strings (36-char) to match `Run`/`Conversation`. Alembic migration in `backend/migrations/` with `nvarchar`-compatible types.

```python
class SchemaConnection(Base):
    __tablename__ = "schema_connections"
    id: str                        # UUID
    name: str                      # "contoso_prod"
    connection_ref: str            # env var name or vault key — NOT the raw string
    dialect: str                   # "tsql" | "postgresql" | ...
    default_schema: str | None
    created_at / updated_at

class SchemaAnnotation(Base):
    __tablename__ = "schema_annotations"
    id: str
    connection_id: str             # FK
    schema_name: str               # "hr"
    table_name: str                # "employees"
    column_name: str | None        # None = table-level annotation
    description: str               # Text / NVARCHAR(MAX)
    business_name: str | None      # "Employee Record" vs "employees"
    synonyms_json: str | None      # ["staff", "personnel"]
    tags_json: str | None          # ["pii", "hr_sensitive"]
    deprecated_at: datetime | None
    updated_at: datetime
    # Unique(connection_id, schema_name, table_name, column_name)

class BusinessTerm(Base):
    __tablename__ = "business_terms"
    id: str
    connection_id: str
    term: str                      # "active_customer"
    definition: str                # "Customer with at least one order in the last 90 days"
    sql_expression: str | None     # "EXISTS (SELECT 1 FROM sales.orders o WHERE ...)"
    aliases_json: str | None       # ["engaged customer", "recent buyer"]
    related_tables_json: str | None
    updated_at: datetime

class JoinHint(Base):
    __tablename__ = "join_hints"
    id: str
    connection_id: str
    left_schema: str; left_table: str
    right_schema: str; right_table: str
    join_type: str                 # "INNER" | "LEFT" | ...
    join_predicate: str            # "l.department_id = r.id"
    cardinality: str               # "1:1" | "1:N" | "N:M"
    priority: int                  # canonical=0, alternative=1+
    description: str | None        # "Standard path from order to customer"
    updated_at: datetime

class QueryExample(Base):
    __tablename__ = "query_examples"
    id: str
    connection_id: str
    natural_language: str
    sql: str
    dialect: str
    tables_used_json: str          # ["sales.orders", "sales.customers"]
    tags_json: str | None          # ["aggregation", "join_3_tables", "window_function"]
    approved: bool
    source: str                    # "curated" | "mined_from_runs"
    source_run_id: str | None      # FK to runs.id when mined
    created_at / updated_at

class ColumnValueSample(Base):
    __tablename__ = "column_value_samples"
    id: str
    connection_id: str
    schema_name: str; table_name: str; column_name: str
    sample_values_json: str        # [{"value": "Active", "count": 1203}, ...]
    distinct_count: int
    total_count: int
    is_low_cardinality: bool       # True if distinct_count <= threshold
    refreshed_at: datetime
    # Unique(connection_id, schema_name, table_name, column_name)
```

### Seeding the Contoso schema

Script: `backend/scripts/seed_contoso_metadata.py`. Populates:

- ~40–50 annotations covering all tables in `hr`, `sales`, `inventory`, `finance`, `support` plus their key columns (PII flags on `hr.employees.email`, soft-delete flags, currency units on money columns, etc.).
- ~15–20 business terms: `active_customer`, `total_revenue`, `net_revenue`, `gross_margin`, `on_time_shipment_rate`, `churn_rate_30d`, `repeat_customer`, `open_ticket`, `inventory_at_risk`, etc. Each carries both a prose definition and a canonical T-SQL expression where meaningful.
- ~20–30 canonical join hints covering: orders⋈customers, orders⋈order_items⋈products, employees⋈departments, employees⋈employees (self-join for manager), tickets⋈customers, invoices⋈orders⋈customers.
- 25–30 curated NL→T-SQL examples (see Pillar 4).

Idempotent: script upserts by `(connection_id, natural_key)`.

### Import from target DB extended properties

Optional script `backend/scripts/import_extended_properties.py`. Reads `sys.extended_properties` from the target Azure SQL DB and merges `MS_Description` values into `schema_annotations.description`. One-way only — app DB is always the source of truth.

### API

New router `backend/app/routers/schema_metadata.py`, gated by a new `METADATA_ADMIN_ENABLED` config flag (separate from `DEV_DB_TOOLS_ENABLED` because this endpoint performs writes to the app DB). Standard CRUD:

- `/api/metadata/connections` — list/create/delete
- `/api/metadata/annotations` — CRUD + bulk upsert
- `/api/metadata/business-terms` — CRUD
- `/api/metadata/join-hints` — CRUD
- `/api/metadata/query-examples` — CRUD + `POST /.../test` (runs an example through NL2SQL and returns diff vs stored SQL)
- `POST /api/metadata/import/extended-properties?connection_id=...` — triggers the importer
- `POST /api/metadata/column-value-samples/refresh?connection_id=...&max_cardinality=50` — re-samples low-cardinality columns

All list endpoints paginated (`limit` default 50, max 500). Mutations return the updated row.

---

## Pillar 3 — Canonical Join Paths

**Goal:** Tell the model *the* right way to join common table pairs, so it doesn't invent wrong ones.

A `JoinHint` captures a canonical join between two tables, including the T-SQL predicate, cardinality, and priority. When the assembler sees that a question likely touches tables A and B, it injects the hint(s).

**Example output in prompt:**

```
## Canonical Join Paths

-- sales.orders ⋈ sales.customers (N:1)
--   ON o.customer_id = c.id
--   Standard path: every order belongs to exactly one customer.

-- sales.orders ⋈ sales.order_items (1:N)
--   ON o.id = oi.order_id
--   Use for line-item aggregations (unit price × quantity).

-- hr.employees ⋈ hr.employees (self-join, 1:1 manager)
--   ON e.manager_id = m.id
--   LEFT JOIN — top-level managers have NULL manager_id.
```

**Retrieval rule:** include all hints where both `left_table` and `right_table` are in the assembled catalog (respecting `table_filter`). Sort by `priority` ascending.

---

## Pillar 4 — Few-Shot Examples

**Goal:** Show the model 3–5 worked examples that closely resemble the current question.

### Storage

`query_examples` table (Pillar 2). Seeded with 25–30 curated Contoso pairs covering:

| Category | Count | Example |
|----------|------:|---------|
| Simple filter + sort | 3 | "Top 10 highest-paid employees" |
| Single-table aggregation | 3 | "Total salary by department" |
| 2-table join + aggregation | 4 | "Revenue per customer last quarter" |
| 3+ table joins | 4 | "Products with no sales in any region" |
| Window functions | 3 | "Rank employees by tenure within department" |
| CTEs | 3 | "Customers whose first order was in 2024" |
| Self-joins | 2 | "Employees managed by Alice's team" |
| `EXISTS`/`NOT EXISTS` | 2 | "Customers who never placed a second order" |
| Date range + rolling | 2 | "Rolling 7-day order count per region" |
| `CASE`/pivoting | 2 | "Order counts by status as columns" |

Each example has `tags_json` for categorization and `tables_used_json` for retrieval.

### Retrieval: BM25 over curated set

Use [`rank_bm25`](https://pypi.org/project/rank-bm25/) (pure Python, no external service). Corpus document per example: `natural_language + " " + tables_used + " " + tags`. At request time:

1. Tokenize the question.
2. Score all examples for the connection.
3. Apply **hard filter**: examples whose `tables_used` ⊆ the assembled catalog's table filter (if any).
4. Take top-K (default K=5).
5. Cache the BM25 index per connection with a TTL (invalidated on example mutation).

**Why BM25 and not embeddings:** fits in-memory for the ~30 examples we seed, zero infra, no API call latency, deterministic. Vector retrieval is a clean upgrade path when the corpus grows past a few hundred examples (see *Future Extensions*).

### Auto-mining from run history (secondary path)

A nightly job (or admin-triggered `POST /api/metadata/query-examples/mine`) promotes high-quality `Run` records into `query_examples` with `source = "mined_from_runs"` and `approved = False`. Promotion criteria:

- `Run.status == "success"`
- Generated SQL validated (no syntax errors, optional dry-run passed)
- User thumbs-up or explicit flag (UI surfaces a "save as example" button on run detail)

Mined examples require `approved = True` before being eligible for retrieval.

### Prompt format

```
## Example Queries

-- Q: Revenue per customer in Q4 2025, top 10
-- Tables: sales.orders, sales.customers
WITH q4 AS (
  SELECT customer_id, SUM(total_amount) AS revenue
  FROM sales.orders
  WHERE order_date BETWEEN '2025-10-01' AND '2025-12-31'
  GROUP BY customer_id
)
SELECT TOP 10 c.name, q.revenue
FROM q4 q JOIN sales.customers c ON q.customer_id = c.id
ORDER BY q.revenue DESC;

-- Q: Employees with more direct reports than their own manager
...
```

---

## Pillar 5 — Column Value Samples

**Goal:** Help the model generate correct filter predicates on categorical/enum columns.

If `sales.orders.status` takes values `{'NEW', 'PAID', 'SHIPPED', 'CANCELLED'}`, the model should use those literals — not `'pending'` or `'P'`.

### Collection

`backend/scripts/refresh_column_value_samples.py` (also exposed via admin API). For each column in each table of a connection:

1. Run `SELECT COUNT(DISTINCT col), COUNT(*) FROM <table>` (with `TOP 100000` safeguard).
2. If `distinct_count <= max_cardinality` (default 50): store all distinct values with counts.
3. Else: mark `is_low_cardinality = False` and store only a handful of representative values (top 10 by count).
4. Skip columns typed as text/JSON/binary or with more than ~100 chars average length unless explicitly configured.
5. Store refresh timestamp; re-sample on a schedule (weekly) or on demand.

All reads go through `DevDBService.query()` with existing read-only guard + row limit + timeout.

### Prompt format

Only included for columns whose table is in the assembled catalog, and only low-cardinality columns:

```
## Column Value Samples (filter/enum guidance)

sales.orders.status: 'NEW' (12034), 'PAID' (8917), 'SHIPPED' (4502), 'CANCELLED' (211)
sales.orders.region: 'NA' (18021), 'EU' (6123), 'APAC' (1520)
hr.employees.employment_type: 'FULL_TIME' (482), 'CONTRACT' (61), 'INTERN' (14)
```

Token cost is small (a few hundred tokens for a typical assembled catalog) and the accuracy lift on filter predicates is substantial.

---

## Pillar 6 — Context Assembler

**Goal:** Orchestrate the pillars into a single prompt string that respects a token budget.

Module: `backend/app/nl2sql/schema_context/assembler.py`.

```python
@dataclass
class AssembledContext:
    schema_ddl: str
    glossary: str
    join_hints: str
    examples: str
    value_samples: str
    conversation_refs: str
    estimated_tokens: int
    trace: AssemblyTrace            # what was included / dropped, for observability

class ContextAssembler:
    async def assemble(
        self,
        *,
        question: str,
        connection_id: str,
        dialect: SQLDialect,
        table_filter: list[str] | None = None,
        token_budget: int = 8_000,
        options: ContextOptions,    # flags per section (include_examples, etc.)
    ) -> AssembledContext: ...
```

### Pipeline

1. **Introspect** via `SchemaIntrospector` → `SchemaCatalog`.
2. **Enrich** — merge `SchemaAnnotation` rows into `TableDetail.description` and `ColumnDetail.description`.
3. **Retrieve glossary** — BM25 over `BusinessTerm.term + definition + aliases` → top-K (default 5).
4. **Retrieve join hints** — all hints where both tables are in the catalog, sorted by priority.
5. **Retrieve examples** — BM25 over `QueryExample.natural_language + tables_used + tags`, filtered to approved examples whose tables are in scope → top-K (default 5).
6. **Retrieve value samples** — all low-cardinality samples for columns in the catalog.
7. **Conversation refs** (stretch, Pillar 8) — extract prior entities.
8. **Budget enforcement** — if estimated tokens > budget, drop in reverse priority order:
   - Priority 1 (never drop): schema DDL, FK relationships.
   - Priority 2: table/column descriptions (merge shorter stubs first).
   - Priority 3: business glossary (drop lowest BM25 score first).
   - Priority 4: canonical join hints (drop alternatives, keep priority-0).
   - Priority 5: few-shot examples (drop lowest score first).
   - Priority 6: column value samples (drop high-cardinality first, then all).
9. **Trace** — record what was included and what was dropped, with scores, into `AssemblyTrace`. Persisted alongside the `Run` for observability.

### Token budget defaults

- `compact_ddl` format: 8,000 token budget is comfortable for ~30 tables with all pillars enabled.
- `concise_notation`: 4,000 budget sufficient; use for 100+ table schemas.
- Budget is a parameter, not a hard ceiling — the assembler reports actual usage and callers can override.

---

## Pillar 7 — Enhanced Prompt Template

The default prompt template (`backend/app/nl2sql/prompts.py`) gains sections that are elided when empty:

```
You are an expert SQL engineer specializing in {dialect_name}.

## Database Schema
{schema_ddl}

## Business Glossary
{glossary}

## Canonical Join Paths
{join_hints}

## Column Value Samples (filter/enum guidance)
{value_samples}

## Example Queries
{examples}

## Conversation Context
{conversation_refs}

## SQL Dialect
{dialect_guidance}

## Instructions
- Generate one or more SQL query approaches for the given question.
- Before writing SQL, briefly state which tables you'll use and why in `assumptions`.
- Prefer the canonical join paths provided. If you deviate, explain why in `assumptions`.
- For categorical filters, use values from the column value samples when applicable.
- If a business glossary term matches, prefer its canonical SQL expression.
- When multiple interpretations exist, provide each as a separate query entry.
- Set `recommended_index` to the 0-based index of the query you recommend.
- List assumptions about ambiguous terms, soft-delete behavior, date ranges, etc.

## SQL Rules
- Use meaningful table aliases.
- Prefer explicit JOINs; always qualify columns when multiple tables are involved.
- Avoid SELECT * in production queries.
- Use CTEs for multi-step logic.

## Response Format
(unchanged — JSON schema with queries[], recommended_index, assumptions[])
```

### `build_system_prompt` signature

`backend/app/nl2sql/prompts.py` already supports `schema_context` and `custom_prompt`. Extend to:

```python
def build_system_prompt(
    *,
    dialect: SQLDialect,
    schema_context: str | None = None,
    glossary: str | None = None,
    join_hints: str | None = None,
    value_samples: str | None = None,
    examples: str | None = None,
    conversation_refs: str | None = None,
    custom_prompt: str | None = None,
) -> str: ...
```

When `custom_prompt` is set, it still wins as a full override (power-user path unchanged).

### Fix `_build_chat_request`

`backend/app/nl2sql/service.py:122-126` currently passes only `custom_prompt`, so the `{schema_context}` placeholder is never populated by the auto path. Change to:

```python
system_prompt = build_system_prompt(
    dialect=request.dialect,
    schema_context=assembled.schema_ddl,
    glossary=assembled.glossary,
    join_hints=assembled.join_hints,
    value_samples=assembled.value_samples,
    examples=assembled.examples,
    conversation_refs=assembled.conversation_refs,
    custom_prompt=request.system_prompt,
)
```

---

## Pillar 8 — Conversation-Aware Context (Stretch)

`NL2SQLRequest` already carries `conversation_history`. Today that history is appended as raw `Message` turns to the chat request; it's not used to *enrich* the system prompt.

When prior turns referenced specific tables ("show me last quarter's orders" → "now filter to EU only"), the assembler extracts those entities and prepends a `## Conversation Context` block:

```
## Conversation Context

Previous turns referenced:
  - sales.orders (mentioned 2 times)
  - sales.customers (mentioned 1 time)
If the current question uses pronouns ("them", "their", "those"), they likely refer to these tables.
```

Extraction is string-matching against the catalog's table and column names plus annotated synonyms. Deferred to M7.

---

## Pillar 9 — Static Validation + Self-Repair Loop

**Goal:** Catch hallucinated identifiers and malformed T-SQL before surfacing results; give the model one chance to correct itself.

Module: `backend/app/nl2sql/repair.py`.

### Step 1: Static validation

Use [`sqlglot`](https://github.com/tobymao/sqlglot) with `dialect="tsql"` to:

1. **Parse** the SQL — syntax errors caught here are returned as `SQLValidationResult.syntax_errors`.
2. **Extract referenced tables and columns** from the AST.
3. **Catalog check** — verify every referenced `schema.table` exists in the `SchemaCatalog` and every qualified column exists on its table.
4. **Report** — list of `unknown_table` / `unknown_column` errors with suggestions (fuzzy match against catalog for "did you mean").

No DB round-trip; runs in milliseconds.

### Step 2: Dry-run against target DB (gated)

Opt-in via config flag `NL2SQL_DRY_RUN_ENABLED` (default `False`). When enabled and static validation passed:

1. Wrap the SQL: `SELECT * FROM (<sql>) AS __dry_run WHERE 1=0` (forces 0 rows) or for T-SQL: `SET PARSEONLY ON; <sql>; SET PARSEONLY OFF;` as an initial cheap check, then a `SELECT TOP 0 * FROM (...)` for binding validation.
2. Execute via `DevDBService.query()` — inherits read-only guard, 5-second timeout, row limit.
3. Capture any database error (binding, type mismatch, missing column after a rename, etc.).

### Step 3: Repair attempt (gated)

Opt-in via `NL2SQL_REPAIR_ENABLED` (default `False`). When enabled and either validation step failed:

1. Build a repair prompt: original question + original SQL + error message + the *same* assembled context.
2. Single LLM call asking for a corrected SQL.
3. Re-run static validation (and dry-run if enabled).
4. If still fails, return with `repair_history` populated but original SQL preserved for debugging.

Max attempts: 1 by default (configurable up to 3). Each attempt costs one LLM call plus one dry-run.

### Response shape

Extend `NL2SQLResponse` with:

```python
class RepairAttempt(BaseModel):
    error_type: Literal["static", "dry_run"]
    error_message: str
    repaired_sql: str | None
    validation_status: Literal["pass", "fail"]

class NL2SQLResponse(BaseModel):
    # ... existing fields ...
    repair_history: list[RepairAttempt] = Field(default_factory=list)
```

### Observability

Persist `repair_attempts` count and token cost into `Run.tags` (JSON) or a new `run_context_stats` column. Dashboard: repair success rate, avg attempts per query, repair token cost vs generation token cost.

---

## Pillar 10 — Observability & Measurement

Context construction is only valuable if we can measure its effect on answer quality.

### Per-run telemetry

Extend `Run` (or add `NL2SQLTelemetry` table keyed by `run_id`) with:

- `context_tokens_schema`, `context_tokens_glossary`, `context_tokens_examples`, `context_tokens_samples` — token cost per pillar.
- `examples_used_json` — IDs of few-shot examples pulled.
- `glossary_terms_used_json` — IDs of business terms pulled.
- `join_hints_used_json` — IDs of hints pulled.
- `static_validation_result` — pass/fail + error count.
- `dry_run_result` — pass/fail + error type.
- `repair_attempt_count`.
- `user_thumbs_up` / `user_thumbs_down` — populated from run detail UI.

### Offline evaluation

Maintain a gold set in `backend/tests/eval/contoso_gold.yaml`:

```yaml
- question: "Top 5 departments by total salary, 2025"
  expected_tables: [hr.employees, hr.departments]
  expected_result_columns: [department_name, total_salary]
  gold_sql: |
    SELECT TOP 5 d.name, SUM(e.salary) AS total_salary
    ...
  accept_variants:
    - allow_different_join_order: true
    - allow_cte_or_subquery: true
```

Runner (`backend/scripts/eval_nl2sql.py`) executes the pipeline for every gold entry, compares result sets against the gold SQL (set equality), and reports accuracy per category (simple, moderate, complex). Track accuracy over time to validate that each new pillar moves the number.

---

## Frontend Integration

### QueryLab page

`frontend/src/pages/QueryLab.tsx` gains state:

```ts
const [connectionId, setConnectionId] = useState<string>("contoso_prod")
const [schemaContext, setSchemaContext] = useState<string>("")
const [contextOptions, setContextOptions] = useState<ContextOptions>({
  include_glossary: true,
  include_examples: true,
  include_value_samples: true,
  include_join_hints: true,
})
```

Request body sends `connection_id`, `schema_context` (when manually edited), and `context_options`. Leaves `system_prompt` for the full-override power user path.

### SchemaPromptEditor component

Transform `frontend/src/components/querylab/SchemaPromptEditor.tsx` to a two-mode component:

- **Auto mode (default):** format selector (DDL / Catalog / Concise), "Load from connection" button, token estimate badge, collapsible per-pillar preview, toggles for each context option. Read-only text area shows what will be sent.
- **Manual mode:** existing textarea, used as full override (emits `system_prompt`).

### Metadata admin UI

New route `/metadata` with tabs: Annotations, Business Terms, Join Hints, Query Examples. Each tab is a filterable table with inline editing, bulk import (CSV/JSON), and an "examples" tab adds a "Try it" button that sends the example's NL through the NL2SQL pipeline and diffs against stored SQL.

---

## Rollout Milestones

Smaller deployable increments. Each milestone ships independently and moves the accuracy dial measurably.

**M1 — Foundation (ships first)**
- Phases 1–5 of the original plan: `schema_context` module, FK/PK introspection, `/api/dev/db/schema-context`, fix `_build_chat_request`, dual-mode frontend editor.
- Unblocks: the paste-the-DDL hack goes away.

**M2 — Metadata backbone**
- ORM models + Alembic migration (Azure SQL / T-SQL types).
- Seed script for Contoso (~40 annotations, ~18 terms, ~25 join hints, ~28 curated examples).
- Admin API router (CRUD for all entities), gated by `METADATA_ADMIN_ENABLED`.

**M3 — Context assembler + enhanced prompt**
- `ContextAssembler` with BM25 retrieval (`rank_bm25` dependency).
- Enhanced `build_system_prompt` signature and template.
- New fields on `NL2SQLRequest`: `connection_id`, `context_options`.
- Telemetry columns on `Run`.

**M4 — Validation + repair loop**
- `sqlglot` integration for static validation.
- Opt-in dry-run (`NL2SQL_DRY_RUN_ENABLED`).
- Opt-in repair (`NL2SQL_REPAIR_ENABLED`), max 1 attempt.

**M5 — Column value samples**
- ORM + refresh script + refresh endpoint.
- Assembler integration.

**M6 — Metadata admin UI**
- `/metadata` route in frontend.
- Run-detail "save as example" action for mining.

**M7 — Conversation-aware context (stretch)**
- Entity extraction from `conversation_history`.
- "Conversation Context" prompt block.

---

## Future Extensions (Out of Scope)

- **Vector retrieval.** Once `query_examples` grows beyond a few hundred, replace BM25 with embeddings (pgvector or SQL Server vector ops). Hybrid BM25 + vector is cleanest.
- **Two-stage table selection.** For schemas with 500+ tables, a first LLM call picks relevant tables, a second generates SQL with only those tables' schema. Our ~30-table seed doesn't need this yet.
- **Self-consistency voting.** Generate N candidate SQLs at higher temperature, pick the most common result via set equality on dry-run. Expensive but lifts accuracy on ambiguous questions.
- **Schema drift detection.** Cache `SchemaCatalog` with TTL; detect when a table's column set diverges from the last cached version and invalidate dependent annotations.
- **Learned glossary.** Mine business terms from accepted `Run.assumptions` fields over time.
- **Query plan hints.** For very large tables, expose `sys.dm_db_index_usage_stats` summaries so the LLM prefers indexed access paths.

---

## Verification Checklist (per milestone)

1. **Unit tests** — formatters, introspector, assembler (with fixtures for each pillar), BM25 retrieval, static validator, repair loop.
2. **Integration test** — Azure SQL test database with the Contoso seed. Run every gold-set question; assert set-equality of result sets.
3. **Regression test** — `uv run pytest -v` must remain green; assert that the `_build_chat_request` fix doesn't break backward-compatible paths (`system_prompt`-only override).
4. **Manual QA** — Start backend with `DEV_DB_TOOLS_ENABLED=true` and `METADATA_ADMIN_ENABLED=true`. Seed Contoso metadata. Open QueryLab → pick `contoso_prod` connection → ask a moderate-complexity question ("top 5 products by Q4 2025 revenue, excluding cancelled orders, joined with customer region") → inspect `raw_llm_output` to confirm glossary terms, join hints, value samples, and examples all appear in the system prompt.
5. **Accuracy regression** — Run `backend/scripts/eval_nl2sql.py` against the gold set before and after each milestone; accuracy should be monotonically non-decreasing.

---

## Key Files Summary

| File | Change |
|------|--------|
| `backend/app/nl2sql/schema_context/__init__.py` | New — public exports |
| `backend/app/nl2sql/schema_context/models.py` | New — Pydantic catalog models |
| `backend/app/nl2sql/schema_context/formatters.py` | New — 3 formatters + dispatcher |
| `backend/app/nl2sql/schema_context/introspector.py` | New — DB introspection with FK/PK |
| `backend/app/nl2sql/schema_context/service.py` | New — orchestration service (Pillar 1) |
| `backend/app/nl2sql/schema_context/assembler.py` | New — context assembler (Pillar 6) |
| `backend/app/nl2sql/retrieval.py` | New — BM25 retrieval over examples/terms |
| `backend/app/nl2sql/repair.py` | New — static validation + self-repair |
| `backend/app/metadata/__init__.py` | New |
| `backend/app/metadata/models.py` | New — SchemaConnection, SchemaAnnotation, BusinessTerm, JoinHint, QueryExample, ColumnValueSample |
| `backend/app/metadata/service.py` | New — CRUD + retrieval helpers |
| `backend/app/devdb/dialects.py` | Modify — add FK/PK SQL helpers |
| `backend/app/nl2sql/schemas.py` | Modify — add `schema_context`, `connection_id`, `context_options`, `repair_history` |
| `backend/app/nl2sql/prompts.py` | Modify — extend template + `build_system_prompt` signature |
| `backend/app/nl2sql/service.py` | Modify — fix `_build_chat_request`; integrate assembler + repair |
| `backend/app/routers/dev_db.py` | Modify — add `/schema-context` endpoint |
| `backend/app/routers/schema_metadata.py` | New — metadata admin API |
| `backend/migrations/versions/XXXX_metadata.py` | New — Alembic migration for metadata tables |
| `backend/scripts/seed_contoso_metadata.py` | New — seed script |
| `backend/scripts/import_extended_properties.py` | New — optional importer |
| `backend/scripts/refresh_column_value_samples.py` | New — value sampler |
| `backend/scripts/eval_nl2sql.py` | New — offline evaluation runner |
| `backend/tests/eval/contoso_gold.yaml` | New — gold question set |
| `frontend/src/api/types.ts` | Modify — add new types |
| `frontend/src/api/client.ts` | Modify — add metadata + schema-context API calls |
| `frontend/src/components/querylab/SchemaPromptEditor.tsx` | Modify — dual-mode |
| `frontend/src/pages/QueryLab.tsx` | Modify — wire connection + context options |
| `frontend/src/pages/MetadataAdmin.tsx` | New — `/metadata` route |

---

## Configuration Reference

New environment variables (`backend/.env.example`):

```
# Metadata admin endpoints (writes to app DB)
METADATA_ADMIN_ENABLED=false

# NL2SQL execution feedback loop
NL2SQL_DRY_RUN_ENABLED=false
NL2SQL_REPAIR_ENABLED=false
NL2SQL_MAX_REPAIR_ATTEMPTS=1

# Context assembler defaults
NL2SQL_CONTEXT_TOKEN_BUDGET=8000
NL2SQL_CONTEXT_EXAMPLE_TOP_K=5
NL2SQL_CONTEXT_GLOSSARY_TOP_K=5
```

New Python dependencies (via `uv add`):

- `sqlglot` — SQL parsing and catalog validation.
- `rank-bm25` — pure-Python BM25 retrieval.
