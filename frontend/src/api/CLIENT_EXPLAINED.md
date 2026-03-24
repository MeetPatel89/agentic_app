# API Client (`client.ts`) — Detailed Explanation

## Overview

`client.ts` is the frontend's single point of contact with the backend. Every HTTP call the UI makes — health checks, chat requests, run history, conversations — goes through the `api` object exported from this file. It wraps the browser `fetch` API with TypeScript generics, consistent error handling, and JSON serialization so that calling code never deals with raw HTTP plumbing.

---

## The `request<T>` Helper (lines 17–27)

```ts
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}
```

This is the core of the module — a generic async function that every endpoint method delegates to.

### How it works, step by step

1. **URL construction** — `BASE` is `""` (empty string), so paths like `"/api/chat"` resolve relative to the current origin. In dev, Vite's proxy (`vite.config.ts`) forwards `/api/*` and `/health` to the backend at `localhost:8000`. In production, both frontend and backend live behind the same origin, so no proxy is needed.

2. **Default headers** — Every request gets `Content-Type: application/json`. The spread `...init` lets callers override or add headers (e.g. a future auth token), and also supply `method`, `body`, `signal`, etc.

3. **Error handling** — If the response status is not 2xx (`!res.ok`):
   - It tries to parse the body as JSON to extract a `detail` field (FastAPI's default error shape).
   - If parsing fails (e.g. a 502 HTML page), it falls back to `res.statusText` (e.g. `"Bad Gateway"`).
   - Either way, it throws an `Error` with a human-readable message. Callers catch this in `.catch()` or `try/catch`.

4. **Return type** — The response body is parsed as JSON and cast to `T`. This gives every call site full type safety — e.g. `request<HealthResponse>(...)` returns `Promise<HealthResponse>`.

### Why a single helper matters

- **Consistency** — All requests get the same headers, error handling, and JSON parsing. No endpoint can accidentally skip error checking.
- **Single point of change** — If you later need to add an auth header, a retry policy, or request logging, you change one function.
- **Type safety** — The generic `<T>` parameter means every response is typed at the call site. The compiler catches mismatches between what the backend returns and what the frontend expects.

---

## The `api` Object (lines 29–73)

The exported `api` object groups every backend endpoint into a flat namespace. Each method is a thin one-liner that calls `request<T>` with the right path, HTTP method, and body.

### Health & Discovery

```ts
health: () => request<HealthResponse>("/health")
```
- **GET `/health`** — Returns `{ status, available_providers }`. Called once on page load to discover which LLM providers have valid API keys configured.

```ts
listTools: () => request<ToolListResponse>("/api/tools")
```
- **GET `/api/tools`** — Returns `{ tools: ToolDefinition[] }`. Fetches the list of server-side tool definitions (name, description, JSON schema) so the Playground UI can show tool toggles.

```ts
listModels: (provider: string) =>
  request<ProviderModelsResponse>(`/api/providers/${encodeURIComponent(provider)}/models`)
```
- **GET `/api/providers/:provider/models`** — Returns `{ provider, models: string[] }`. Called whenever the user switches providers in the Playground dropdown. `encodeURIComponent` protects against special characters in provider names.

### Chat

```ts
chat: (req: ChatRequest) =>
  request<ChatApiResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify(req),
  })
```
- **POST `/api/chat`** — Legacy single-shot (non-streaming) chat. Sends a full message array and returns the complete response in one round trip. Returns `{ run_id, response: NormalizedChatResponse, latency_ms }`.

```ts
chatTurn: (req: ConversationTurnRequest) =>
  request<TurnResponse>("/api/chat/turn", {
    method: "POST",
    body: JSON.stringify(req),
  })
```
- **POST `/api/chat/turn`** — Turn-based conversation endpoint. Sends a single user message (plus optional `conversation_id` to continue an existing conversation). The backend appends the message to conversation history, calls the LLM, and returns `{ conversation_id, run_id, response, latency_ms }`. Used as the **non-streaming fallback** when tools are enabled (tool execution requires seeing the full response before deciding next steps).

> **Note:** Streaming is NOT handled by `client.ts`. The `useStream` hook (`hooks/useStream.ts`) opens its own `fetch` to `/api/chat/turn/stream` and processes Server-Sent Events directly. This is because streaming responses are fundamentally different — they arrive as a sequence of SSE chunks, not a single JSON body.

### Runs (Execution History)

Every chat request — streaming or not — is recorded as a "Run" in the backend's SQLite database.

```ts
listRuns: (page = 1, perPage = 20) =>
  request<PaginatedRuns>(`/api/runs?page=${page}&per_page=${perPage}`)
```
- **GET `/api/runs?page=&per_page=`** — Paginated list of run summaries (id, provider, model, status, latency, tokens). Default: page 1, 20 items per page. Used by the History page's "Runs" tab.

```ts
getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`)
```
- **GET `/api/runs/:id`** — Full run detail including request JSON, raw response JSON, and normalized response JSON. Used by the Run Detail page for inspection and JSON export.

```ts
deleteRun: (id: string) =>
  request<{ deleted: string }>(`/api/runs/${id}`, { method: "DELETE" })
