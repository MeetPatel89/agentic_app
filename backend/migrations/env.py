import asyncio
import os
from logging.config import fileConfig
from urllib.parse import parse_qsl

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def _resolved_database_url_from_env() -> str:
    # Keep Alembic self-contained and avoid importing app settings module.
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    host = os.getenv("DATABASE_HOST", "").strip()
    name = os.getenv("DATABASE_NAME", "").strip()
    user = os.getenv("DATABASE_USER", "").strip()
    password = os.getenv("DATABASE_PASSWORD", "").strip()
    if host and name and user and password:
        drivername = os.getenv("DATABASE_DRIVERNAME", "mssql+aioodbc")
        port_raw = os.getenv("DATABASE_PORT", "").strip()
        port = int(port_raw) if port_raw else None
        query = dict(parse_qsl(os.getenv("DATABASE_QUERY", ""), keep_blank_values=True))
        if drivername.startswith("mssql") and "driver" not in query:
            query["driver"] = "ODBC Driver 18 for SQL Server"
        return str(
            URL.create(
                drivername=drivername,
                username=user,
                password=password,
                host=host,
                port=port,
                database=name,
                query=query,
            )
        )

    return "sqlite+aiosqlite:///./llm_router.db"


# Prefer a URL already injected by a programmatic caller (e.g. migrations.py)
# over the static alembic.ini default.  Fall back to env-var resolution only
# when the URL is still the ini placeholder (direct `alembic upgrade` from CLI).
_INI_DEFAULT = "sqlite+aiosqlite:///./llm_router.db"
_existing_url = (config.get_main_option("sqlalchemy.url") or "").replace("%%", "%")
if not _existing_url or _existing_url == _INI_DEFAULT:
    database_url = _resolved_database_url_from_env().replace("%", "%%")
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
