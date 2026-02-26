from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.adapters.registry import get_adapter, list_providers

router = APIRouter()


@router.get("/health")
async def healthcheck() -> dict:
    return {
        "status": "ok",
        "available_providers": list_providers(),
    }


@router.get("/api/providers/{provider}/models")
async def provider_models(provider: str) -> dict:
    adapter = get_adapter(provider)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not available")

    try:
        models = await adapter.list_models()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to list models for '{provider}': {exc}") from exc

    return {"provider": provider, "models": models}
