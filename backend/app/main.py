from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.registry import init_registry
from app.agentic.tools import register_default_tools
from app.config import get_settings
from app.database import engine
from app.middleware.request_logging import RequestLoggingMiddleware
from app.models import Base
from app.nl2sql.router import router as nl2sql_router
from app.routers import chat, conversations, health, runs, tools


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Create tables (dev convenience; use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    init_registry()
    register_default_tools()
    yield


app = FastAPI(title="LLM Router & Playground", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(runs.router)
app.include_router(conversations.router)
app.include_router(tools.router)
app.include_router(nl2sql_router)
