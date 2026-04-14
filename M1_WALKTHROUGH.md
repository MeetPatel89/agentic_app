# M1 Walkthrough — Schema Context Foundation

A hands-on guide for exercising everything shipped in M1 of the
[Schema Context Plan](./SCHEMA_CONTEXT_PLAN.md). It covers the backend
endpoint, the Query Lab dual-mode editor, and the code you can peek at
to understand how the pieces fit together.

> **Scope reminder:** M1 is the foundation only — live-DB introspection,
> three prompt formatters, a new dev-DB endpoint, the fix that lets the
> default NL→SQL system prompt actually receive schema context, and a
> dual-mode frontend editor. M2+ (metadata backbone, retrieval, static
> validation, samples, admin UI) is still future work.

---

## 1. What M1 actually changed

| Area | Before M1 | After M1 |
| --- | --- | --- |
| FK introspection | Not supported in `DevDBService` | `list_foreign_keys` works on SQLite / Postgres / Azure SQL |
| PK introspection | Hard-coded `is_primary_key=False` for non-SQLite | `primary_keys_sql()` per dialect + populated set |
| Schema prompt | User had to paste raw DDL in a textarea | Three formatters + live introspector |
| NL→SQL template | `{schema_context}` slot was literal text | Wired through `NL2SQLRequest.schema_context` |
| Frontend editor | Plain textarea | `SchemaPromptEditor` with Auto / Manual modes |
| Dev API | `tables`, `describe`, `query` | New `GET /api/dev/db/schema-context` |

---

## 2. Code map — where to peek

```
backend/app/
├── devdb/
│   ├── dialects.py              ← foreign_keys_sql / primary_keys_sql / pragma variant
│   └── service.py               ← list_foreign_keys; describe_table PK fix
├── nl2sql/
│   ├── schema_context/          ← NEW module
│   │   ├── __init__.py
│   │   ├── models.py            ← Pydantic: ColumnDetail, TableDetail, SchemaCatalog,
│   │   │                          SchemaContextFormat, SchemaContextResponse
│   │   ├── formatters.py        ← compact_ddl / structured_catalog / concise_notation
│   │   ├── introspector.py      ← SchemaIntrospector (asyncio.gather + Semaphore(10))
│   │   └── service.py           ← SchemaContextService (facade)
│   ├── schemas.py               ← NL2SQLRequest.schema_context field (new)
│   └── service.py               ← _build_chat_request now passes schema_context
└── routers/dev_db.py            ← GET /api/dev/db/schema-context

frontend/src/
├── api/
│   ├── client.ts                ← fetchSchemaContext(params?)
│   └── types.ts                 ← SchemaContextFormat / SchemaContextResponse / NL2SQLRequest.schema_context
├── components/querylab/
│   └── SchemaPromptEditor.tsx   ← Dual-mode Auto / Manual
└── pages/QueryLab.tsx           ← wires mode, format, schema_context, system_prompt into request

backend/tests/
├── test_schema_context.py       ← formatters + introspector + service (new)
├── test_nl2sql_service.py       ← TestBuildChatRequest (new)
└── test_devdb_router_gating.py  ← schema-context path gating (updated)
```

---

## 3. Setup — one-time dev database

M1 is best experienced end-to-end against a tiny SQLite DB that has
foreign keys. The app's `AUTO_CREATE_SCHEMA=true` doesn't help here
because we want **our own tables** (employees/departments) to see the
relationships formatting.

```bash
cd backend
cp .env.example .env   # if you haven't already
```

Make sure `.env` has:

```dotenv
DEV_DB_TOOLS_ENABLED=true
DEV_DB_TOOLS_REQUIRE_LOCALHOST=true
DATABASE_URL=sqlite+aiosqlite:///./llm_router.db
AUTO_CREATE_SCHEMA=true
# plus at least one provider key, e.g. OPENAI_API_KEY=sk-...
```

Seed a couple of human-friendly tables into the same DB the dev-DB
tools will introspect:

```bash
uv run python - <<'PY'
import sqlite3
conn = sqlite3.connect("llm_router.db")
cur = conn.cursor()
cur.executescript("""
CREATE TABLE IF NOT EXISTS departments (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    budget NUMERIC
);

CREATE TABLE IF NOT EXISTS employees (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT,
    manager_id    INTEGER,
    department_id INTEGER NOT NULL,
    salary        NUMERIC,
    hired_on      DATE,
    FOREIGN KEY(manager_id)    REFERENCES employees(id),
    FOREIGN KEY(department_id) REFERENCES departments(id)
);

INSERT OR IGNORE INTO departments(id, name, budget) VALUES
    (1, 'Engineering', 1000000),
    (2, 'Sales',        500000);

INSERT OR IGNORE INTO employees(id, name, email, manager_id, department_id, salary, hired_on) VALUES
    (1, 'Alice', 'alice@acme.com', NULL, 1, 180000, '2020-01-15'),
    (2, 'Bob',   'bob@acme.com',   1,    1, 140000, '2021-06-01'),
    (3, 'Carol', 'carol@acme.com', NULL, 2, 160000, '2019-09-09');
""")
conn.commit()
conn.close()
print("seeded.")
PY
```

