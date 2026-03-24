from __future__ import annotations

from dvsdb.btree import DuplicateKeyError
from dvsdb.models import Row
from dvsdb.parser import InsertStatement, SelectStatement, Statement
from dvsdb.table import Table


class ExecutionEngine:
    def __init__(self, table: Table) -> None:
        self.table = table

    def execute(self, statement: Statement) -> str:
        if isinstance(statement, InsertStatement):
            row = Row(id=statement.row_id, username=statement.username, email=statement.email)
            self.table.insert_transactional(row)
            return "OK"
        if isinstance(statement, SelectStatement):
            rows = self.table.select_all()
            return "\n".join(f"{r.id}\t{r.username}\t{r.email}" for r in rows) if rows else "(empty)"
        raise ValueError("Unsupported statement type")


def run_statement(engine: ExecutionEngine, statement: Statement) -> str:
    try:
        return engine.execute(statement)
    except DuplicateKeyError as exc:
        return f"ERROR: {exc}"
    except ValueError as exc:
        return f"ERROR: {exc}"
