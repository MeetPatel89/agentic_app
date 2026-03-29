# Backend Rules

These rules supplement the root `CLAUDE.md` with specific required and prohibited patterns for backend development.

## Architecture Boundaries

- Keep routing thin: validate input, call services/adapters, and shape HTTP responses.
- Keep provider-specific logic inside `backend/app/adapters/`.
- Keep database access and transaction orchestration in service/repository helpers, not in routers.
- Prefer extending existing modules before introducing new abstractions.

### Required Patterns

- Routers call services/adapters; they do not contain multi-step business workflows.
- Adapters return normalized response models, not provider-native payloads.
- New providers implement the existing `ProviderAdapter` contract and register through the adapter registry.
- Keep durable schema changes in Alembic migrations instead of relying on dev-only auto-create behavior.

### Prohibited Patterns

- No direct provider SDK calls from `backend/app/routers/`.
- No raw SQL or DB session orchestration in route handlers.
- No leaking provider-specific fields through API responses.
- No contract-breaking endpoint, schema, or event-shape changes without explicit approval.

## Async Performance

- Use `async def` for all request paths that perform I/O.
- Avoid blocking calls (`time.sleep`, sync HTTP clients, sync DB sessions) in async code.
- Use bounded concurrency for independent external I/O; avoid unbounded fan-out.
- Set explicit timeouts for provider/network operations.
- Use cancellation-safe cleanup for streaming and long-lived tasks.

### Required Patterns

- Prefer shared async clients/resources over per-request initialization.
- Use retries only for transient failures and bound retry count/backoff.
- Keep middleware non-blocking and minimal on hot request paths.

### Prohibited Patterns

- No synchronous SDK calls in adapters or routers.
- No silent fallback loops that mask latency spikes.
- No unbounded background tasks created from request handlers.

## API Contracts and SSE

- Use typed Pydantic request/response models for API boundaries.
- Keep API shapes backward compatible unless explicitly approved.
- Treat `backend/app/schemas.py` and frontend mirrored types as one contract.

### Required Patterns

- Return normalized response models from API routes.
- Map errors to consistent HTTP status codes and response envelopes.
- Validate inputs early and produce deterministic validation errors.
- Keep route-level transformations simple and explicit.

### Streaming Contract

- Emit `delta`, `meta`, `final`, and `error` events in expected sequence.
- Keep SSE payloads JSON-serializable and schema-stable.
- Ensure stream termination paths are explicit for both success and failure.
- Update frontend stream parsing and mirrored types in the same change when event payloads evolve.

## Database Efficiency

- Use `AsyncSession` from the project database layer for DB operations.
- Keep transactions scoped and explicit; commit/rollback intentionally.
- Default list endpoints to pagination with safe limits.
- Design query paths to avoid N+1 patterns.

### Required Patterns

- Select only fields needed for response models on hot paths.
- Keep read/write responsibilities clear and easy to test.
- Add or use indexed filters for frequent lookup paths.
- Handle idempotency for retried write operations when applicable.

### Prohibited Patterns

- No unbounded table scans for user-facing list APIs.
- No DB access from middleware unless strictly necessary.
- No DB transaction control in router handlers when a service/repository can own it.

## Observability and Reliability

- Use structured logs with request or trace identifiers.
- Measure latency for DB calls and external provider calls.
- Surface actionable errors; avoid swallowing exceptions.
- Keep request-logging middleware lightweight and non-blocking.

### Required Patterns

- Ensure retries, timeouts, and fallback behavior are explicit in code.
- Propagate cancellation and timeout context to downstream calls where possible.
- Fail predictably with stable error contracts.
- Add enough diagnostic context to make provider and DB failures debuggable.

### Prohibited Patterns

- No bare `except` blocks that hide root cause.
- No noisy per-token logging on hot streaming loops.
- No silent retries or fallback paths that hide latency spikes or degraded behavior.

## Security and Configuration

- Never hardcode credentials, API keys, or secrets.
- Use environment-driven config and existing project settings patterns.
- Validate and sanitize all user-provided inputs.
- Minimize sensitive data retention in logs, errors, and persisted run records.

### Required Patterns

- Prefer least-privilege defaults for new integrations.
- For new endpoints, consider auth, CORS, and rate-limit implications.
- Redact secret-like fields before logging or telemetry emission.
- Keep security checks in server-side code, not only frontend controls.
- Follow the existing `pydantic-settings` configuration pattern before introducing new config loaders.

### Prohibited Patterns

- No committing `.env` values or sample real tokens.
- No verbose exception output to clients in production paths.
- No trusting provider/webhook payloads without validation.
- No logging of secrets, tokens, connection strings, or full private payloads.

## Testing Gates

- Any behavior change requires test updates in the same change set.
- Cover happy path, validation failure, timeout/failure, and edge cases.
- For streaming features, test event ordering and stream completion behavior.
- For contract changes, add backward-compatibility assertions or explicit migration notes.

### Performance-Sensitive Paths

- Add focused checks for hot paths where latency or throughput can regress.
- Prefer deterministic tests (mock provider/network boundaries).
- Avoid flaky timing-based assertions without tolerance windows.
- Mirror backend schema or SSE changes in frontend contract checks when applicable.

### Prohibited Patterns

- No merging endpoint or adapter behavior changes without tests.
- No deleting failing tests to make a change pass.
- No silently changing API or SSE event shapes without test updates.

## Package Management

Use `uv` exclusively — never `pip`, `pip-tools`, or `poetry`.

```bash
uv add <package>        # Add or upgrade dependencies
uv remove <package>     # Remove dependencies
uv sync                 # Reinstall all from lock file
uv run script.py        # Run script with proper dependencies
```

For inline script metadata:

```bash
uv add package-name --script script.py    # Add script dependency
uv remove package-name --script script.py # Remove script dependency
uv sync --script script.py                # Sync script dependencies
```
