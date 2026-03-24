# Request Flow: Submitting Questions to an LLM

This document traces the complete lifecycle of a user submitting a question through the Playground UI, receiving a streamed response, and then submitting a follow-up question in the same conversation.

---

## Overview

```
Browser (React, :5173)
  │
  │  fetch POST /api/chat/turn/stream
  │
  ▼
Vite Dev Proxy (:5173 → :8000)
  │
  ▼
FastAPI (:8000)
  │
  ├─ RequestLoggingMiddleware  (assigns request_id, logs timing)
  ├─ CORSMiddleware
  │
  ▼
Router: POST /api/chat/turn/stream
  │
  ├─ ConversationService  (creates conversation, persists messages, builds ChatRequest)
  ├─ AdapterRegistry       (resolves provider adapter)
  │
  ▼
ProviderAdapter.stream_chat()  (e.g. OpenAIAdapter)
  │
  │  SSE: event: meta  → event: delta (×N) → event: final
  │
  ▼
Browser: useStream hook parses SSE → updates React state → renders tokens
```

---

## First Question: Step by Step

### 1. User Types and Clicks Send

In `Playground.tsx`, the user fills in a message and presses Send (or Enter). The `handleSend` callback fires.

**What happens immediately in React state:**

```
messages: [ ...prev, { role: "user", content: text }, { role: "assistant", content: "" } ]
userInput: ""
lastResponse: null
syncError: null
```

The empty assistant message is a placeholder — the `ChatMessageList` component will render streaming text into it while data arrives.

### 2. Building the Turn Request

`handleSend` constructs a `ConversationTurnRequest` object:

```ts
{
  conversation_id: undefined,        // null on first turn — tells backend to create a new conversation
  provider: "openai",
  model: "gpt-4o-mini",
  message: "What is the capital of France?",
  system_prompt: "You are a helpful assistant.",  // only sent on first turn
  temperature: 0.7,
  max_tokens: 1024,
  provider_options: {},
  tool_mode: "off",
}
```

Key detail: `system_prompt` is only included when `conversationId` is `null` (first turn). On subsequent turns it is `undefined` because the conversation already has its system prompt stored server-side.

### 3. Starting the Stream (Frontend)

Since `toolMode` is `"off"`, the code takes the streaming path:

```ts
stream.startTurnStream(turnReq);
```

Inside `useStream.ts`, `startTurnStream` calls `runStream("/api/chat/turn/stream", turnReq)`, which:

1. **Aborts** any previous in-flight stream (via `AbortController`).
2. **Resets** state: `streamingText = ""`, `error = null`, `finalResponse = null`, `isStreaming = true`.
3. **Opens a `fetch` POST** to `/api/chat/turn/stream` with `Content-Type: application/json` and the request body.

### 4. Vite Proxy

The browser is on `localhost:5173`. The Vite dev server sees the `/api` prefix and proxies the request to `http://localhost:8000/api/chat/turn/stream` (configured in `vite.config.ts`). In production, a reverse proxy (nginx, etc.) does this instead.

### 5. FastAPI Middleware Layer

The request hits FastAPI on port 8000 and passes through two middleware layers in order:

1. **`RequestLoggingMiddleware`** — Generates a short `request_id` (8-char UUID prefix), attaches it to `request.state`, logs `[abc12345] POST /api/chat/turn/stream`, and starts a timer. When the response completes, logs the status code and elapsed milliseconds. Adds `X-Request-ID` header to the response.

2. **`CORSMiddleware`** — Validates the `Origin` header against the configured `CORS_ORIGINS` list (default: `["http://localhost:5173"]`). Adds `Access-Control-Allow-*` headers.

### 6. Router: `chat_turn_stream` Endpoint

`POST /api/chat/turn/stream` is handled by `chat.py:chat_turn_stream()`. FastAPI's dependency injection provides an `AsyncSession` via `get_db()`.

#### 6a. `_prepare_turn()` — Shared Setup

This function runs first and does all the pre-LLM work:

**Create the Conversation (first turn only):**

Since `req.conversation_id` is `None`, the `ConversationService` creates a new `Conversation` row in SQLite:

