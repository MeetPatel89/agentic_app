from __future__ import annotations

from fastapi import APIRouter

from app.agentic.tools import tool_registry

router = APIRouter(prefix="/api")


@router.get("/tools")
async def list_tools() -> dict:
    return {
        "tools": [d.model_dump() for d in tool_registry.list_definitions()],
    }
