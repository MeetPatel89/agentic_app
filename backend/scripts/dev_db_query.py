from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.devdb.schemas import DevDBQueryRequest
from app.devdb.service import DevDBError, DevDBService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Developer database debugging CLI (read-only).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tables = subparsers.add_parser("tables", help="List database tables")
    tables.add_argument("--connection-string", default=None, help="Optional DB URL override")
    tables.add_argument("--max-tables", type=int, default=1000, help="Maximum number of tables")

    describe = subparsers.add_parser("describe", help="Describe table columns")
    describe.add_argument("table_name", help="Table name")
    describe.add_argument("--schema-name", default=None, help="Schema name (if applicable)")
    describe.add_argument("--connection-string", default=None, help="Optional DB URL override")

    query = subparsers.add_parser("query", help="Run read-only SQL")
    query.add_argument("sql", help="SQL statement (read-only)")
    query.add_argument("--connection-string", default=None, help="Optional DB URL override")
    query.add_argument("--timeout-seconds", type=int, default=15, help="Query timeout")
    query.add_argument("--max-rows", type=int, default=200, help="Maximum rows returned")

    return parser


async def run_cli(args: argparse.Namespace) -> int:
    service = DevDBService()
    try:
        if args.command == "tables":
            result = await service.list_tables(
                connection_string=args.connection_string,
                max_tables=args.max_tables,
            )
        elif args.command == "describe":
            result = await service.describe_table(
                table_name=args.table_name,
                schema_name=args.schema_name,
                connection_string=args.connection_string,
            )
        else:
            result = await service.query(
                DevDBQueryRequest(
                    sql=args.sql,
                    connection_string=args.connection_string,
                    timeout_seconds=args.timeout_seconds,
                    max_rows=args.max_rows,
                )
            )
    except DevDBError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result.model_dump(), indent=2, default=str))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run_cli(args))


if __name__ == "__main__":
    raise SystemExit(main())
