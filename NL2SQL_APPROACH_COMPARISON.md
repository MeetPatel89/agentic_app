# NL-to-SQL Approach Comparison — Cisco/AWS vs. QueryLab Plan

## Purpose

This document compares the Cisco + AWS Bedrock "enterprise NL-to-SQL" pattern described in the AWS Machine Learning blog (April 2025, co-authored with Renuka Kumar and Thomas Matthew from Cisco) against the design in [`SCHEMA_CONTEXT_PLAN.md`](./SCHEMA_CONTEXT_PLAN.md). It is meant to be read alongside the plan — not as a replacement. The goal is to surface the places where the two approaches converge, the places where they diverge, and the specific Cisco techniques worth absorbing or deferring.

**Bottom line up front:** Cisco solves a harder problem (thousands of tables across Aurora/Oracle/Teradata) and therefore adds two heavyweight stages — **domain classification** and **named-entity resolution with a preamble temp-table pattern** — that QueryLab's current scope (~30 tables on a single Azure SQL instance) does not need yet. Everything else is remarkably aligned: compact domain-scoped schema, join hints, few-shot examples, metadata enrichment, and SQL execution as a validation step. Where we go further: explicit token-budget enforcement, BM25-driven retrieval, `sqlglot` static validation before any DB round-trip, and observability with an offline gold set.

---

## The Cisco / AWS Architecture in Short

Source: *Enterprise-grade natural language to SQL generation using LLMs: Balancing accuracy, latency, and scale* (AWS ML Blog, 2025) and the related multi-database implementation writeup on cloudthat.com.

**Six-stage pipeline on Bedrock, orchestrated by Lambda behind API Gateway + Cognito:**

1. **Request Preprocessing** — Two LLM-backed sub-steps: (a) *domain classification* decides which corporate domain (e.g. "olympics", "sales") the question belongs to; (b) *named resource extraction* uses NER to pull out proper nouns / entities (athlete names, product SKUs) from the question.
2. **Identifier Resolution** — Extracted entities are looked up via domain-specific lookup services and resolved to database IDs. The IDs are **not** inlined into the SQL. Instead they are staged.
3. **Request Preparation** — Two artifacts produced in parallel:
   - An LLM prompt containing the **domain-scoped** table definitions, enriched metadata comments, join hints, and few-shot examples.
   - A **SQL preamble script** that creates temp tables and populates them with the resolved IDs.
4. **SQL Generation** — A lightweight model (Claude Haiku 3 or Code Llama 13B) receives the prompt and generates SQL that references the temp tables (e.g. `WHERE athlete_id IN (SELECT id FROM #__athletes)`).
5. **SQL Execution** — The orchestrator concatenates preamble + generated SQL and runs it against the target database. The target is chosen from a **domain-to-DB mapping** (Aurora / Oracle / Teradata / …).
6. **Response Return** — Results back to the user.

**Reported numbers:** 1–3 s SQL generation with a small model; 2–5 s end-to-end for 200 named resources and 10 k rows; ">95% accuracy" across three evaluated domains.

**Schema handling strategy that sits under all six stages:**
- Domain-scoped schemas: never ship the full enterprise catalog to the LLM.
- Rich **metadata comments** on tables and columns.
- **Join hints** telling the model which join type to use between specific tables.
- **Temporary views** that abstract complex nested structures (their specific example: XML fields) and multi-dim joins.
- **Security rules per domain** that forbid certain columns from ever appearing in `SELECT`.
- **Curated few-shot examples** per domain.

---

## Side-by-Side Matrix

Compact scan of capability coverage. "○" = not present; "◐" = partial; "●" = present as a first-class pillar.

