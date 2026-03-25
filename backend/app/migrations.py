from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config


def run_migrations(database_url: str) -> None:
    """Run Alembic migrations to head for the provided database URL."""
    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini = backend_root / "alembic.ini"

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


async def run_migrations_async(database_url: str) -> None:
    """Async wrapper to run Alembic safely within app lifespan."""
    await asyncio.to_thread(run_migrations, database_url)
