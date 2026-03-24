# How Tools Work in This Project

This guide explains the tool-calling system end to end: what tools are, how the backend registers and executes them, how the LLM decides to call them, and how the frontend UI controls it all. It finishes with step-by-step instructions for testing every path, both in the browser and with raw API requests.

---

## Table of Contents

1. [The Big Picture](#1-the-big-picture)
2. [What Is a "Tool" in the Context of LLMs?](#2-what-is-a-tool-in-the-context-of-llms)
3. [Backend Architecture](#3-backend-architecture)
   - [Tool Definition and the Tool ABC](#31-tool-definition-and-the-tool-abc)
   - [The Five Built-In Tools](#32-the-five-built-in-tools)
   - [The Tool Registry](#33-the-tool-registry)
   - [How Tools Get Registered at Startup](#34-how-tools-get-registered-at-startup)
   - [Tool Mode and the `_prepare_turn` Function](#35-tool-mode-and-the-_prepare_turn-function)
   - [The Agentic Loop (ToolExecutor)](#36-the-agentic-loop-toolexecutor)
   - [How the OpenAI Adapter Sends Tools to the LLM](#37-how-the-openai-adapter-sends-tools-to-the-llm)
   - [The Tool Discovery Endpoint](#38-the-tool-discovery-endpoint)
4. [Frontend Architecture](#4-frontend-architecture)
   - [Tool Mode Selector UI](#41-tool-mode-selector-ui)
   - [How the Frontend Builds the Request](#42-how-the-frontend-builds-the-request)
   - [Streaming vs Non-Streaming Path](#43-streaming-vs-non-streaming-path)
5. [The Full Request Lifecycle (Step by Step)](#5-the-full-request-lifecycle-step-by-step)
6. [Testing via the UI](#6-testing-via-the-ui)
   - [Prerequisites](#61-prerequisites)
   - [Test 1: Tool Mode "Off" (Default)](#62-test-1-tool-mode-off-default)
   - [Test 2: Tool Mode "Auto"](#63-test-2-tool-mode-auto)
   - [Test 3: Tool Mode "Manual"](#64-test-3-tool-mode-manual)
   - [Test 4: Verify Streaming Still Works with Tools Off](#65-test-4-verify-streaming-still-works-with-tools-off)
7. [Testing via API Requests (curl)](#7-testing-via-api-requests-curl)
   - [Discover Available Tools](#71-discover-available-tools)
   - [Send a Turn with `tool_mode: "auto"`](#72-send-a-turn-with-tool_mode-auto)
   - [Send a Turn with `tool_mode: "manual"`](#73-send-a-turn-with-tool_mode-manual)
   - [Send a Turn with `tool_mode: "off"` (Default)](#74-send-a-turn-with-tool_mode-off-default)
   - [Verify Streaming + Tools Returns 400](#75-verify-streaming--tools-returns-400)
   - [Backward Compatibility (No `tool_mode` Field)](#76-backward-compatibility-no-tool_mode-field)
   - [Continue a Conversation with Tools](#77-continue-a-conversation-with-tools)
   - [Use the Legacy `/api/chat` Endpoint with Tools](#78-use-the-legacy-apichat-endpoint-with-tools)
8. [Running the Automated Tests](#8-running-the-automated-tests)
9. [Schemas Reference](#9-schemas-reference)
10. [How to Add a New Tool](#10-how-to-add-a-new-tool)

---

## 1. The Big Picture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React)                               │
│                                                                         │
│  User types "What time is it?" with Tool Mode = Auto                    │
│       │                                                                 │
│       ▼                                                                 │
│  Playground.tsx builds ConversationTurnRequest:                         │
│    { message: "What time is it?", tool_mode: "auto", ... }             │
│       │                                                                 │
│       ▼                                                                 │
│  POST /api/chat/turn  (non-streaming, because tools are active)         │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       BACKEND (FastAPI)                                  │
│                                                                         │
│  chat.py::_prepare_turn()                                               │
│    1. Creates/loads conversation                                        │
│    2. Sees tool_mode="auto" → calls tool_registry.list_request_schemas()│
│    3. Injects 5 tool definitions + tool_choice="auto" into ChatRequest  │
│       │                                                                 │
│       ▼                                                                 │
│  chat.py::chat_turn()                                                   │
│    Sees chat_req.tools is not None → creates ToolExecutor               │
│       │                                                                 │
│       ▼                                                                 │
│  ToolExecutor.execute_with_tools()  [THE AGENTIC LOOP]                  │
│    ┌───────────────────────────────────────────────────────┐            │
│    │ Iteration 1:                                          │            │
│    │   Send messages + 5 tool defs to OpenAI API           │            │
│    │   OpenAI responds: "I'll call get_current_time()"     │            │
│    │     → finish_reason = "tool_calls"                    │            │
│    │   Execute get_current_time → "2026-03-14T15:30:00+00" │            │
│    │   Append assistant msg + tool result to messages       │            │
│    │                                                       │            │
│    │ Iteration 2:                                          │            │
│    │   Send updated messages to OpenAI API                 │            │
│    │   OpenAI responds: "The current time is 3:30 PM UTC"  │            │
│    │     → finish_reason = "stop"                          │            │
│    │   Loop exits                                          │            │
│    └───────────────────────────────────────────────────────┘            │
│       │                                                                 │
│       ▼                                                                 │
│  Returns TurnResponse { response: { output_text: "The time is..." } }   │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND displays: "The current time is 3:30 PM UTC"                   │
└─────────────────────────────────────────────────────────────────────────┘
```

The key insight: **the LLM doesn't run tools itself**. The LLM only *requests* that a tool be called by returning a structured `tool_calls` array. Our backend then *actually executes* the tool, feeds the result back, and lets the LLM write a human-readable response incorporating that result.

---

## 2. What Is a "Tool" in the Context of LLMs?

When you send a chat request to an LLM like GPT-4o, you can optionally include a list of **tool definitions**. Each definition tells the LLM:

- The tool's **name** (e.g., `get_current_time`)
- A **description** of what it does (e.g., "Returns the current date and time in ISO 8601 format")
- A **parameters JSON Schema** describing what arguments the tool accepts

The LLM reads these definitions and, if it decides a tool would help answer the user's question, it responds not with text but with a **tool call request** — a structured JSON object saying "please call tool X with arguments Y."

The LLM itself **cannot** execute the tool. It is the backend's responsibility to:
1. See the tool call request in the LLM's response
2. Actually run the tool's code
3. Send the tool's output back to the LLM as a new message
4. Let the LLM generate its final text response using that output

This back-and-forth is called the **agentic tool-calling loop**.

### What `tool_choice` Means

When you set `tool_choice: "auto"` (which this project does whenever tools are injected), you're telling the LLM: "You may or may not call a tool — it's your decision." Other possible values:

- `"none"` — never call tools (even if they're defined)
- `"required"` — you must call at least one tool
- `{"type": "function", "function": {"name": "..."}}` — call this specific tool

This project always uses `"auto"`, which is the most natural behavior.

---

## 3. Backend Architecture

### 3.1 Tool Definition and the Tool ABC

**File:** `backend/app/agentic/tools.py`

Every tool is a Python class that extends the abstract base class `Tool`:

```python
class ToolDefinition(BaseModel):
    name: str                              # Unique identifier, e.g. "calculate"
    description: str                       # Human-readable, shown to the LLM
    parameters_schema: dict[str, Any]      # JSON Schema for the arguments

class Tool(ABC):
    definition: ToolDefinition             # Class-level attribute

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> str:
        """Run the tool and return a string result."""
        ...

    def as_request_schema(self) -> ToolDefinitionRequest:
        """Convert to the wire format sent to LLM providers (OpenAI format)."""
        return ToolDefinitionRequest(
            function=ToolFunctionDefinition(
                name=self.definition.name,
                description=self.definition.description,
                parameters=self.definition.parameters_schema,
            )
        )
```

There are two representations of a tool:

| Representation | Purpose | Shape |
|---|---|---|
| `ToolDefinition` | Internal use + the `GET /api/tools` discovery endpoint | `{ name, description, parameters_schema }` |
| `ToolDefinitionRequest` | Wire format sent to the LLM provider (OpenAI format) | `{ type: "function", function: { name, description, parameters } }` |

The `as_request_schema()` method converts between the two.

### 3.2 The Five Built-In Tools

**File:** `backend/app/agentic/tools.py`

| Tool Class | Name | Description | Parameters |
|---|---|---|---|
| `GetCurrentTimeTool` | `get_current_time` | Returns the current date and time in ISO 8601 format | None (empty object) |
| `CalculateTool` | `calculate` | Evaluates a math expression. Supports +, -, *, /, //, %, ** | `expression` (string, required) |
| `GenerateUuidTool` | `generate_uuid` | Generates a random UUID v4 | None (empty object) |
| `WordCountTool` | `word_count` | Counts words, characters, sentences, and lines in text | `text` (string, required) |
| `JsonFormatterTool` | `json_formatter` | Validates, pretty-prints, or minifies a JSON string | `json_string` (string, required), `mode` (enum: pretty/minify/validate, required) |

**How `CalculateTool` stays safe:** It doesn't use `eval()`. Instead, it parses the expression into a Python AST (Abstract Syntax Tree) and walks it manually, only allowing arithmetic operations (+, -, *, /, //, %, **). Function calls, imports, and variable access are all rejected.

### 3.3 The Tool Registry

**File:** `backend/app/agentic/tools.py`

The `ToolRegistry` is a simple in-memory dictionary that maps tool names to `Tool` instances:

```python
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.definition.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[ToolDefinition]:
        """Used by GET /api/tools endpoint."""
        return [t.definition for t in self._tools.values()]

    def list_request_schemas(self) -> list[ToolDefinitionRequest]:
        """Used when tool_mode='auto' to inject all tools into the LLM request."""
        return [t.as_request_schema() for t in self._tools.values()]
```

There is one **global singleton** at the bottom of the file:

```python
tool_registry = ToolRegistry()
```

This singleton is imported by the chat router and the tools router.

### 3.4 How Tools Get Registered at Startup

**File:** `backend/app/main.py`

During the application lifespan (startup), `register_default_tools()` is called:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... logging, DB setup, adapter registry ...
    register_default_tools()   # <-- registers all 5 tools into tool_registry
    yield
```

The function itself (in `tools.py`) simply does:

```python
def register_default_tools() -> None:
    tool_registry.register(GetCurrentTimeTool())
    tool_registry.register(CalculateTool())
    tool_registry.register(GenerateUuidTool())
    tool_registry.register(WordCountTool())
    tool_registry.register(JsonFormatterTool())
```

### 3.5 Tool Mode and the `_prepare_turn` Function

**File:** `backend/app/routers/chat.py`

The `ConversationTurnRequest` schema has a `tool_mode` field:

```python
class ConversationTurnRequest(BaseModel):
    # ... other fields ...
    tool_mode: Literal["off", "auto", "manual"] = "off"
    tool_names: list[str] | None = None
```

The three modes work as follows:

| Mode | Behavior | When to Use |
|---|---|---|
| `"off"` | No tools are sent to the LLM. This is the **default**. | Normal chat without tool capabilities |
| `"auto"` | **All** registered tools are injected into the request. The LLM decides whether to call any of them. | When you want the LLM to autonomously discover and use tools |
| `"manual"` | Only the tools named in `tool_names` are injected. | When you want fine-grained control over which tools the LLM can see |

The resolution happens in `_prepare_turn()` (lines 176-188 of `chat.py`):

```python
# Resolve tools based on tool_mode
tool_defs: list = []
if req.tool_mode == "auto":
    tool_defs = tool_registry.list_request_schemas()       # ALL tools
elif req.tool_mode == "manual" and req.tool_names:
    for name in req.tool_names:
        tool = tool_registry.get(name)
        if tool is None:
            raise HTTPException(status_code=400, detail=f"Unknown tool: '{name}'")
        tool_defs.append(tool.as_request_schema())

if tool_defs:
    chat_req = chat_req.model_copy(update={"tools": tool_defs, "tool_choice": "auto"})
```

Key points:
- `tool_mode: "off"` → `tool_defs` stays empty → no tools injected
- `tool_mode: "manual"` without `tool_names` → `tool_defs` stays empty → treated like "off"
- `tool_mode: "manual"` with unknown tool name → 400 error
- When tools are injected, `tool_choice` is always set to `"auto"`

### 3.6 The Agentic Loop (ToolExecutor)

**File:** `backend/app/services/tool_executor.py`

This is the core loop that makes tools actually work. Here's what happens step by step:

```
┌─────────────────────────────────────────────────────────┐
│                   ToolExecutor Loop                      │
│                                                         │
│  Input: ChatRequest with messages + tool definitions     │
│                                                         │
│  for i in range(max_iterations):    # default: 10       │
│    │                                                    │
│    ├─ Send current messages + tools to LLM adapter      │
│    │    adapter.chat(current_req) → response             │
│    │                                                    │
│    ├─ Accumulate token usage                            │
│    │                                                    │
│    ├─ Does response have tool_calls?                    │
│    │    │                                               │
│    │    ├─ NO → break (we have our final text answer)   │
│    │    │                                               │
│    │    └─ YES →                                        │
│    │        ├─ Append assistant message (with tool_calls)│
│    │        │  to the message list                      │
│    │        │                                           │
│    │        └─ For each tool_call:                      │
│    │            ├─ Look up tool in registry              │
│    │            ├─ Parse JSON arguments                  │
│    │            ├─ Call tool.execute(arguments)          │
│    │            ├─ Append tool result as a "tool" role   │
│    │            │  message to the message list           │
│    │            └─ (If tool not found or raises:         │
│    │                append error string instead)         │
│    │                                                    │
│    └─ Continue loop (re-send to LLM with tool results)  │
│                                                         │
│  Output: Final NormalizedChatResponse with text answer   │
│          and aggregated token usage                      │
└─────────────────────────────────────────────────────────┘
```

Here's the actual code (simplified for clarity):

```python
class ToolExecutor:
    def __init__(self, registry: ToolRegistry, max_iterations: int = 10):
        self._registry = registry
        self._max_iterations = max_iterations

    async def execute_with_tools(self, adapter, req):
        messages = list(req.messages)
        total_usage = UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0)

        for i in range(self._max_iterations):
            current_req = req.model_copy(update={"messages": messages})
            response = await adapter.chat(current_req)
            _accumulate_usage(total_usage, response.usage)

            if not response.tool_calls:
                break  # LLM gave a text answer, we're done

            # LLM wants to call tools
            messages.append(Message(
                role="assistant",
                content=response.output_text or None,
                tool_calls=response.tool_calls,
            ))

            for tc in response.tool_calls:
                result = await self._execute_single(tc.function.name, tc.function.arguments)
                messages.append(Message(
                    role="tool",
                    content=result,
                    tool_call_id=tc.id,
                ))

        response.usage = total_usage
        return response
```

**Important details:**
- The **max iteration limit** (default 10) prevents infinite loops if the LLM keeps calling tools forever
- **Token usage is accumulated** across all iterations, so you get the real total
- **Unknown tools** don't crash the loop — an error string is returned as the tool result, and the LLM can try again or give up gracefully
- **Tool exceptions** are caught and returned as error strings too
- The LLM can request **multiple tool calls in a single response** (parallel tool calling) — the executor handles all of them before re-calling the LLM

### 3.7 How the OpenAI Adapter Sends Tools to the LLM

**File:** `backend/app/adapters/openai_adapter.py`

The OpenAI adapter has a method `_build_tool_kwargs()` that adds tools to the API call:

```python
def _build_tool_kwargs(self, req: ChatRequest) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if req.tools:
        kwargs["tools"] = [t.model_dump() for t in req.tools]    # tool definitions
    if req.tool_choice:
        kwargs["tool_choice"] = req.tool_choice                   # "auto"
    return kwargs
```

These kwargs get unpacked into the OpenAI SDK call:

```python
resp = await client.chat.completions.create(
    model=req.model,
    messages=self._build_messages(req),
    max_completion_tokens=req.max_tokens,
    **self._build_sampling_kwargs(req),
    **self._build_tool_kwargs(req),     # <-- tools and tool_choice go here
    **req.provider_options,
)
```

When the LLM responds with tool calls, the adapter normalizes them:

```python
if choice.message.tool_calls:
    normalized_tool_calls = [
        ToolCall(
            id=tc.id,                                    # e.g. "call_abc123"
            type=tc.type,                                # "function"
            function=ToolCallFunction(
                name=tc.function.name,                   # e.g. "get_current_time"
                arguments=tc.function.arguments,          # e.g. "{}"
            ),
        )
        for tc in choice.message.tool_calls
    ]
```

The `finish_reason` will be `"tool_calls"` instead of `"stop"`, which is how the `ToolExecutor` knows the LLM wants to call tools rather than being done.

### 3.8 The Tool Discovery Endpoint

**File:** `backend/app/routers/tools.py`

A simple GET endpoint that returns all registered tools:

```python
@router.get("/tools")
async def list_tools() -> dict:
    return {
        "tools": [d.model_dump() for d in tool_registry.list_definitions()],
    }
```

The frontend calls this on page load to populate the tool list in the settings panel.

**Example response:**
```json
{
  "tools": [
    {
      "name": "get_current_time",
      "description": "Returns the current date and time in ISO 8601 format.",
      "parameters_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
      "name": "calculate",
      "description": "Evaluates a math expression. Supports +, -, *, /, //, %, **.",
      "parameters_schema": {
        "type": "object",
        "properties": {
          "expression": {
            "type": "string",
            "description": "A mathematical expression, e.g. '2 + 3 * 4'"
          }
        },
        "required": ["expression"]
      }
    }
    // ... 3 more tools
  ]
}
```

---

## 4. Frontend Architecture

### 4.1 Tool Mode Selector UI

**File:** `frontend/src/components/playground/SettingsPanel.tsx`

The settings panel shows a three-button segmented control when tools are available:

```
┌──────────┬──────────┬──────────┐
│   Off    │   Auto   │  Manual  │
└──────────┴──────────┴──────────┘
```

- **Off** (default): No tools are sent. Chat uses streaming for real-time token display.
- **Auto**: All 5 tools are made available to the LLM. An info message appears: "All tools available to LLM automatically (disables streaming)". The chat switches to non-streaming mode because tool calling requires the full agentic loop.
- **Manual**: The existing checkbox list appears, letting you pick individual tools.

### 4.2 How the Frontend Builds the Request

**File:** `frontend/src/pages/Playground.tsx`

When you click "Send", the `handleSend` callback builds a `ConversationTurnRequest`:

```typescript
const turnReq: ConversationTurnRequest = {
  conversation_id: conversationId ?? undefined,
  provider,
  model,
  message: text,
  system_prompt: conversationId ? undefined : systemPrompt || undefined,
  temperature: isReasoning ? null : temperature,
  max_tokens: maxTokens,
  provider_options: parsedProviderOpts(),
  tool_mode: toolMode,                                                        // "off" | "auto" | "manual"
  tool_names: toolMode === "manual" && enabledToolNames.length > 0
    ? enabledToolNames
    : undefined,                                                              // only sent in manual mode
};
```

### 4.3 Streaming vs Non-Streaming Path

The frontend decides which endpoint to call based on whether tools are active:

```typescript
const toolsActive = toolMode === "auto" || (toolMode === "manual" && enabledToolNames.length > 0);

if (toolsActive) {
  // Non-streaming: POST /api/chat/turn (returns full response at once)
  api.chatTurn(turnReq).then((res) => { /* update messages */ });
} else {
  // Streaming: POST /api/chat/turn/stream (SSE, tokens arrive one by one)
  stream.startTurnStream(turnReq);
}
```

**Why can't tools work with streaming?** The agentic loop requires multiple round-trips between the backend and the LLM (send request → get tool call → execute tool → send result → get response). Each round-trip is a separate API call to the LLM provider. The current architecture doesn't support streaming intermediate results from this multi-step process, so the backend blocks streaming when tools are active and returns a 400 error:

```python
if req.tool_mode == "auto" or (req.tool_mode == "manual" and req.tool_names):
    raise HTTPException(status_code=400, detail="Tool calling is not supported with streaming")
```

---

## 5. The Full Request Lifecycle (Step by Step)

Here's exactly what happens when you type "What time is it?" with tool mode set to "Auto":

### Step 1: Frontend

1. User types "What time is it?" and clicks Send
2. `handleSend()` builds `ConversationTurnRequest` with `tool_mode: "auto"`
3. Since `toolsActive` is `true`, the frontend calls `api.chatTurn(turnReq)` (not streaming)
4. This sends `POST /api/chat/turn` with the JSON body

### Step 2: Backend — `_prepare_turn()`

5. FastAPI deserializes the request into a `ConversationTurnRequest`
6. A new conversation is created (or existing one is loaded if `conversation_id` is provided)
7. The user message is appended to the conversation in the DB
8. A `ChatRequest` is built from the conversation history (system prompt + all messages so far)
9. `tool_mode == "auto"` → `tool_registry.list_request_schemas()` returns all 5 tool definitions
10. The `ChatRequest` is updated with `tools: [5 tool defs]` and `tool_choice: "auto"`
11. The provider adapter is looked up (e.g., `OpenAIAdapter`)

### Step 3: Backend — `chat_turn()`

12. `chat_req.tools` is not None, so `ToolExecutor` is created
13. `executor.execute_with_tools(adapter, chat_req)` is called

### Step 4: ToolExecutor — Iteration 1

14. The current messages + tool definitions are sent to OpenAI via `adapter.chat()`
15. OpenAI's API receives the request. It sees the tool definitions and the user asking about time.
16. OpenAI decides to call `get_current_time` and responds with:
    ```json
    {
      "finish_reason": "tool_calls",
      "message": {
        "tool_calls": [{
          "id": "call_abc123",
          "type": "function",
          "function": {
            "name": "get_current_time",
            "arguments": "{}"
          }
        }]
      }
    }
    ```
17. The adapter normalizes this into a `NormalizedChatResponse` with `tool_calls`
18. The executor sees `response.tool_calls` is not empty → continues the loop
19. The assistant message (with the tool call) is appended to the messages list
20. The executor looks up `get_current_time` in the registry, finds `GetCurrentTimeTool`
21. `GetCurrentTimeTool.execute({})` runs → returns `"2026-03-14T15:30:00+00:00"`
22. A tool-role message is appended: `{ role: "tool", content: "2026-03-14T15:30:00+00:00", tool_call_id: "call_abc123" }`

### Step 5: ToolExecutor — Iteration 2

23. The updated messages (now including the tool call and result) are sent to OpenAI again
24. OpenAI sees the tool result and writes a human-readable response:
    ```json
    {
      "finish_reason": "stop",
      "message": {
        "content": "The current time is March 14, 2026 at 3:30 PM UTC."
      }
    }
    ```
25. `response.tool_calls` is empty → the loop exits
26. Token usage from both iterations is summed up

### Step 6: Backend — Response

27. The response is persisted as a `Run` record in the database
28. The assistant message is appended to the conversation
29. A `TurnResponse` is returned to the frontend

### Step 7: Frontend — Display

30. The frontend receives the response and displays "The current time is March 14, 2026 at 3:30 PM UTC."
31. The metadata panel shows token usage, latency, etc.

---

## 6. Testing via the UI

### 6.1 Prerequisites

Start both servers:

```bash
# Terminal 1: Backend
cd backend
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Make sure you have at least one provider API key set in `backend/.env` (e.g., `OPENAI_API_KEY`).

Open http://localhost:5173 in your browser.

### 6.2 Test 1: Tool Mode "Off" (Default)

1. Open the Playground. The tool mode selector should show **Off** highlighted.
2. Select a provider (e.g., OpenAI) and model (e.g., gpt-4o-mini).
3. Type: **"What time is it?"**
4. Click Send.

**Expected result:** The LLM responds with something generic like "I don't have access to real-time information" or "I can't check the current time." **This is because no tools were sent to the LLM** — it has no way to check the time.

**Also verify:** The response streams in token by token (you'll see text appearing progressively, not all at once). This confirms streaming is working.

### 6.3 Test 2: Tool Mode "Auto"

1. Click the **Auto** button in the tool mode selector.
2. You should see the message: "All tools available to LLM automatically (disables streaming)"
3. Type: **"What time is it?"**
4. Click Send.

**Expected result:** The LLM responds with the **actual current time** (e.g., "The current time is March 14, 2026 at 3:30 PM UTC"). This confirms:
- All 5 tools were injected into the request
- The LLM chose to call `get_current_time`
- The agentic loop executed the tool and fed the result back
- The LLM generated a human-readable answer

**Also verify:** The response appears all at once (not streaming), since tools force non-streaming mode. You may notice a slight delay as the agentic loop makes 2 round-trips to the LLM.

**More tests with Auto mode:**
- Try: **"What is 137 * 429?"** — The LLM should call `calculate` and give `58,773`
- Try: **"Generate a unique ID for me"** — The LLM should call `generate_uuid`
- Try: **"Count the words in: The quick brown fox jumps over the lazy dog"** — The LLM should call `word_count`
- Try: **'Pretty print this JSON: {"a":1,"b":[2,3]}'** — The LLM should call `json_formatter`

### 6.4 Test 3: Tool Mode "Manual"

1. Click the **Manual** button in the tool mode selector.
2. The checkbox list of tools appears. Check only **`calculate`**.
3. Type: **"What time is it?"**
4. Click Send.

**Expected result:** The LLM responds generically (cannot check the time) because `get_current_time` is not in the selected tools — only `calculate` is.

5. Now type: **"What is 2 + 2?"**

**Expected result:** The LLM calls `calculate` and responds with `4`.

6. Uncheck all tools. Now type: **"What is 2 + 2?"**

**Expected result:** Since no tools are selected in manual mode, it behaves like "off". The LLM answers `4` from its own knowledge (no tool call), and the response **streams** in.

### 6.5 Test 4: Verify Streaming Still Works with Tools Off

1. Click the **Off** button.
2. Type any message (e.g., "Tell me a joke").
3. Click Send.

**Expected result:** The response streams in token by token. Open the browser's Network tab (DevTools → Network) and look for a `turn/stream` request. You should see:
- Request URL: `/api/chat/turn/stream`
- Response type: `text/event-stream`
- Events in the response: `event: meta`, multiple `event: delta`, and `event: final`

---

## 7. Testing via API Requests (curl)

All examples assume the backend is running on `http://localhost:8000`.

### 7.1 Discover Available Tools

```bash
curl -s http://localhost:8000/api/tools | python3 -m json.tool
```

**Expected response:**
```json
{
  "tools": [
    {
      "name": "get_current_time",
      "description": "Returns the current date and time in ISO 8601 format.",
      "parameters_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
      "name": "calculate",
      "description": "Evaluates a math expression. Supports +, -, *, /, //, %, **.",
      "parameters_schema": {
        "type": "object",
        "properties": {
          "expression": {"type": "string", "description": "A mathematical expression, e.g. '2 + 3 * 4'"}
        },
        "required": ["expression"]
      }
    },
    {
      "name": "generate_uuid",
      "description": "Generates a random UUID v4. Useful when a unique identifier is needed.",
      "parameters_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
      "name": "word_count",
      "description": "Counts words, characters, sentences, and lines in the given text.",
      "parameters_schema": {
        "type": "object",
        "properties": {
          "text": {"type": "string", "description": "The text to analyze."}
        },
        "required": ["text"]
      }
    },
    {
      "name": "json_formatter",
      "description": "Validates, pretty-prints, or minifies a JSON string.",
      "parameters_schema": {
        "type": "object",
        "properties": {
          "json_string": {"type": "string", "description": "The JSON string to process."},
          "mode": {
            "type": "string",
            "enum": ["pretty", "minify", "validate"],
            "description": "Operation mode: 'pretty' to format with indentation, 'minify' to compact, 'validate' to check validity."
          }
        },
        "required": ["json_string", "mode"]
      }
    }
  ]
}
```

### 7.2 Send a Turn with `tool_mode: "auto"`

This injects all 5 tools. The LLM decides which (if any) to call.

```bash
curl -s -X POST http://localhost:8000/api/chat/turn \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "What time is it?",
    "system_prompt": "You are a helpful assistant.",
    "temperature": 0.7,
    "max_tokens": 1024,
    "provider_options": {},
    "tool_mode": "auto"
  }' | python3 -m json.tool
```

**Expected response:**
```json
{
  "conversation_id": "some-uuid",
  "run_id": "some-uuid",
  "response": {
    "output_text": "The current time is 2026-03-14T15:30:00+00:00 UTC.",
    "finish_reason": "stop",
    "provider_response_id": "chatcmpl-...",
    "usage": {
      "prompt_tokens": 150,
      "completion_tokens": 30,
      "total_tokens": 180
    },
    "tool_calls": null,
    "raw": {}
  },
  "latency_ms": 2500.0
}
```

The `output_text` should contain the **actual current time**, proving the LLM called `get_current_time` behind the scenes.

Note: The token usage is the **total** across all iterations of the agentic loop. The latency includes all LLM round-trips.

### 7.3 Send a Turn with `tool_mode: "manual"`

Only specific tools are made available.

```bash
curl -s -X POST http://localhost:8000/api/chat/turn \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "What is 15 * 37?",
    "system_prompt": "You are a helpful assistant.",
    "temperature": 0.7,
    "max_tokens": 1024,
    "provider_options": {},
    "tool_mode": "manual",
    "tool_names": ["calculate"]
  }' | python3 -m json.tool
```

**Expected response:** The `output_text` should contain `555` (the result of 15 * 37), computed via the `calculate` tool.

**Test with an unknown tool name:**

```bash
curl -s -X POST http://localhost:8000/api/chat/turn \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "hello",
    "tool_mode": "manual",
    "tool_names": ["nonexistent_tool"]
  }' | python3 -m json.tool
```

**Expected response:** HTTP 400 with `{"detail": "Unknown tool: 'nonexistent_tool'"}`

### 7.4 Send a Turn with `tool_mode: "off"` (Default)

```bash
curl -s -X POST http://localhost:8000/api/chat/turn \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "What time is it?",
    "system_prompt": "You are a helpful assistant.",
    "temperature": 0.7,
    "max_tokens": 1024,
    "provider_options": {},
    "tool_mode": "off"
  }' | python3 -m json.tool
```

**Expected response:** The LLM responds generically — it does NOT know the time because no tools were provided.

### 7.5 Verify Streaming + Tools Returns 400

The backend rejects streaming requests when tools are active:

```bash
# Auto mode + streaming = 400
curl -s -X POST http://localhost:8000/api/chat/turn/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "What time is it?",
    "tool_mode": "auto"
  }' | python3 -m json.tool
```

**Expected response:**
```json
{
  "detail": "Tool calling is not supported with streaming"
}
```

```bash
# Manual mode with tools + streaming = 400
curl -s -X POST http://localhost:8000/api/chat/turn/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "What is 2+2?",
    "tool_mode": "manual",
    "tool_names": ["calculate"]
  }' | python3 -m json.tool
```

**Expected response:** Same 400 error.

```bash
# Off mode + streaming = works fine
curl -s -N -X POST http://localhost:8000/api/chat/turn/stream \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "Tell me a joke",
    "tool_mode": "off"
  }'
```

**Expected response:** SSE stream with `event: meta`, `event: delta` (multiple), and `event: final`.

### 7.6 Backward Compatibility (No `tool_mode` Field)

Omitting `tool_mode` entirely is valid — it defaults to `"off"`:

```bash
curl -s -X POST http://localhost:8000/api/chat/turn \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "Hello!",
    "temperature": 0.7,
    "max_tokens": 1024,
    "provider_options": {}
  }' | python3 -m json.tool
```

**Expected response:** Works normally, no tools injected.

### 7.7 Continue a Conversation with Tools

Use the `conversation_id` from a previous response to continue the conversation:

```bash
# First turn — start a conversation with auto tools
RESPONSE=$(curl -s -X POST http://localhost:8000/api/chat/turn \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "message": "What time is it?",
    "system_prompt": "You are a helpful assistant.",
    "tool_mode": "auto"
  }')

echo "$RESPONSE" | python3 -m json.tool

# Extract conversation_id
CONV_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['conversation_id'])")

# Second turn — continue the conversation
curl -s -X POST http://localhost:8000/api/chat/turn \
  -H "Content-Type: application/json" \
  -d "{
    \"conversation_id\": \"$CONV_ID\",
    \"provider\": \"openai\",
    \"model\": \"gpt-4o-mini\",
    \"message\": \"And what is 100 * 24?\",
    \"tool_mode\": \"auto\"
  }" | python3 -m json.tool
```

**Expected:** The second turn has access to the full conversation history AND all tools. The LLM should call `calculate` and return `2400`.

### 7.8 Use the Legacy `/api/chat` Endpoint with Tools

The legacy endpoint doesn't use `tool_mode` — it uses the raw `tools` field in `ChatRequest`. This is a lower-level interface where you provide the tool definitions directly:

```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What time is it?"}
    ],
    "temperature": 0.7,
    "max_tokens": 1024,
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_current_time",
          "description": "Returns the current date and time in ISO 8601 format.",
          "parameters": {"type": "object", "properties": {}, "required": []}
        }
      }
    ],
    "tool_choice": "auto"
  }' | python3 -m json.tool
```

**Expected:** Same behavior — the LLM calls `get_current_time` and returns the actual time.

The key difference from the turn-based endpoint: you must provide the tool definitions in OpenAI wire format yourself, there's no `tool_mode`, and there's no conversation tracking.

---

## 8. Running the Automated Tests

```bash
cd backend

# Run ALL tool-related tests (46 tests)
uv run pytest -v tests/test_tools.py

# Run only the tool mode tests (8 tests)
uv run pytest -v tests/test_tools.py::TestToolMode

# Run a specific test
uv run pytest -v tests/test_tools.py::TestToolMode::test_auto_mode_injects_all_tools
```

### What the TestToolMode Tests Cover

| Test | What It Verifies |
|---|---|
| `test_auto_mode_injects_all_tools` | `tool_mode: "auto"` injects all 5 tools into ChatRequest with `tool_choice: "auto"` |
| `test_off_mode_sends_no_tools` | `tool_mode: "off"` sends no tools and no `tool_choice` |
| `test_manual_mode_with_tool_names` | `tool_mode: "manual"` + `tool_names: ["calculate"]` resolves just that tool |
| `test_manual_mode_without_tool_names_sends_no_tools` | `tool_mode: "manual"` without `tool_names` = no tools (treated like off) |
| `test_streaming_with_auto_mode_returns_400` | `POST /api/chat/turn/stream` + `tool_mode: "auto"` → HTTP 400 |
| `test_omitting_tool_mode_defaults_to_off` | Omitting `tool_mode` entirely → no tools (backward compatible) |
| `test_streaming_with_manual_tools_returns_400` | `POST /api/chat/turn/stream` + `tool_mode: "manual"` + tools → HTTP 400 |
| `test_streaming_with_off_mode_allowed` | `POST /api/chat/turn/stream` + `tool_mode: "off"` → HTTP 200 (streaming works) |

### Other Test Classes

| Class | What It Tests |
|---|---|
| `TestGetCurrentTimeTool` | The time tool returns valid ISO format |
| `TestCalculateTool` | Math expressions, edge cases, security (rejects function calls/imports) |
| `TestGenerateUuidTool` | UUID format and uniqueness |
| `TestWordCountTool` | Word/char/sentence/line counting |
| `TestJsonFormatterTool` | Pretty-print, minify, validate modes |
| `TestToolRegistry` | Register, get, list operations |
| `TestToolExecutor` | Agentic loop: pass-through, single tool call, unknown tools, exceptions, max iterations, usage aggregation, parallel calls |
| `TestChatAPIToolIntegration` | Legacy `/api/chat` endpoint backward compat and streaming guard |
| `TestTurnToolIntegration` | Turn endpoint: unknown tool name → 400, streaming guard, backward compat |
| `TestToolDiscoveryEndpoint` | `GET /api/tools` returns all 5 tools with correct schema shape |

---

## 9. Schemas Reference

### `ConversationTurnRequest` (what the frontend sends)

```
POST /api/chat/turn
POST /api/chat/turn/stream
```

```json
{
  "conversation_id": "optional-uuid",       // omit for new conversation
  "provider": "openai",                     // required
  "model": "gpt-4o-mini",                  // required
  "message": "What time is it?",           // required - the user's message
  "system_prompt": "You are helpful.",      // optional, only used for first turn
  "temperature": 0.7,                       // optional, default 0.7
  "max_tokens": 1024,                       // optional, default 1024
  "provider_options": {},                   // optional, pass-through to provider
  "tool_mode": "auto",                     // "off" | "auto" | "manual", default "off"
  "tool_names": ["calculate"]              // only used when tool_mode is "manual"
}
```

### `TurnResponse` (what the backend returns)

```json
{
  "conversation_id": "uuid",
  "run_id": "uuid",
  "response": {
    "output_text": "The time is ...",
    "finish_reason": "stop",
    "provider_response_id": "chatcmpl-...",
    "usage": {
      "prompt_tokens": 150,
      "completion_tokens": 30,
      "total_tokens": 180
    },
    "tool_calls": null,
    "raw": {}
  },
  "latency_ms": 2500.0
}
```

### `ChatRequest` (internal, also used by legacy `/api/chat`)

This is the lower-level schema used between the router and the adapter. The turn-based endpoint converts `ConversationTurnRequest` into this format internally.

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "What time is it?"}
  ],
  "temperature": 0.7,
  "max_tokens": 1024,
  "tools": [                                            // injected by _prepare_turn based on tool_mode
    {
      "type": "function",
      "function": {
        "name": "get_current_time",
        "description": "Returns the current date and time in ISO 8601 format.",
        "parameters": {"type": "object", "properties": {}, "required": []}
      }
    }
  ],
  "tool_choice": "auto",                               // injected alongside tools
  "provider_options": {}
}
```

---

## 10. How to Add a New Tool

1. **Create the tool class** in `backend/app/agentic/tools.py`:

```python
class MyNewTool(Tool):
    definition = ToolDefinition(
        name="my_new_tool",                              # unique name
        description="Does something useful.",            # LLM reads this to decide when to use it
        parameters_schema={
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "The input to process.",
                }
            },
            "required": ["input"],
        },
    )

    async def execute(self, arguments: dict[str, Any]) -> str:
        input_val = arguments.get("input", "")
        # ... your logic here ...
        return "result string"
```

2. **Register it** in `register_default_tools()` in the same file:

```python
def register_default_tools() -> None:
    # ... existing tools ...
    tool_registry.register(MyNewTool())
```

3. **Write tests** in `backend/tests/test_tools.py`.

4. **No frontend changes needed.** The tool automatically appears in `GET /api/tools` and in the UI's tool list. When `tool_mode: "auto"` is used, the new tool is automatically available to the LLM.
