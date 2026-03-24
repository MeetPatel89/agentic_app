from __future__ import annotations

from app.nl2sql.sandbox import transpile_sql, validate_syntax, validate_with_sandbox
from app.nl2sql.schemas import SQLDialect


class TestValidateSyntax:
    def test_valid_postgresql_select(self):
        result = validate_syntax("SELECT id, name FROM users WHERE active = true", SQLDialect.postgresql)
        assert result.is_valid is True
        assert result.syntax_errors == []
        assert result.transpiled_sql is not None

    def test_valid_tsql_top(self):
        result = validate_syntax("SELECT TOP 10 id, name FROM users", SQLDialect.tsql)
        assert result.is_valid is True

    def test_valid_mysql_backtick_identifiers(self):
        result = validate_syntax("SELECT `id`, `name` FROM `users`", SQLDialect.mysql)
        assert result.is_valid is True

    def test_invalid_sql_syntax_error(self):
        result = validate_syntax("SELEC id FROM users", SQLDialect.postgresql)
        assert result.is_valid is False
        assert len(result.syntax_errors) > 0

    def test_empty_sql(self):
        result = validate_syntax("", SQLDialect.postgresql)
        assert result.is_valid is False

    def test_cte_query(self):
        sql = """
        WITH active_users AS (
            SELECT id, name FROM users WHERE active = true
        )
        SELECT * FROM active_users ORDER BY name
        """
        result = validate_syntax(sql, SQLDialect.postgresql)
        assert result.is_valid is True

    def test_join_query(self):
        sql = """
        SELECT u.id, u.name, o.total
        FROM users u
        INNER JOIN orders o ON u.id = o.user_id
        WHERE o.total > 100
        """
        result = validate_syntax(sql, SQLDialect.postgresql)
        assert result.is_valid is True


class TestValidateWithSandbox:
    SAMPLE_DDL = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT,
        active INTEGER DEFAULT 1
    );
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        total REAL,
        created_at TEXT
    );
    """

    def test_valid_query_against_schema(self):
        result = validate_with_sandbox(
            "SELECT id, name FROM users WHERE active = 1",
            SQLDialect.postgresql,
            self.SAMPLE_DDL,
        )
        assert result.is_valid is True
        assert result.sandbox_execution_success is True

    def test_invalid_column_reference(self):
        result = validate_with_sandbox(
            "SELECT nonexistent_column FROM users",
            SQLDialect.postgresql,
            self.SAMPLE_DDL,
        )
        assert result.is_valid is True  # syntax is valid
        assert result.sandbox_execution_success is False
        assert result.sandbox_error is not None

    def test_join_against_schema(self):
        sql = """
        SELECT u.name, o.total
        FROM users u
        JOIN orders o ON u.id = o.user_id
        """
        result = validate_with_sandbox(sql, SQLDialect.postgresql, self.SAMPLE_DDL)
        assert result.is_valid is True
        assert result.sandbox_execution_success is True

    def test_syntax_error_skips_sandbox(self):
        result = validate_with_sandbox(
            "SELEC id FROM users",
            SQLDialect.postgresql,
            self.SAMPLE_DDL,
        )
        assert result.is_valid is False
        assert result.sandbox_execution_success is None


class TestTranspileSQL:
    def test_postgresql_to_mysql(self):
        sql = "SELECT id FROM users LIMIT 10"
        result = transpile_sql(sql, SQLDialect.postgresql, SQLDialect.mysql)
        assert "LIMIT" in result

    def test_postgresql_to_tsql(self):
        sql = "SELECT id FROM users LIMIT 10"
        result = transpile_sql(sql, SQLDialect.postgresql, SQLDialect.tsql)
        assert "TOP" in result or "FETCH" in result