```
- **DELETE `/api/runs/:id`** — Deletes a single run. Returns `{ deleted: "<id>" }`.

### Conversations

Conversations group multiple turns (user + assistant message pairs) under a single ID with shared context.

```ts
listConversations: (page = 1, perPage = 20) =>
  request<PaginatedConversations>(`/api/conversations?page=${page}&per_page=${perPage}`)
```
- **GET `/api/conversations?page=&per_page=`** — Paginated list of conversation summaries (title, provider, model, message count, timestamps). Used by the History page's "Conversations" tab.

```ts
getConversation: (id: string) =>
  request<ConversationDetail>(`/api/conversations/${id}`)
```
- **GET `/api/conversations/:id`** — Full conversation detail including all messages and the system prompt. Used when resuming a conversation from History (the "Continue" button loads the conversation into the Playground).

```ts
deleteConversation: (id: string) =>
  request<{ deleted: string }>(`/api/conversations/${id}`, { method: "DELETE" })
```
- **DELETE `/api/conversations/:id`** — Deletes a conversation and all its messages.

```ts
updateConversation: (id: string, body: { title?: string }) =>
  request<{ id: string; title: string }>(`/api/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
```
- **PATCH `/api/conversations/:id`** — Partial update. Currently only supports renaming (setting `title`).

---

## Data Flow Diagram

```
Playground.tsx / History.tsx / RunDetail.tsx
        │
        ▼
   api.someMethod()          ←── typed call
        │
        ▼
   request<T>(path, init)    ←── adds headers, handles errors
        │
        ▼
   fetch(url, options)       ←── browser Fetch API
        │
        ▼
   Vite proxy (dev only)     ←── /api/* → localhost:8000
        │
        ▼
   FastAPI backend           ←── routers/chat.py, runs.py, etc.
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| `BASE = ""` (empty) | Relies on Vite's dev proxy and same-origin deployment. No hardcoded backend URL to manage across environments. |
| Single generic `request<T>` | One place for headers, error handling, and JSON parsing. Every endpoint is a one-liner. |
| Errors throw `Error` with `detail` | Matches FastAPI's `HTTPException(detail=...)` convention. Callers just catch and display `err.message`. |
| Streaming lives elsewhere | SSE responses can't use the JSON request/response pattern. `useStream.ts` handles its own `fetch` + `ReadableStream` loop for `/api/chat/turn/stream`. |
| `encodeURIComponent` on provider | Defensive URL encoding. Prevents breakage if a provider name ever contains `/`, `?`, `#`, etc. |
| Pagination defaults (page=1, perPage=20) | Matches backend defaults. Callers can omit params for the common case. |