| Capability                                   | Cisco / AWS | `SCHEMA_CONTEXT_PLAN.md` |
|----------------------------------------------|:-----------:|:------------------------:|
| Domain classification (LLM)                  | ●           | ○ (single domain for now) |
| Named entity extraction (NER)                | ●           | ○                         |
| Entity → ID resolution with preamble temps   | ●           | ○                         |
| Domain-scoped schema in prompt               | ●           | ◐ (via `table_filter`)    |
| Compact DDL / catalog formatters             | ◐ (implicit) | ●                        |
| Metadata comments (table / column)           | ●           | ● (`SchemaAnnotation`)    |
| Business glossary (term → SQL expression)    | ◐ (few-shot) | ● (`BusinessTerm`)       |
| Canonical join hints                         | ●           | ● (`JoinHint`)            |
| Curated few-shot examples                    | ●           | ●                         |
| Few-shot **retrieval** (BM25 / vector)       | ○ (per-domain static set) | ● (BM25)     |
| Column value samples (enum guidance)         | ○           | ● (`ColumnValueSample`)   |
| Temporary views for nested structures        | ●           | ○ (future extension)      |
| Column-level security / redaction            | ●           | ◐ (via `tags_json` only) |
| Token-budget enforcement w/ priority drops   | ○ (domain scoping is the budget) | ●    |
| Static SQL validation before execution       | ○           | ● (`sqlglot`)             |
| Execute-to-validate (dry-run)                | ● (full exec) | ● (`TOP 0` dry-run)     |
| Self-repair LLM loop                         | ◐ (not emphasized) | ●                  |
| Observability — per-pillar token accounting  | ○           | ●                         |
| Offline gold-set evaluation                  | ○           | ●                         |
| Multi-database routing                       | ●           | ○ (single connection)     |
| Lightweight model choice                     | ● (Haiku 3, Code Llama 13B) | ◐ (configurable)|

---

## Where the Two Approaches Agree

These choices were reached independently and are load-bearing in both designs. Conviction should be high that they are correct.

1. **Don't ship the raw DDL unfiltered.** Both plans strip irrelevant tables before the LLM call. Cisco does it via domain partitioning; we do it via `table_filter` + catalog format selection.
2. **Metadata comments beat DDL alone.** Table and column descriptions meaningfully improve complex-join accuracy. Cisco relies on them; we persist them in `SchemaAnnotation`.
3. **Join hints are not optional.** Both approaches explicitly hand the model "the right way to join A and B" because the model reliably invents wrong paths otherwise.
4. **Few-shot examples are table-stakes.** Both seed a curated library of NL→SQL pairs and acknowledge that this is where complex-query accuracy comes from.
5. **Execution is the best validation.** Cisco runs the actual SQL; our Pillar 9 dry-runs with `TOP 0` but the principle is identical — the database is the oracle, not the LLM.
6. **Lightweight model, heavy prompt.** Cisco documents that Claude Haiku 3 is enough when the prompt is rich. Our design is also model-agnostic and assumes prompt quality matters more than model size.
7. **Prompt engineering, not fine-tuning (for now).** Neither approach fine-tunes a model. Cisco reaches 95%+ accuracy via prompt engineering alone; we follow the same default.

---

## What Cisco Does That We Don't

Techniques worth understanding, and a call for each on whether to absorb them into our plan.

### 1. Domain classification as a first LLM call

Cisco runs an LLM to tag the question with a domain (`olympics`, `sales`, …) before building the SQL-generation prompt. Only that domain's schema + few-shot library is passed to the generator.

**Why it works for them:** their enterprise catalog has thousands of tables across multiple business areas. Sending everything is infeasible.

**Our situation:** the Contoso seed has five schemas (hr, sales, inventory, finance, support) — small enough that a single well-assembled prompt can carry them all. Our plan's `table_filter` is a caller-supplied knob; it isn't driven by an LLM.