Now start the backend:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

---

## 4. Backend endpoint — `GET /api/dev/db/schema-context`

### 4.1 Default format (`compact_ddl`)

```bash
curl -s "http://localhost:8000/api/dev/db/schema-context" | jq .
```

Expected shape:

```json
{
  "format": "compact_ddl",
  "schema_text": "CREATE TABLE departments (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL,\n  budget NUMERIC\n);\n\nCREATE TABLE employees (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL,\n  email TEXT,\n  manager_id INTEGER REFERENCES employees(id),\n  department_id INTEGER NOT NULL REFERENCES departments(id),\n  salary NUMERIC,\n  hired_on DATE\n);\n\n-- Relationships:\n-- employees.manager_id -> employees.id (self-referencing)\n-- employees.department_id -> departments.id",
  "table_count": 2,
  "estimated_tokens": 87
}
```

Pretty-printed `schema_text` (what actually goes into the LLM prompt):

```sql
CREATE TABLE departments (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  budget NUMERIC
);

CREATE TABLE employees (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT,
  manager_id INTEGER REFERENCES employees(id),
  department_id INTEGER NOT NULL REFERENCES departments(id),
  salary NUMERIC,
  hired_on DATE
);

-- Relationships:
-- employees.manager_id -> employees.id (self-referencing)
-- employees.department_id -> departments.id
```

### 4.2 Structured catalog (Markdown)

```bash
curl -s "http://localhost:8000/api/dev/db/schema-context?format=structured_catalog" \
  | jq -r .schema_text
```

```markdown
### departments

| Column | Type | PK | FK | Nullable | Description |
|---|---|---|---|---|---|
| id | INTEGER | ✓ |  | N |  |
| name | TEXT |  |  | N |  |
| budget | NUMERIC |  |  | Y |  |

### employees

| Column | Type | PK | FK | Nullable | Description |
|---|---|---|---|---|---|
| id | INTEGER | ✓ |  | N |  |
| name | TEXT |  |  | N |  |
| email | TEXT |  |  | Y |  |
| manager_id | INTEGER |  | → employees.id | Y |  |
| department_id | INTEGER |  | → departments.id | N |  |
| salary | NUMERIC |  |  | Y |  |
| hired_on | DATE |  |  | Y |  |
```

### 4.3 Concise notation (token-saver)

```bash
curl -s "http://localhost:8000/api/dev/db/schema-context?format=concise_notation" \
  | jq -r .schema_text
```

```
departments(id*:integer, name:text, budget:numeric)
employees(id*:integer, name:text, email:text, manager_id->employees:integer, department_id->departments:integer, salary:numeric, hired_on:date)
```

`*` marks PKs, `->table` marks FKs. Same info as `compact_ddl`, but
typically ~50% fewer tokens — useful when you're hammering a large
schema into a small context window.

### 4.4 Filtering & FK toggle

```bash
# Only one table:
curl -s "http://localhost:8000/api/dev/db/schema-context?tables=employees" | jq -r .schema_text

# Skip the Relationships block entirely:
curl -s "http://localhost:8000/api/dev/db/schema-context?include_foreign_keys=false" \
  | jq -r .schema_text
```

### 4.5 Gating

Flip the feature off and prove the route disappears:

```bash
DEV_DB_TOOLS_ENABLED=false uv run uvicorn app.main:app --port 8001 &
sleep 1
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8001/api/dev/db/schema-context"
# → 404
kill %1
```

---

## 5. Frontend — Query Lab dual-mode editor

Start the frontend in a second terminal:

```bash
cd frontend
npm install       # first time only
npm run dev       # http://localhost:5173
```

Open **Query Lab** (`http://localhost:5173/query-lab`). The schema
prompt editor now has a mode toggle at the top.

### 5.1 Auto mode (recommended)

1. Pick a format (`Compact DDL` / `Structured catalog` / `Concise notation`).
2. Click **Load from connection**.
3. The textarea fills with the same text you saw from `curl` above, and
   badges show `2 tables` and `~87 tokens`.
