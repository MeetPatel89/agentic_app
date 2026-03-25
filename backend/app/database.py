from __future__ import annotations

from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def _engine_kwargs(database_url: str) -> dict[str, Any]:
    url = make_url(database_url)
    backend = url.get_backend_name()

    kwargs: dict[str, Any] = {
        "echo": False,
        "future": True,
    }

    # Avoid stale pooled connections for networked databases.
    if backend != "sqlite":
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["pool_timeout"] = 30
    else:
        kwargs["connect_args"] = {"timeout": 30}

    return kwargs


def create_app_engine(database_url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    db_url = database_url or settings.resolved_database_url
    return create_async_engine(db_url, **_engine_kwargs(db_url))


engine = create_app_engine()

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        yield session
