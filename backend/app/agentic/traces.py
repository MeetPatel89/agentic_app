"""Stub: Multi-step run traces for agentic workflows (v2+).

Design:
- A Trace groups multiple Runs under a single trace_id.
- Each Run can have a parent_run_id forming a tree (e.g., main LLM call -> tool call -> sub-LLM call).
- The Run model already has trace_id and parent_run_id columns.
- This module will provide helpers to create/manage traces.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class TraceContext:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_run_id: str | None = None

    def child(self, run_id: str) -> TraceContext:
        return TraceContext(trace_id=self.trace_id, parent_run_id=run_id)


def new_trace() -> TraceContext:
    return TraceContext()
