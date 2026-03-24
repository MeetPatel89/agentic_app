from __future__ import annotations

import logging
import sqlite3

import sqlglot
from sqlglot import errors as sqlglot_errors
from sqlglot.dialects import bigquery, mysql, postgres, snowflake, tsql
from sqlglot.dialects import sqlite as sqlite_dialect

from app.nl2sql.schemas import SQLDialect, SQLValidationResult

logger = logging.getLogger(__name__)

_SQLGLOT_DIALECT_MAP: dict[SQLDialect, str] = {
    SQLDialect.postgresql: "postgres",
    SQLDialect.tsql: "tsql",
    SQLDialect.mysql: "mysql",
    SQLDialect.sqlite: "sqlite",
    SQLDialect.bigquery: "bigquery",
    SQLDialect.snowflake: "snowflake",
}

# Ensure dialect modules are importable (side-effect: registers them with sqlglot)
_DIALECT_MODULES = [postgres, tsql, mysql, sqlite_dialect, bigquery, snowflake]


def _get_sqlglot_dialect(dialect: SQLDialect) -> str:
    return _SQLGLOT_DIALECT_MAP.get(dialect, "postgres")


def validate_syntax(sql: str, dialect: SQLDialect) -> SQLValidationResult:
    """Parse SQL with sqlglot to check syntax validity for the given dialect."""
    sg_dialect = _get_sqlglot_dialect(dialect)
    syntax_errors: list[str] = []
    transpiled: str | None = None

    try:
        parsed = sqlglot.parse(sql, read=sg_dialect)
        if not parsed or all(p is None for p in parsed):
            syntax_errors.append("Failed to parse SQL: empty parse result")
        else:
            transpiled = sqlglot.transpile(sql, read=sg_dialect, write=sg_dialect, pretty=True)[0]
    except sqlglot_errors.ParseError as exc:
        syntax_errors.append(f"Syntax error: {exc}")
    except Exception as exc:
        syntax_errors.append(f"Parse error: {exc}")

    return SQLValidationResult(
        is_valid=len(syntax_errors) == 0,
        syntax_errors=syntax_errors,
        transpiled_sql=transpiled,
    )


def validate_with_sandbox(
    sql: str,
    dialect: SQLDialect,
    sandbox_ddl: str,
) -> SQLValidationResult:
    """Full validation: syntax check + execution against in-memory SQLite with user-provided DDL.

    The DDL and query are transpiled to SQLite dialect before execution so that
    dialect-specific syntax (e.g. PostgreSQL, T-SQL) can still be validated
    structurally against an in-memory SQLite database.
    """
    result = validate_syntax(sql, dialect)
    if not result.is_valid:
        return result

    sg_dialect = _get_sqlglot_dialect(dialect)
    conn: sqlite3.Connection | None = None

    try:
        ddl_statements = _transpile_ddl(sandbox_ddl, sg_dialect)
        query_sqlite = sqlglot.transpile(sql, read=sg_dialect, write="sqlite")[0]

        conn = sqlite3.connect(":memory:")
        for stmt in ddl_statements:
            try:
                conn.execute(stmt)
            except sqlite3.Error as exc:
                logger.debug("Sandbox DDL statement failed (non-fatal): %s — %s", stmt[:80], exc)

        try:
            conn.execute(f"EXPLAIN QUERY PLAN {query_sqlite}")
            result.sandbox_execution_success = True
        except sqlite3.Error:
            try:
                conn.execute(query_sqlite)
                result.sandbox_execution_success = True
            except sqlite3.Error as exc:
                result.sandbox_execution_success = False
                result.sandbox_error = str(exc)

    except sqlglot_errors.ParseError as exc:
        result.sandbox_execution_success = False
        result.sandbox_error = f"Transpilation error: {exc}"
    except Exception as exc:
        result.sandbox_execution_success = False
        result.sandbox_error = f"Sandbox error: {exc}"
    finally:
        if conn:
            conn.close()

    return result


def transpile_sql(sql: str, source_dialect: SQLDialect, target_dialect: SQLDialect) -> str:
    """Transpile SQL from one dialect to another using sqlglot."""
    return sqlglot.transpile(
        sql,
        read=_get_sqlglot_dialect(source_dialect),
        write=_get_sqlglot_dialect(target_dialect),
        pretty=True,
    )[0]


def _transpile_ddl(ddl: str, source_dialect: str) -> list[str]:
    """Transpile DDL statements from source dialect to SQLite."""
    results: list[str] = []
    try:
        statements = sqlglot.transpile(ddl, read=source_dialect, write="sqlite")
        results.extend(s for s in statements if s.strip())
    except sqlglot_errors.ParseError:
        for line in ddl.split(";"):
            line = line.strip()
            if line:
                try:
                    transpiled = sqlglot.transpile(line, read=source_dialect, write="sqlite")
                    results.extend(s for s in transpiled if s.strip())
                except Exception:
                    results.append(line)
    return results