```python
conv = Conversation(
    provider="openai",
    model="gpt-4o-mini",
    system_prompt="You are a helpful assistant.",
    title=None,
)
db.add(conv)
await db.flush()  # generates the UUID primary key
```

The `Conversation` model fields:
- `id` — UUID v4 (auto-generated)
- `created_at` / `updated_at` — UTC timestamps
- `provider`, `model`, `system_prompt` — conversation-level settings
- `config_json` — extensibility hook (unused currently)

**Build the `ChatRequest`:**

`ConversationService.build_chat_request()` assembles the full messages array that will be sent to the LLM provider:

```python
messages = []

# 1. If memory store is configured, prepend retrieved memories (Approach 3 hook — currently off)

# 2. System prompt → first message
messages.append(Message(role="system", content="You are a helpful assistant."))

# 3. Load conversation history from DB (ordered by ordinal)
#    On the first turn: history is EMPTY (no messages persisted yet)
history = await self.get_messages(db, conversation.id)
history = self._apply_sliding_window(history, window_size=50)
for msg in history:
    messages.append(Message(role=msg.role, content=msg.content))

# 4. Append the new user message
messages.append(Message(role="user", content="What is the capital of France?"))
```

Result for the first turn:
```
[
  { role: "system", content: "You are a helpful assistant." },
  { role: "user",   content: "What is the capital of France?" }
]
```

These are wrapped into a `ChatRequest` Pydantic model with `provider`, `model`, `temperature`, `max_tokens`, etc.

**Persist the user message:**

```python
await svc.append_message(db, conversation_id=conv.id, role="user", content=req.message)
```

This creates a `ConversationMessage` row with `ordinal=0`. The ordinal is computed as `MAX(ordinal) + 1` for the conversation.

**Resolve tools:**

Since `tool_mode` is `"off"`, no tool definitions are attached to the `ChatRequest`.

**Get the adapter:**

```python
adapter = get_adapter("openai")  # looks up the registry dict
```

The adapter registry was populated at app startup (`lifespan` → `init_registry()`). Each adapter class is instantiated and checked via `is_available()` (which verifies the API key env var exists). Only available adapters are registered.

**Create trace context:**

```python
trace = new_trace()  # TraceContext(trace_id=<new UUID>, parent_run_id=None)
parent_run_id = await svc.get_last_run_id(db, conv.id)  # None on first turn
```

### 7. Streaming from the LLM Provider

Back in `chat_turn_stream`, the endpoint returns a `StreamingResponse` wrapping an `event_generator()` async generator.

**Inside `event_generator()`:**

```python
async for event in adapter.stream_chat(chat_req):
    ...
```

**Inside `OpenAIAdapter.stream_chat()`:**

1. Gets (or lazily creates) the `AsyncOpenAI` client.
2. Calls `client.chat.completions.create(model=..., messages=..., stream=True, stream_options={"include_usage": True}, ...)`.
3. Yields events:

```
StreamMeta(provider="openai", model="gpt-4o-mini")        ← first yield
StreamDelta(text="The")                                     ← per-chunk
StreamDelta(text=" capital")
StreamDelta(text=" of")
StreamDelta(text=" France")
StreamDelta(text=" is")
StreamDelta(text=" Paris")
StreamDelta(text=".")
StreamFinal(response=NormalizedChatResponse(...))           ← after stream ends
```

The `NormalizedChatResponse` in the final event includes:
- `output_text`: full concatenated text
- `finish_reason`: `"stop"`
- `provider_response_id`: OpenAI's response ID
- `usage`: `{ prompt_tokens, completion_tokens, total_tokens }`

**The router's `event_generator` reformats these as SSE:**

```
event: meta
data: {"type":"meta","provider":"openai","model":"gpt-4o-mini"}

event: delta
data: {"type":"delta","text":"The"}

event: delta
data: {"type":"delta","text":" capital"}

...

event: final
data: {"type":"final","response":{...},"conversation_id":"<conv-uuid>"}
```

Note: For the turn-based endpoint, the `conversation_id` is injected into the `StreamFinal` event so the frontend can track it.

### 8. SSE Parsing in the Browser

