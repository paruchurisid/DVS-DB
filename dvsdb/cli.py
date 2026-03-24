from __future__ import annotations

import argparse

from dvsdb.engine import ExecutionEngine, run_statement
from dvsdb.parser import parse_sql
from dvsdb.table import Table


def repl(db_path: str) -> None:
    table = Table(db_path)
    engine = ExecutionEngine(table)
    print("DvsDB shell. Enter SQL or .exit")
    try:
        while True:
            try:
                raw = input("dvsdb> ").strip()
            except EOFError:
                print()
                break
            if not raw:
                continue
            if raw.lower() in (".exit", ".quit"):
                break
            try:
                stmt = parse_sql(raw)
                print(run_statement(engine, stmt))
            except Exception as exc:  # broad so REPL remains interactive
                print(f"ERROR: {exc}")
    finally:
        table.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="DvsDB embedded database shell")
    parser.add_argument("database", nargs="?", default="dvsdb.db", help="Path to .db file")
    args = parser.parse_args()
    repl(args.database)


if __name__ == "__main__":
    main()
