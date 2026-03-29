"""
Mock Tool Demo — Demonstrates the ToolExecutor's iterative loop with no API keys.

Run with:
    cd backend && uv run python scripts/mock_tool_demo.py

Scenario:
    The user asks the LLM to plan a meeting. The mock LLM decides it needs
    multiple tools across several iterations, showing exactly why the
    ToolExecutor uses an iterative loop.

    Iteration 1: get_current_time + generate_uuid      (parallel — no dependencies)
    Iteration 2: calculate + word_count                 (depends on iteration 1 context)
    Iteration 3: json_formatter                         (aggregates all prior results)
    Iteration 4: final text response                    (no tool_calls → loop exits)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import AsyncIterator
from pathlib import Path

# Ensure the backend package is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.base import ProviderAdapter, StreamEvent
from app.agentic.tools import register_default_tools, tool_registry
from app.schemas import (
    ChatRequest,
    Message,
    NormalizedChatResponse,
    ToolCall,
    ToolCallFunction,
    UsageInfo,
)
from app.services.tool_executor import ToolExecutor

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")


# ── Helpers ────────────────────────────────────────────────────────────────

def _divider(char: str = "─", width: int = 64) -> str:
    return char * width


def _print_messages(messages: list[Message], label: str) -> None:
    """Pretty-print the message list at a given point in the loop."""
    print(f"\n  📨 {label} ({len(messages)} messages):")
    for i, m in enumerate(messages):
        role = m.role.upper().ljust(10)
        if m.role == "tool":
            preview = (m.content or "")[:70]
            print(f"      [{i}] {role} (call_id={m.tool_call_id}) → {preview}")
        elif m.role == "assistant" and m.tool_calls:
            names = [tc.function.name for tc in m.tool_calls]
            print(f"      [{i}] {role} requests tools: {names}")
        else:
            preview = (m.content or "")[:70]
            print(f"      [{i}] {role} {preview}")


# ── Mock LLM Adapter ──────────────────────────────────────────────────────

class MockLLMAdapter(ProviderAdapter):
    """Fake adapter with scripted responses — no network calls.

    Each call to chat() returns a pre-defined response that mimics what a
    real LLM would return at each stage of multi-step reasoning.
    """

    name = "mock"

    def __init__(self) -> None:
        self._call_count = 0

    def is_available(self) -> bool:
        return True

    async def chat(self, req: ChatRequest) -> NormalizedChatResponse:
        self._call_count += 1
        n = self._call_count

        print(f"\n{'=' * 64}")
        print(f"  🤖 MOCK LLM — chat() call #{n}")
        _print_messages(req.messages, f"Context sent to LLM (call #{n})")

        if n == 1:
            return self._iteration_1()
        elif n == 2:
            return self._iteration_2()
        elif n == 3:
            return self._iteration_3()
        else:
            return self._iteration_final()

    # ── Scripted responses per iteration ──────────────────────────────

    def _iteration_1(self) -> NormalizedChatResponse:
        """Two parallel tool calls — no dependency on prior results."""
        print("\n  💭 LLM reasoning: \"I need the current time and a unique ID.")
        print("     These are independent — I'll call both at once.\"")
        print("\n  → Returning 2 tool_calls: get_current_time, generate_uuid")
        print(f"{'=' * 64}")
        return NormalizedChatResponse(
            output_text="Let me get the current time and generate a meeting ID.",
            finish_reason="tool_calls",
            tool_calls=[
                ToolCall(
                    id="call_time_001",
                    function=ToolCallFunction(
                        name="get_current_time",
                        arguments="{}",
                    ),
                ),
                ToolCall(
                    id="call_uuid_001",
                    function=ToolCallFunction(
                        name="generate_uuid",
                        arguments="{}",
                    ),
                ),
            ],
            usage=UsageInfo(prompt_tokens=85, completion_tokens=30, total_tokens=115),
        )

    def _iteration_2(self) -> NormalizedChatResponse:
        """Two more tool calls — these depend on the iteration-1 context."""
        print("\n  💭 LLM reasoning: \"Good, I have the time and UUID. Now I need")
        print("     to compute the meeting duration and analyze the agenda text.")
        print("     The calculate tool needs an expression; the word_count tool")
        print("     needs the agenda. These two are independent of each other.\"")
        print("\n  → Returning 2 tool_calls: calculate, word_count")
        print(f"{'=' * 64}")
        return NormalizedChatResponse(
            output_text="Now let me calculate the duration and analyze the agenda.",
            finish_reason="tool_calls",
            tool_calls=[
                ToolCall(
                    id="call_calc_001",
                    function=ToolCallFunction(
                        name="calculate",
                        arguments=json.dumps({"expression": "2.5 * 60"}),
                    ),
                ),
                ToolCall(
                    id="call_wc_001",
                    function=ToolCallFunction(
                        name="word_count",
                        arguments=json.dumps({
                            "text": (
                                "Discuss Q3 roadmap. Review hiring pipeline. "
                                "Finalize budget allocation for infrastructure upgrades."
                            )
                        }),
                    ),
                ),
            ],
            usage=UsageInfo(prompt_tokens=180, completion_tokens=45, total_tokens=225),
        )

    def _iteration_3(self) -> NormalizedChatResponse:
        """One tool call — aggregates all prior results into formatted JSON."""
        print("\n  💭 LLM reasoning: \"I have all the pieces. Let me assemble a")
        print("     structured summary and format it nicely with json_formatter.\"")
        print("\n  → Returning 1 tool_call: json_formatter")
        print(f"{'=' * 64}")
        summary = {
            "meeting_id": "<uuid from iteration 1>",
            "scheduled_at": "<time from iteration 1>",
            "duration_minutes": 150,
            "agenda_stats": {"words": 11, "sentences": 3},
            "status": "confirmed",
        }
        return NormalizedChatResponse(
            output_text="Let me format the meeting summary.",
            finish_reason="tool_calls",
            tool_calls=[
                ToolCall(
                    id="call_json_001",
                    function=ToolCallFunction(
                        name="json_formatter",
                        arguments=json.dumps({
                            "json_string": json.dumps(summary),
                            "mode": "pretty",
                        }),
                    ),
                ),
            ],
            usage=UsageInfo(prompt_tokens=260, completion_tokens=35, total_tokens=295),
        )

    def _iteration_final(self) -> NormalizedChatResponse:
        """No tool_calls — the loop will exit after this."""
        print("\n  💭 LLM reasoning: \"I have everything. Time to give the user")
        print("     a final answer. No more tools needed.\"")
        print("\n  → Returning text only (tool_calls=None) — LOOP WILL EXIT")
        print(f"{'=' * 64}")
        return NormalizedChatResponse(
            output_text=(
                "Here's your meeting summary:\n\n"
                "• Meeting ID: a]3f7c2e1-...\n"
                "• Scheduled: 2026-03-26T14:30:00+00:00\n"
                "• Duration: 150 minutes (2.5 hours × 60)\n"
                "• Agenda: 11 words, 3 sentences\n\n"
                "The formatted JSON summary is ready for your records."
            ),
            finish_reason="stop",
            tool_calls=None,
            usage=UsageInfo(prompt_tokens=340, completion_tokens=60, total_tokens=400),
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError("Streaming not used in this demo")

    async def list_models(self) -> list[str]:
        return ["mock-scripted-v1"]


# ── Main ───────────────────────────────────────────────────────────────────

async def main() -> None:
    print(f"\n{'▓' * 64}")
    print("  MOCK TOOL DEMO — ToolExecutor Iterative Loop")
    print(f"{'▓' * 64}")
    print()
    print("This demo runs the real ToolExecutor with a mock LLM adapter.")
    print("No API keys needed. Watch how the loop iterates until the LLM")
    print("stops requesting tools.\n")
    print(_divider())

    # 1. Register the real built-in tools
    register_default_tools()
    tools = tool_registry.list_definitions()
    print(f"Registered {len(tools)} tools: {[t.name for t in tools]}")

    # 2. Create executor and mock adapter
    executor = ToolExecutor(registry=tool_registry, max_iterations=10)
    adapter = MockLLMAdapter()

    # 3. Build the initial request
    request = ChatRequest(
        provider="mock",
        model="mock-scripted-v1",
        messages=[
            Message(
                role="system",
                content="You are a helpful meeting assistant with access to tools.",
            ),
            Message(
                role="user",
                content=(
                    "Plan a meeting for me: tell me the current time, calculate "
                    "how many minutes 2.5 hours is, count the words in my agenda "
                    "'Discuss Q3 roadmap. Review hiring pipeline. Finalize budget "
                    "allocation for infrastructure upgrades.' — and give me a "
                    "unique meeting ID. Format everything as JSON."
                ),
            ),
        ],
        tools=tool_registry.list_request_schemas(),
        tool_choice="auto",
    )

    print(f"\nUser prompt:\n  \"{request.messages[1].content}\"\n")
    print(f"Max loop iterations: {executor._max_iterations}")
    print(_divider())

    # 4. Run the tool-calling loop
    print("\n🚀 Starting ToolExecutor.execute_with_tools()...\n")
    response = await executor.execute_with_tools(adapter, request)

    # 5. Print results
    print(f"\n{'▓' * 64}")
    print("  LOOP COMPLETE — FINAL RESULT")
    print(f"{'▓' * 64}")
    print(f"\nTotal LLM calls (iterations): {adapter._call_count}")
    print(f"Finish reason: {response.finish_reason}")
    print(f"Accumulated usage: {response.usage.model_dump()}")
    print("\nFinal output text:")
    print(_divider("─", 40))
    print(response.output_text)
    print(_divider("─", 40))

    print("""
WHAT HAPPENED (iteration by iteration):

  Iteration 1:
    LLM received: [system, user]  (2 messages)
    LLM returned: tool_calls → [get_current_time, generate_uuid]
    Executor ran both tools, appended assistant + 2 tool results

  Iteration 2:
    LLM received: [system, user, assistant, tool, tool]  (5 messages)
    LLM returned: tool_calls → [calculate, word_count]
    Executor ran both tools, appended assistant + 2 tool results

  Iteration 3:
    LLM received: [system, user, asst, tool, tool, asst, tool, tool]  (9 messages)
    LLM returned: tool_calls → [json_formatter]
    Executor ran tool, appended assistant + 1 tool result

  Iteration 4:
    LLM received: 12 messages (full conversation history)
    LLM returned: text only (tool_calls=None)
    → No tool_calls → loop breaks → response returned to caller

WHY THE LOOP EXISTS:
    The LLM can't know all the answers up front. Each iteration gives it
    new information (tool results) that informs what to do next. Without
    the loop, you'd need a separate API call for every single step, and
    the caller would have to manually manage the message history.
""")


if __name__ == "__main__":
    asyncio.run(main())
