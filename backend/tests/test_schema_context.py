from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.devdb.service import DevDBService
from app.nl2sql.schema_context.formatters import (
    format_compact_ddl,
    format_concise_notation,
    format_structured_catalog,
)
from app.nl2sql.schema_context.introspector import SchemaIntrospector
from app.nl2sql.schema_context.models import (
    ColumnDetail,
    ForeignKeyInfo,
    SchemaCatalog,
    SchemaContextFormat,
    TableDetail,
)
from app.nl2sql.schema_context.service import SchemaContextService


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _sample_catalog() -> SchemaCatalog:
    employees = TableDetail(
        name="employees",
        schema_name="hr",
        columns=[
            ColumnDetail(name="id", data_type="INTEGER", nullable=False, is_primary_key=True),
            ColumnDetail(name="name", data_type="TEXT", nullable=False),
            ColumnDetail(name="manager_id", data_type="INTEGER", nullable=True),
            ColumnDetail(name="department_id", data_type="INTEGER", nullable=False),
        ],
        foreign_keys=[
            ForeignKeyInfo(
                column_name="department_id",
                referenced_schema="hr",
                referenced_table="departments",
                referenced_column="id",
            ),
            ForeignKeyInfo(
                column_name="manager_id",
                referenced_schema="hr",
                referenced_table="employees",
                referenced_column="id",
            ),
        ],
    )
    departments = TableDetail(
        name="departments",
        schema_name="hr",
        columns=[
            ColumnDetail(name="id", data_type="INTEGER", nullable=False, is_primary_key=True),
            ColumnDetail(name="name", data_type="TEXT", nullable=False),
        ],
    )
    return SchemaCatalog(backend="sqlite", tables=[employees, departments])


class TestFormatters:
    def test_compact_ddl_includes_pk_fk_and_relationships(self):
        text = format_compact_ddl(_sample_catalog())
        assert "CREATE TABLE hr.employees" in text
        assert "id INTEGER PRIMARY KEY" in text
        assert "REFERENCES hr.departments(id)" in text
        assert "-- Relationships:" in text
        assert "-- hr.employees.manager_id -> hr.employees.id (self-referencing)" in text

    def test_structured_catalog_has_markdown_header(self):
        text = format_structured_catalog(_sample_catalog())
        assert "### hr.employees" in text
        assert "| Column | Type | PK | FK | Nullable | Description |" in text
        assert "→ hr.departments.id" in text

    def test_concise_notation_one_line_per_table(self):
        text = format_concise_notation(_sample_catalog())
        lines = [line for line in text.splitlines() if line.strip()]
        assert len(lines) == 2
        assert lines[0].startswith("hr.employees(")
        assert "id*" in lines[0]
        assert "manager_id->hr.employees" in lines[0]


class TestIntrospector:
    async def test_introspects_sqlite_with_fks(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        monkeypatch.setenv("DEV_DB_TOOLS_ENABLED", "true")
        db_url = f"sqlite+aiosqlite:///{tmp_path / 'schema.sqlite'}"

        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
            await conn.execute(
                text(
                    "CREATE TABLE employees ("
                    "id INTEGER PRIMARY KEY, "
                    "name TEXT NOT NULL, "
                    "department_id INTEGER NOT NULL, "
                    "FOREIGN KEY(department_id) REFERENCES departments(id))"
                )
            )
        await engine.dispose()

        introspector = SchemaIntrospector(DevDBService())
        catalog = await introspector.introspect(connection_string=db_url)

        assert catalog.backend == "sqlite"
        names = {t.name for t in catalog.tables}
        assert {"employees", "departments"} <= names

        employees = next(t for t in catalog.tables if t.name == "employees")
        pk_cols = [c.name for c in employees.columns if c.is_primary_key]
        assert pk_cols == ["id"]
        assert len(employees.foreign_keys) == 1
        assert employees.foreign_keys[0].referenced_table == "departments"

    async def test_table_filter_limits_result(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        monkeypatch.setenv("DEV_DB_TOOLS_ENABLED", "true")
        db_url = f"sqlite+aiosqlite:///{tmp_path / 'filter.sqlite'}"

        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE keep (id INTEGER PRIMARY KEY)"))
            await conn.execute(text("CREATE TABLE drop_me (id INTEGER PRIMARY KEY)"))
        await engine.dispose()

        catalog = await SchemaIntrospector(DevDBService()).introspect(
            connection_string=db_url,
            table_filter=["keep"],
        )
        assert [t.name for t in catalog.tables] == ["keep"]


class TestSchemaContextService:
    async def test_generate_returns_compact_ddl_by_default(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        monkeypatch.setenv("DEV_DB_TOOLS_ENABLED", "true")
        db_url = f"sqlite+aiosqlite:///{tmp_path / 'svc.sqlite'}"

        engine = create_async_engine(db_url, echo=False)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)"))
        await engine.dispose()

        # override the default DevDBService so we can inject the test connection string
        svc = SchemaContextService()
        catalog = await svc._introspector.introspect(connection_string=db_url)
        response = svc.format_catalog(catalog)

        assert response.format == SchemaContextFormat.compact_ddl
        assert "CREATE TABLE sample" in response.schema_text
        assert response.table_count == 1
        assert response.estimated_tokens > 0
