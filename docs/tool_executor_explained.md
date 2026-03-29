# Tool Executor — How the Iterative Loop Works

## Quick Start

```bash
cd backend && uv run python scripts/mock_tool_demo.py
```

No API keys required — the demo uses a mock adapter with scripted LLM responses.

---

## The Problem the Loop Solves

When an LLM has access to tools, it can't always answer in one shot. Consider this user request:

> "What time is it? Calculate how many minutes 2.5 hours is, count the words in my meeting agenda, and give me a unique meeting ID. Format everything as JSON."

The LLM needs to:
1. Call `get_current_time` to learn the time (it doesn't know it)
2. Call `generate_uuid` to create a meeting ID
3. Call `calculate` with `2.5 * 60`
4. Call `word_count` on the agenda text
5. Call `json_formatter` to produce the final output
6. Compose a final answer using all the results

The LLM **cannot do all of this in one response**. After each batch of tool calls, it needs to see the results before deciding what to do next. This is why the `ToolExecutor` uses a loop.

---

## The Loop — Step by Step

Here is the core loop from `backend/app/services/tool_executor.py`:

```python
for i in range(self._max_iterations):            # ← Safety cap (default: 10)
    current_req = req.model_copy(update={"messages": messages})
    response = await adapter.chat(current_req)    # ← Call the LLM

    _accumulate_usage(total_usage, response.usage)

    if not response.tool_calls:                   # ← EXIT CONDITION
        break                                     #    LLM gave a text answer

    # Append the assistant message that requested tools
    messages.append(Message(
        role="assistant",
        content=response.output_text or None,
        tool_calls=response.tool_calls,
    ))

    # Execute each tool and append results
    for tc in response.tool_calls:
        result = await self._execute_single(tc.function.name, tc.function.arguments)
        messages.append(Message(
            role="tool",
            content=result,
            tool_call_id=tc.id,
        ))
```

### What happens at each iteration:

| Step | What | Why |
|------|-------|-----|
| 1 | Send messages + tool definitions to LLM | LLM needs the full conversation context |
| 2 | LLM returns a response | Could be text (done) or tool_calls (needs more info) |
| 3 | Check: `tool_calls` empty? | If yes → **break**, return the text answer |
| 4 | Append assistant message to history | The LLM's "I want to call these tools" becomes part of the conversation |
| 5 | Execute each tool | Real function calls — `get_current_time()`, `calculate()`, etc. |
| 6 | Append tool results to history | So the LLM can see them on the next iteration |
| 7 | Go to step 1 | Loop continues with enriched context |

---

## Demo Walkthrough

The mock demo (`backend/scripts/mock_tool_demo.py`) simulates this exact flow:

### Iteration 1 — Parallel Independent Calls

```
Messages sent to LLM:  [system, user]  →  2 messages

LLM thinks: "I need the time and a meeting ID. These are independent."

LLM returns:
  tool_calls: [get_current_time, generate_uuid]

Executor runs both tools:
  get_current_time → "2026-03-26T14:30:00+00:00"
  generate_uuid    → "a3f7c2e1-8b4d-4f9a-..."

Messages after: [system, user, assistant(tool_calls), tool, tool]  →  5 messages
```

**Key insight**: The LLM requested two tools in a single response. The executor runs them both, then continues. This is **intra-iteration parallelism** — the LLM is smart enough to batch independent calls.

### Iteration 2 — Calls That Depend on Prior Results

```
Messages sent to LLM:  5 messages (includes tool results from iteration 1)

LLM thinks: "Good, I have the time and UUID. Now I need the calculation
             and word count. These two don't depend on each other."

LLM returns:
  tool_calls: [calculate("2.5 * 60"), word_count("Discuss Q3...")]

Executor runs both:
  calculate  → "150.0"
  word_count → {"words": 11, "characters": 89, "sentences": 3, "lines": 1}

Messages after: 9 messages
```

**Key insight**: This iteration could NOT have happened in iteration 1. The LLM needed to see the results from `get_current_time` and `generate_uuid` before it could reason about what to do next. The loop gives it that opportunity.

### Iteration 3 — Aggregation

```
Messages sent to LLM:  9 messages (full history)

LLM thinks: "I have all the pieces. Let me format them as JSON."

LLM returns:
  tool_calls: [json_formatter(summary_json, "pretty")]

Executor runs:
  json_formatter → pretty-printed JSON string

Messages after: 12 messages
```

### Iteration 4 — Final Answer (Loop Exits)

```
Messages sent to LLM:  12 messages

LLM thinks: "Everything is ready. I'll compose the final answer."

LLM returns:
  output_text: "Here's your meeting summary: ..."
  tool_calls: None  ← THIS IS THE EXIT SIGNAL

Loop breaks. Response returned to caller.
```

---

## Why Not Just One Big Call?

You might wonder: can't the LLM call all 5 tools at once and be done in 2 iterations?

**No, for two reasons:**

1. **Data dependencies**: The LLM can't format a JSON summary until it has the actual UUID, time, calculation result, and word count. It needs to *see* those values first.

2. **Reasoning dependencies**: Sometimes the LLM's choice of *which* tool to call next depends on the result of a previous tool. For example, if `calculate` returned an error, the LLM might call it again with a corrected expression instead of proceeding to `json_formatter`.

The iterative loop handles both cases naturally — the LLM decides at each step what to do next, based on everything it knows so far.

---

## The Message History Grows Each Iteration

This is the critical mechanism. Here's how `messages` evolves:

```
Start:     [system, user]

After iter 1:  [system, user, assistant→{tools}, tool_result, tool_result]

After iter 2:  [..., assistant→{tools}, tool_result, tool_result]

After iter 3:  [..., assistant→{tools}, tool_result]

Iter 4 input:  12 messages total — the LLM sees the entire chain
```

Each tool result message includes a `tool_call_id` that links it back to the specific `tool_call` in the preceding assistant message. This is how the LLM knows which result corresponds to which request:

```python
# Assistant message (requesting tools):
Message(role="assistant", tool_calls=[
    ToolCall(id="call_time_001", function=ToolCallFunction(name="get_current_time", ...)),
    ToolCall(id="call_uuid_001", function=ToolCallFunction(name="generate_uuid", ...)),
])

# Tool result messages (linked by tool_call_id):
Message(role="tool", content="2026-03-26T14:30:00+00:00", tool_call_id="call_time_001")
Message(role="tool", content="a3f7c2e1-8b4d-...",          tool_call_id="call_uuid_001")
```

---

## Safety: The Iteration Cap

```python
MAX_TOOL_ITERATIONS = 10
```

The loop has a hard limit to prevent:
- **Infinite loops**: A misbehaving LLM that always requests tools and never gives a final answer
- **Runaway costs**: Each iteration is a full LLM API call with growing context
- **Token explosion**: The message list grows each iteration — without a cap, context could exceed limits

If the limit is reached, the executor returns whatever the last response was (which may have `tool_calls` still set — the caller should handle this).

---

## How the Router Triggers the Loop

From `backend/app/routers/chat.py`:

```python
@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)) -> dict:
    adapter = get_adapter(req.provider)

    if req.tools:                                    # ← Tools requested?
        executor = ToolExecutor(tool_registry)
        response = await executor.execute_with_tools(adapter, req)  # ← Loop runs here
    else:
        response = await adapter.chat(req)           # ← Simple single-shot call
```

When the frontend sends `tools` in the request, the router delegates to `ToolExecutor` instead of calling the adapter directly. The executor handles the entire multi-turn conversation internally and returns a single final response.

---

## Token Usage Accumulation

Each iteration costs tokens. The executor tracks this:

```python
total_usage = UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0)

for i in range(self._max_iterations):
    response = await adapter.chat(current_req)
    _accumulate_usage(total_usage, response.usage)   # ← Sum across all iterations
    ...

response.usage = total_usage  # ← Final response carries the total
```

In the mock demo, the 4 iterations accumulate:
- Iteration 1: 115 tokens
- Iteration 2: 225 tokens
- Iteration 3: 295 tokens
- Iteration 4: 400 tokens
- **Total: 1,035 tokens**

This is important for cost tracking and the `Run` record persisted to the database.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     ToolExecutor                         │
│                                                          │
│  messages = [system, user]                               │
│                                                          │
│  ┌─── for i in range(max_iterations): ───────────────┐   │
│  │                                                    │   │
│  │   ┌─────────────┐     ┌──────────────────────┐    │   │
│  │   │  LLM Call    │────▶│ Response has          │    │   │
│  │   │  (adapter)   │     │ tool_calls?           │    │   │
│  │   └─────────────┘     └──────┬───────┬────────┘    │   │
│  │                        No    │       │ Yes          │   │
│  │                    ┌─────────┘       ▼              │   │
│  │                    │     ┌──────────────────┐       │   │
│  │                    │     │ Execute tools     │       │   │
│  │                    │     │ (ToolRegistry)    │       │   │
│  │                    │     └────────┬─────────┘       │   │
│  │                    │              │                  │   │
│  │                    │              ▼                  │   │
│  │                    │     ┌──────────────────┐       │   │
│  │                    │     │ Append to messages│       │   │
│  │                    │     │ • assistant msg   │       │   │
│  │                    │     │ • tool results    │       │   │
│  │                    │     └────────┬─────────┘       │   │
│  │                    │              │                  │   │
│  │                    │              └──── next iter ───┘   │
│  │                    │                                     │
│  │                    ▼                                     │
│  │              BREAK (return response)                     │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Summary

| Concept | Detail |
|---------|--------|
| **Why a loop?** | LLMs need to see tool results before deciding next steps |
| **Exit condition** | `response.tool_calls` is empty → LLM gave a final text answer |
| **Safety cap** | `MAX_TOOL_ITERATIONS = 10` prevents infinite/runaway loops |
| **Parallel tools** | LLM can request multiple tools per iteration; executor runs them all |
| **Message growth** | Each iteration adds assistant + tool messages; LLM sees full history |
| **Usage tracking** | Token counts accumulated across all iterations for cost visibility |
| **Router integration** | `if req.tools:` branches into the executor; otherwise single-shot |