Back in `useStream.ts`, the `fetch` response body is read as a `ReadableStream`:

```ts
const reader = res.body.getReader();
const decoder = new TextDecoder();
```

The stream is read chunk by chunk. Each chunk is decoded and split on newlines. The parser looks for `event: <type>` / `data: <json>` pairs:

- **`delta` events**: The text is appended to `textBufferRef.current`. A `requestAnimationFrame` is scheduled to batch DOM updates — this prevents excessive re-renders when tokens arrive faster than 60fps.
- **`final` event**: Sets `finalResponse` (the full `NormalizedChatResponse`) and `conversationId` in React state.
- **`error` event**: Sets the error message.

When the stream ends (`reader.read()` returns `done: true`), `isStreaming` is set to `false`.

### 9. React State Updates After Stream Completes

Two `useEffect` hooks in `Playground.tsx` fire:

**Capture `conversation_id`:**
```ts
useEffect(() => {
  if (stream.conversationId && !conversationId) {
    setConversationId(stream.conversationId);  // saved for subsequent turns
  }
}, [stream.conversationId, conversationId]);
```

**Finalize the assistant message:**
```ts
useEffect(() => {
  if (!stream.isStreaming && stream.finalResponse && stream.streamingText) {
    setMessages(prev => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && last.content === "") {
        // Replace the empty placeholder with the final text
        return [...prev.slice(0, -1), { role: "assistant", content: stream.finalResponse.output_text }];
      }
      return prev;
    });
    setLastResponse(stream.finalResponse);
  }
}, [stream.isStreaming, stream.finalResponse, stream.streamingText]);
```

At this point the `messages` state is:
```
[
  { role: "user",      content: "What is the capital of France?" },
  { role: "assistant", content: "The capital of France is Paris." }
]
```

And `conversationId` is now set to the UUID returned by the backend.

### 10. Backend Persistence (in `finally` block)

After the stream completes (whether successfully or with an error), the `event_generator`'s `finally` block runs:

1. **Persist the Run:**
```python
run = await _persist_run(
    db, chat_req, final_response, error_msg, latency,
    trace_id=trace.trace_id,
    parent_run_id=parent_run_id,
    conversation_id=conv.id,
)
```
This creates a `Run` row with: full request JSON, normalized response JSON, raw response JSON, latency, token counts, status (`"success"` or `"error"`), trace/parent linkage, and conversation FK.

2. **Persist the assistant message:**
```python
await svc.append_message(
    db, conversation_id=conv.id, role="assistant",
    content=final_response.output_text, run_id=run.id,
)
```
This creates a `ConversationMessage` row with `ordinal=1`, linked to the `Run` via `run_id`.

3. **Commit the transaction.**

**Database state after the first turn:**

| Table | Rows |
|---|---|
| `conversations` | 1 row (id, provider, model, system_prompt) |
| `conversation_messages` | 2 rows: user (ordinal=0), assistant (ordinal=1) |
| `runs` | 1 row (linked to conversation, trace_id set) |

---

## Second Question: What Changes

The user types a follow-up: *"What about Germany?"* and clicks Send.

### 11. Frontend Differences on Turn 2

`handleSend` builds the request, but now `conversationId` is set:

```ts
{
  conversation_id: "abc-123-...",    // ← existing conversation UUID
  provider: "openai",
  model: "gpt-4o-mini",
  message: "What about Germany?",
  system_prompt: undefined,           // ← NOT sent on subsequent turns
  temperature: 0.7,
  max_tokens: 1024,
  provider_options: {},
  tool_mode: "off",
}
```

The `messages` state is updated optimistically:
```
[
  { role: "user",      content: "What is the capital of France?" },
  { role: "assistant", content: "The capital of France is Paris." },
  { role: "user",      content: "What about Germany?" },          ← new
  { role: "assistant", content: "" },                              ← placeholder
]
```

### 12. Backend: `_prepare_turn` on Turn 2

**Load existing conversation:**

Since `req.conversation_id` is provided, the service loads the existing `Conversation` from the database (with eager-loaded messages):

