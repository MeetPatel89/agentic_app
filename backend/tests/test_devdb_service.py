from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.devdb.dialects import detect_backend
from app.devdb.schemas import DevDBQueryRequest
from app.devdb.service import DevDBError, DevDBService


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_sqlite_db(db_url: str) -> None:
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)"))
        await conn.execute(text("INSERT INTO sample (name) VALUES ('alpha'), ('beta')"))
    await engine.dispose()


async def test_devdb_sqlite_list_describe_and_query(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("DEV_DB_TOOLS_ENABLED", "true")
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'devdb.sqlite'}"
    await _seed_sqlite_db(db_url)

    service = DevDBService()

    tables = await service.list_tables(connection_string=db_url)
    assert any(table.name == "sample" for table in tables.tables)

    describe = await service.describe_table(table_name="sample", connection_string=db_url)
    names = [column.name for column in describe.columns]
    assert "id" in names
    assert "name" in names

    query = await service.query(
        DevDBQueryRequest(
            sql="SELECT id, name FROM sample ORDER BY id",
            connection_string=db_url,
            max_rows=10,
        )
    )
    assert query.row_count == 2
    assert query.rows[0][1] == "alpha"
    assert query.rows[1][1] == "beta"


async def test_devdb_rejects_mutating_sql(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("DEV_DB_TOOLS_ENABLED", "true")
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'devdb.sqlite'}"
    service = DevDBService()

    with pytest.raises(DevDBError):
        await service.query(
            DevDBQueryRequest(
                sql="DELETE FROM sample",
                connection_string=db_url,
            )
        )


async def test_devdb_blocks_remote_hosts_when_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEV_DB_TOOLS_ENABLED", "true")
    monkeypatch.setenv("DEV_DB_TOOLS_REQUIRE_LOCALHOST", "true")

    service = DevDBService()
    with pytest.raises(DevDBError):
        await service.list_tables(
            connection_string="postgresql+asyncpg://user:pass@db.example.com:5432/appdb"
        )


def test_detect_backend_paths():
    assert detect_backend("sqlite+aiosqlite:///./llm_router.db") == "sqlite"
    assert detect_backend("postgresql+asyncpg://u:p@localhost:5432/appdb") == "postgresql"
    assert detect_backend("mssql+aioodbc://user:pass@localhost:1433/appdb") == "mssql"
    assert detect_backend("mysql+aiomysql://user:pass@localhost:3306/appdb") == "generic"