4. Type a prompt in the NL input (e.g. *"Who are the top 3 highest-paid
   employees along with their department name?"*) and run it.
5. Peek at the **Raw LLM output** panel — you'll see the generated SQL
   references `employees.department_id = departments.id`, which is only
   possible because the schema context was delivered to the model.

**What happens on the wire:** the frontend sends

```json
POST /api/nl2sql/generate
{
  "provider": "openai",
  "model": "gpt-4o",
  "natural_language": "Who are the top 3 ...",
  "dialect": "sqlite",
  "schema_context": "CREATE TABLE departments (\n  id INTEGER PRIMARY KEY, ..."
}
```

…and `_build_chat_request` (see §6.2) expands the default system-prompt
template so `{schema_context}` is replaced by the real DDL.

### 5.2 Manual mode (full override)

1. Click the **Manual** toggle.
2. Paste any fully-formed system prompt, e.g.:

```text
You are a SQL analyst for the ACME HR schema. Always quote identifiers.
Schema:
-- employees(id PK, name, email, manager_id FK, department_id FK, salary, hired_on)
-- departments(id PK, name, budget)

Return only JSON with keys queries[], recommended_index, assumptions[].
```

3. The frontend sends `system_prompt` instead of `schema_context`. The
   default template is bypassed entirely (covered by
   `TestBuildChatRequest.test_system_prompt_override_bypasses_schema_context`).

This is the escape hatch for advanced users — full control, no magic.

---

## 6. Code highlights (read these three snippets)

### 6.1 Introspector — bounded-concurrency fan-out

`backend/app/nl2sql/schema_context/introspector.py:42-91`

```python
async def _describe_one(name: str, schema_name: str | None) -> TableDetail:
    async with self._semaphore:                       # cap at 10 parallel describes
        describe = await self._service.describe_table(...)
        columns = [ColumnDetail(...) for col in describe.columns]
        fks: list[ForeignKeyInfo] = []
        if include_foreign_keys:
            fk_rows = await self._service.list_foreign_keys(...)
            fks = [ForeignKeyInfo(...) for row in fk_rows]
        return TableDetail(name=name, schema_name=schema_name,
                           columns=columns, foreign_keys=fks)

details = await asyncio.gather(*(_describe_one(t.name, t.schema_name) for t in selected))
```

A 100-table schema introspects in roughly the time of ~10 serialized
`describe_table` calls, not 100.

### 6.2 Template wiring — the one-line fix that makes M1 worth it

`backend/app/nl2sql/service.py` (inside `_build_chat_request`)

```python
system_prompt = build_system_prompt(
    dialect=request.dialect,
    schema_context=request.schema_context,   # ← added in M1; was missing
    custom_prompt=request.system_prompt,
)
```

Before this change, the default template contained a literal
`{schema_context}` in the system message, and no code path ever filled
it in. LLMs were producing SQL against imaginary tables. Regression
test: `tests/test_nl2sql_service.py::TestBuildChatRequest`.

### 6.3 Formatter — the "Relationships" block

`backend/app/nl2sql/schema_context/formatters.py:21-38`

```python
for table in catalog.tables:
    blocks.append(_compact_ddl_for_table(table))
    for fk in table.foreign_keys:
        left  = _qualified_column(table.schema_name, table.name, fk.column_name)
        right = _qualified_column(fk.referenced_schema, fk.referenced_table, fk.referenced_column or "")
        suffix = ""
        if fk.referenced_table == table.name and (fk.referenced_schema in (None, table.schema_name)):
            suffix = " (self-referencing)"
        relationships.append(f"-- {left} -> {right}{suffix}")
```

The self-reference detection (`employees.manager_id -> employees.id`)
helps models generate proper hierarchical queries — they otherwise tend
to join `employees` to itself without realizing it's legal.

---

## 7. Tests to run

```bash
cd backend
uv run pytest -v tests/test_schema_context.py          # 6 tests: formatters, introspector, service
uv run pytest -v tests/test_nl2sql_service.py          # incl. TestBuildChatRequest
uv run pytest -v tests/test_devdb_router_gating.py     # schema-context path gated by DEV_DB_TOOLS_ENABLED
uv run pytest -q                                       # full suite (143 tests)
```

All pass as of commit on the current branch.

---

## 8. Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `404` on `/api/dev/db/schema-context` | `DEV_DB_TOOLS_ENABLED` is not `true` in `.env` |
| `table_count: 0` but DB has tables | Dev-DB tools are pointed at a different file than the seed script (check `DATABASE_URL`) |
| `Load from connection` button spins forever | Check backend logs — most likely an exception caught in the router and returned as 502 with a generic message |
| FK block missing in `compact_ddl` | The backend reported 0 FKs — for SQLite, confirm the `CREATE TABLE` used inline `FOREIGN KEY(...)` clauses (needed by `PRAGMA foreign_key_list`) |
| Manual-mode prompt ignored | You forgot the JSON contract — the default parser falls back to raw SQL, so always include `{"queries": [...], "recommended_index": 0, "assumptions": []}` format in custom prompts |

---

## 9. What's next (not in M1)

Future milestones queued in `SCHEMA_CONTEXT_PLAN.md`:

- **M2** — Persisted metadata (table/column descriptions, synonyms) with Alembic migration + Contoso seed.
- **M3** — Context assembler + BM25 retrieval for large schemas (pick the top-k relevant tables per question).
- **M4** — Static SQL validation + self-repair loop (parse, check identifiers against catalog, retry on error).
- **M5** — Column-value samples ("region IN ('EMEA', 'AMER', 'APAC')").
- **M6** — Metadata admin UI.
- **M7** — Conversation-aware context (carry schema selection between turns).