```python
conv = await svc.get_conversation(db, req.conversation_id)
# conv.messages → [user(ordinal=0), assistant(ordinal=1)]
# conv.system_prompt → "You are a helpful assistant."
```

**Build the `ChatRequest` with history:**

`build_chat_request` now includes the full conversation history:

```python
messages = []

# 1. System prompt (from stored conversation, not from the request)
messages.append(Message(role="system", content="You are a helpful assistant."))

# 2. Conversation history from DB (2 messages already stored)
#    Sliding window of 50 — both messages fit easily
messages.append(Message(role="user",      content="What is the capital of France?"))
messages.append(Message(role="assistant", content="The capital of France is Paris."))

# 3. New user message
messages.append(Message(role="user", content="What about Germany?"))
```

So the `ChatRequest.messages` sent to the LLM is:
```
[
  { role: "system",    content: "You are a helpful assistant." },
  { role: "user",      content: "What is the capital of France?" },
  { role: "assistant", content: "The capital of France is Paris." },
  { role: "user",      content: "What about Germany?" }
]
```

This is how the LLM gets conversational context — the full history is replayed every turn (up to the sliding window limit of 50 messages).

**Persist the new user message:**

```python
await svc.append_message(db, conversation_id=conv.id, role="user", content="What about Germany?")
# Creates ConversationMessage with ordinal=2
```

**Trace and parent linking:**

```python
trace = new_trace()  # NEW trace_id for this turn
parent_run_id = await svc.get_last_run_id(db, conv.id)
# → returns the run_id from the first turn's assistant message
```

### 13. LLM Call and Streaming (Same as Turn 1)

The adapter calls OpenAI with the 4-message array. The LLM sees the full conversation and responds in context: *"The capital of Germany is Berlin."*

SSE events flow back through the same pipeline: `adapter.stream_chat()` → router `event_generator()` → HTTP response → Vite proxy → browser `useStream` → React state.

### 14. Final Persistence for Turn 2

The `finally` block persists:

1. A new `Run` row (with `parent_run_id` pointing to Turn 1's run, and a new `trace_id`).
2. A new `ConversationMessage` row for the assistant response (ordinal=3, linked to the new Run).
3. Commits.

**Database state after the second turn:**

| Table | Rows |
|---|---|
| `conversations` | 1 row (unchanged) |
| `conversation_messages` | 4 rows: user(0), assistant(1), user(2), assistant(3) |
| `runs` | 2 rows (turn 2's run has `parent_run_id` → turn 1's run) |

---

## Key Design Details

### Conversation State Lives Server-Side
The frontend only holds `conversationId` (a UUID string). All history reconstruction happens in `ConversationService.build_chat_request()` by querying the `conversation_messages` table. The frontend's `messages` array is purely for display.

### Sliding Window
`build_chat_request` applies a sliding window (default 50 messages) to cap context length. If a conversation exceeds 50 messages, only the most recent 50 are sent to the LLM. The system prompt is always prepended outside the window.

### Streaming vs Non-Streaming (Tool Mode)
When tools are enabled (`tool_mode: "auto"` or `"manual"`), the frontend falls back to a synchronous `POST /api/chat/turn` call (non-streaming), because tool execution requires a request-response loop (LLM → tool call → tool result → LLM) that doesn't map to a single SSE stream. The response arrives all at once.

### Run Tracing
Each turn generates a new `TraceContext` with a unique `trace_id`. The `parent_run_id` chains runs within a conversation so you can reconstruct the sequence. This is the foundation for multi-step agentic traces (e.g., LLM call → tool call → sub-LLM call).

### SSE Batching with `requestAnimationFrame`
The `useStream` hook batches delta text updates using `requestAnimationFrame`. Incoming tokens are appended to a mutable ref (`textBufferRef`), and a single state update is scheduled per animation frame. This prevents React from re-rendering on every single token arrival, which would be wasteful at high token rates.

### Error Handling
- **Adapter errors** are caught and yield a `StreamError` SSE event, so the stream closes gracefully.
- **Persistence errors** in the `finally` block are logged but don't propagate — the user still sees their response even if the run failed to save.
- **Network errors** on the frontend are caught by the `useStream` try/catch and surfaced via `stream.error`.
