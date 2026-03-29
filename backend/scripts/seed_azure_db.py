"""Seed Azure SQL with the Contoso Retail Operations enterprise sample schema.

Usage:
    cd backend
    uv run python -m scripts.seed_azure_db              # Create schema + data
    uv run python -m scripts.seed_azure_db --dry-run    # Parse & print batches without executing
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pyodbc

# ---------------------------------------------------------------------------
# Connection helpers — reuse credential resolution from app.config
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SQL_FILE = _SCRIPTS_DIR / "seed_enterprise_schema.sql"


def _build_connection_string() -> str:
    """Build a pyodbc connection string from the app's .env settings."""
    # Import here so the module stays lightweight for --help / --dry-run
    sys.path.insert(0, str(_SCRIPTS_DIR.parent))
    from app.config import get_settings

    s = get_settings()
    if not (s.database_host and s.database_name and s.database_user and s.database_password):
        raise SystemExit(
            "ERROR: Database component settings (DATABASE_HOST, DATABASE_NAME, "
            "DATABASE_USER, DATABASE_PASSWORD) must be set in .env"
        )

    escaped_password = s.database_password.replace("}", "}}")
    port = s.database_port or 1433
    parts = [
        "Driver={ODBC Driver 18 for SQL Server}",
        f"Server=tcp:{s.database_host},{port}",
        f"Database={s.database_name}",
        f"Uid={s.database_user}",
        f"Pwd={{{escaped_password}}}",
        "Encrypt=yes",
        "TrustServerCertificate=no",
        "Connection Timeout=60",
    ]
    return ";".join(parts) + ";"


def _split_batches(sql: str) -> list[str]:
    """Split a T-SQL script on GO batch separators.

    GO must appear on its own line (case-insensitive, optional whitespace).
    """
    batches: list[str] = []
    current: list[str] = []
    for line in sql.splitlines():
        if line.strip().upper() == "GO":
            batch_text = "\n".join(current).strip()
            if batch_text:
                batches.append(batch_text)
            current = []
        else:
            current.append(line)
    # Final batch (if no trailing GO)
    remaining = "\n".join(current).strip()
    if remaining:
        batches.append(remaining)
    return batches


def _batch_preview(batch: str, max_len: int = 120) -> str:
    """Return a short one-line preview of a SQL batch for progress logging."""
    first_line = ""
    for line in batch.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            first_line = stripped
            break
    if not first_line:
        # All comments
        first_line = batch.splitlines()[0].strip() if batch.strip() else "(empty)"
    if len(first_line) > max_len:
        return first_line[:max_len] + "..."
    return first_line


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Azure SQL with enterprise sample data")
    parser.add_argument("--dry-run", action="store_true", help="Parse and list batches without executing")
    parser.add_argument("--sql-file", type=Path, default=_SQL_FILE, help="Path to the seed SQL file")
    args = parser.parse_args()

    sql_path: Path = args.sql_file
    if not sql_path.exists():
        raise SystemExit(f"ERROR: SQL file not found: {sql_path}")

    sql_text = sql_path.read_text(encoding="utf-8")
    batches = _split_batches(sql_text)
    print(f"Parsed {len(batches)} SQL batches from {sql_path.name}")

    if args.dry_run:
        for i, batch in enumerate(batches, 1):
            print(f"  [{i:3d}] {_batch_preview(batch)}")
        print("\n(dry run — nothing executed)")
        return

    conn_str = _build_connection_string()
    # Mask password in log output
    safe_conn = conn_str.split("Pwd=")[0] + "Pwd={***};" if "Pwd=" in conn_str else conn_str
    print(f"Connecting: {safe_conn[:120]}...")

    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    print(f"Connected. Executing {len(batches)} batches...\n")
    t0 = time.perf_counter()
    failed = 0

    for i, batch in enumerate(batches, 1):
        preview = _batch_preview(batch)
        try:
            cursor.execute(batch)
            # Consume any result sets (e.g. the final summary SELECT)
            while True:
                try:
                    rows = cursor.fetchall()
                    if rows:
                        # Print summary table if it looks like the final stats query
                        cols = [desc[0] for desc in cursor.description] if cursor.description else []
                        if cols and "table" in [c.lower() for c in cols]:
                            print(f"\n{'Table':<35} {'Rows':>8}")
                            print("-" * 45)
                            for row in rows:
                                print(f"  {row[0]:<33} {row[1]:>6}")
                            print()
                except pyodbc.ProgrammingError:
                    break
                if not cursor.nextset():
                    break
            print(f"  [{i:3d}/{len(batches)}] OK   {preview}")
        except pyodbc.Error as exc:
            failed += 1
            print(f"  [{i:3d}/{len(batches)}] FAIL {preview}")
            print(f"           {exc}")

    elapsed = time.perf_counter() - t0
    cursor.close()
    conn.close()

    print(f"\nDone in {elapsed:.1f}s — {len(batches) - failed}/{len(batches)} batches succeeded", end="")
    if failed:
        print(f", {failed} failed")
        sys.exit(1)
    else:
        print()


if __name__ == "__main__":
    main()