**Recommendation — Defer, but document a clean upgrade path.** Add "LLM-driven table selection" to *Future Extensions* (it's already there as "two-stage table selection"). Revisit when we cross ~150 tables or add a second business domain.

### 2. Named entity extraction + ID resolution with preamble temp tables

Arguably Cisco's most distinctive technique. The pipeline:
- NER pulls entities from the question: *"What was Michael Phelps' medal count in 2008?"* → entity = "Michael Phelps".
- A domain-specific lookup service resolves "Michael Phelps" → `athlete_id = 14721`.
- The orchestrator emits a preamble: `CREATE TEMP TABLE #athletes (id INT); INSERT INTO #athletes VALUES (14721);`.
- The LLM is told "the user's resources are in `#athletes`" and generates: `SELECT ... WHERE athlete_id IN (SELECT id FROM #athletes)`.

**Why it's clever:**
- The LLM never has to guess at literal values or spellings ("Phelps" vs "Michael Phelps" vs "M. Phelps").
- Set-style filters (`IN`) compose cleanly with the rest of the query.
- The resolution layer is deterministic (DB lookup), not hallucinated.
- Works for multi-entity questions ("Phelps and Ledecky") without prompt inflation.

**Our situation:** our column-value-samples pillar (Pillar 5) solves a *different* but overlapping problem — it shows the model the legal enum values for `status`, `region`, `employment_type`. It does **not** solve entity disambiguation for names/free-text columns.

**Recommendation — Absorb a trimmed version.** A fair fit for our scope is:
- For columns tagged as "named-entity" in `SchemaAnnotation` (e.g. `sales.customers.name`, `hr.employees.full_name`), run a fuzzy-match lookup against the question.
- If one or more matches are found, include a `## Resolved Entities` block in the prompt: `-- "Phelps" → sales.customers.id IN (14721, 14829)`.
- No preamble temp table needed on Azure SQL — we can inline the list as a `VALUES` CTE or as a literal `IN (...)`, since our rows-per-query envelope is small.
- Defer the full preamble pattern until we hit real scale problems.

This belongs as a new **Pillar 11 — Entity Resolution** in the plan, scheduled for a later milestone (post-M6).

### 3. Temporary views over complex / nested structures

Cisco wraps XML-typed columns and multi-dimensional joins in deterministic SQL views and only shows the LLM the view, never the underlying structure.

**Why it works:** LLMs are bad at XML and OLAP-cube-style joins but great at flat tables.

**Our situation:** Contoso is fully relational — no XML, no cubes. The pattern matters zero today.

**Recommendation — Document only.** Mention in `SCHEMA_CONTEXT_PLAN.md` Future Extensions as "Abstraction views for complex types". If and when a customer schema arrives with JSON/XML columns, reach for this first.

### 4. Per-domain security rules (column exclusion)

Cisco hard-codes per-domain rules: for the HR domain, certain columns (SSN, compensation) are *excluded from any generated SQL*. The rules live outside the prompt — the orchestrator strips forbidden columns from the response or rejects the SQL.

**Our situation:** our `SchemaAnnotation.tags_json` can carry `["pii", "sensitive"]` but the plan does not yet act on those tags. Today they're informational.

**Recommendation — Absorb as a lightweight guard.** In Pillar 9 (static validation), after extracting referenced columns from the AST, reject the SQL if any referenced column has a `forbidden` tag for the current user/role. Fails closed; small code; large compliance win. Schedule alongside M4 (validation + repair).

### 5. Multi-database dialect routing

Cisco routes queries to Aurora / Oracle / Teradata based on which domain the question fell into. Each target has its own dialect, and the prompt preparation step picks the dialect guidance accordingly.

**Our situation:** we already support multiple dialects (`_DIALECT_GUIDANCE` in `backend/app/nl2sql/prompts.py`) but drive the dialect from the `NL2SQLRequest`, not from a connection registry.

**Recommendation — Already planned, just finish the wiring.** Our `SchemaConnection.dialect` field is exactly the routing primitive; M2 connects it. No new work.

### 6. Execute-to-validate (not dry-run)

Cisco runs the final SQL for real. They don't dry-run it.

**Our situation:** we wrap in `TOP 0` / a `WHERE 1=0` subquery precisely to avoid paying for full execution on possibly wrong queries.

**Recommendation — Keep our dry-run.** Cisco can afford full execution because the preamble pattern dramatically reduces wrong-query risk (the entity IDs are already correct). Our scope accepts that the LLM might generate a bad filter and hit a 10 M-row scan. `TOP 0` is the right default. Offer "full execute after validation" as a config flag for users who want the results inline.

---

## What We Do That Cisco Doesn't Describe

### 1. Explicit token-budget enforcement with priority tiers

Cisco's answer to token budget is "partition by domain so each prompt is small". Ours is mathematical: Pillar 6 measures assembled-prompt tokens, compares to budget, and drops pillars in priority order (value samples first, then examples, then glossary, then join-hint alternatives, never schema DDL or FK relationships).

**When our approach wins:** single-domain settings where you *want* all the context but have to cap it. Power-user mode where someone cranks up K for examples and needs predictable fallback behavior.

**When Cisco's wins:** multi-domain settings where domain scoping gives you both determinism and a natural budget ceiling for free.

### 2. BM25 retrieval over the curated example set

Cisco's writeup suggests each domain has its **own** static few-shot set — all of the domain's examples go into the prompt. Ours ranks examples per-question via BM25 and picks top-K, so the prompt always reflects the *most relevant* examples regardless of corpus size.

**Advantage:** we don't have to cap the example library at a size that fits in a prompt. The library can grow to hundreds of examples; retrieval keeps the prompt at K=5.

### 3. `sqlglot` static validation before any DB round-trip

Our Pillar 9 parses the generated SQL with `sqlglot`, extracts referenced tables and columns, and cross-checks against the live `SchemaCatalog`. Hallucinated identifiers are caught in milliseconds, without a network hop. The blog does not describe this layer — validation in their pipeline is by execution.

**Advantage:** cheap, fast, informative errors for the repair prompt ("you referenced `sales.customer` but the table is `sales.customers`"). Also the foundation for fuzzy-match "did you mean" suggestions.

### 4. Column value samples for low-cardinality enums

The blog emphasizes named-entity resolution (deterministic lookup) but does not describe enum sampling. Our Pillar 5 is complementary: for columns where `distinct_count <= 50`, we inline the actual values so the model doesn't write `status = 'pending'` when the DB stores `'NEW'`.

**Why keep it even if we adopt Cisco's entity resolution:** they solve different problems. Entity resolution handles identity columns ("which row?"). Value samples handle categorical filters ("which category?").

### 5. Structured observability + offline gold set

Our Pillar 10 persists per-pillar token accounting and runs a YAML-defined gold evaluation set after every milestone to verify accuracy is monotonically non-decreasing. The blog cites "95% across three domains" once but doesn't describe a regression harness.

**Advantage:** we can tell whether adding Pillar X helped or hurt, quantitatively. This is how we avoid shipping "improvements" that actually regress complex-query accuracy.

### 6. Explicit repair loop with `RepairAttempt` history

Cisco's pipeline diagram implies a retry on execution failure but does not describe it as a deliberate technique with observable history. Our `NL2SQLResponse.repair_history` makes the loop visible: which error triggered which retry, which fix landed.

---

## Where The Problem Shapes Differ

| Dimension                | Cisco / AWS                              | QueryLab                          |
|--------------------------|------------------------------------------|-----------------------------------|
| Schema size              | Thousands of tables, many domains        | ~30 tables, single domain (Contoso) |
| Target DB topology       | Multi-DB (Aurora, Oracle, Teradata)      | Single Azure SQL connection       |
| Dialect handling         | Per-domain dialect                       | Per-connection dialect            |
| User type                | Internal enterprise analysts             | Developers building/testing the tool |
| Deployment               | Serverless on AWS (Lambda + Bedrock)     | Self-hosted FastAPI + configurable LLM provider |
| Security surface         | Needs domain-level column-exclusion rules | Dev-oriented; tags exist, enforcement is future work |
| Entity cardinality       | Named entities are the common case (athletes, products, customers) | Enum filters are the common case; named-entity lookups are occasional |
| Query complexity driver  | Multi-DB joins + XML                     | Multi-table joins + business glossary terms |

These differences explain why Cisco invests in domain classification and preamble temp tables while we invest in BM25 retrieval, token-budget math, and static validation. **Neither plan is "better" — they're sized to their respective problems.**

---

## Suggested Additions to `SCHEMA_CONTEXT_PLAN.md`

Based on the comparison, here are the changes worth considering. Ordered by ratio of accuracy-lift to implementation cost.

1. **Column-exclusion enforcement** (Cisco-inspired). Add to Pillar 9: static validator rejects SQL that references any column tagged `forbidden` in `SchemaAnnotation`. Tiny code change, significant security posture improvement. Schedule: **M4**.
2. **Pillar 11 — Entity Resolution** (new). Fuzzy-match named entities in the question against columns marked `entity=True` in annotations; inject a `## Resolved Entities` block with candidate IDs. Schedule: **M7 or later**, after we see real user questions that need it.
3. **"Full execute after validation" opt-in** (Cisco-inspired ergonomics). Add `NL2SQL_EXECUTE_AFTER_VALIDATION_ENABLED` config flag in M4. Separate from `NL2SQL_DRY_RUN_ENABLED`. Defaults off; power-user feature.
4. **Two-stage table selection as a future flag** (Cisco domain classification, re-framed). Already in Future Extensions; upgrade it from a note to a flag contract: describe the exact signature so we can prototype when table count justifies it.
5. **Temporary abstraction views** (Cisco-inspired, fully deferred). Add one line to Future Extensions noting it as the canonical answer to JSON/XML columns when they arrive.

None of these changes displace M1–M7 scheduling. They augment M4 (items 1, 3), Future Extensions (items 4, 5), or land as a new stretch milestone (item 2).

---

## Open Questions for You

1. **Do you want to keep QueryLab as a single-domain tool for now, or plan for multi-domain from the start?** The answer determines whether "domain classification" is a Future Extension or an M3 concern.
2. **How soft is the accuracy target for complex queries?** If >95% is the bar, we probably need entity resolution (Pillar 11) as well as everything currently planned. If >85% is acceptable for MVP, Pillars 1–10 should clear it.
3. **Is full-execute (not just dry-run) acceptable for the dev workflow?** Cisco treats it as a feature. We've treated it as a risk. If the answer is "fine for dev, gated in prod" we can thread that config flag through M4.
4. **Security posture for column exclusion — is a `tags_json` check in the static validator enough, or do you want role-based policies from day one?** The former is M4-sized. The latter is a separate initiative that sits above the NL2SQL layer.

---

## Sources

- [Enterprise-grade natural language to SQL generation using LLMs (AWS ML Blog, Cisco × AWS)](https://aws.amazon.com/blogs/machine-learning/enterprise-grade-natural-language-to-sql-generation-using-llms-balancing-accuracy-latency-and-scale/)
- [Bridging Natural Language and Complex SQL in Multi-Database Environments (CloudThat)](https://www.cloudthat.com/resources/blog/bridging-natural-language-and-complex-sql-in-multi-database-environments) — the most detailed public write-up of the Cisco/AWS pipeline stages
- [text-to-sql-bedrock-workshop (aws-samples, GitHub)](https://github.com/aws-samples/text-to-sql-bedrock-workshop) — hands-on reference for related techniques (RAG over schema metadata, security hardening, fine-tuning Titan on Spider)
- [Generating value from enterprise data: best practices for Text2SQL (AWS ML Blog)](https://aws.amazon.com/blogs/machine-learning/generating-value-from-enterprise-data-best-practices-for-text2sql-and-generative-ai/) — the broader AWS point of view on the same problem class
- Companion document: [`SCHEMA_CONTEXT_PLAN.md`](./SCHEMA_CONTEXT_PLAN.md)
