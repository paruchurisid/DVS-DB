from __future__ import annotations

from dvsdb.btree import DuplicateKeyError
from dvsdb.models import Row
from dvsdb.parser import DeleteStatement, InsertStatement, SelectStatement, Statement, UpdateStatement
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
            rows = self.table.select_where(statement.where_column, statement.where_value)
            return "\n".join(f"{r.id}\t{r.username}\t{r.email}" for r in rows) if rows else "(empty)"
        if isinstance(statement, DeleteStatement):
            deleted = self.table.delete_where(statement.where_column, statement.where_value)
            return f"OK (deleted {deleted})"
        if isinstance(statement, UpdateStatement):
            updated = self.table.update_where(
                statement.set_column,
                statement.set_value,
                statement.where_column,
                statement.where_value,
            )
            return f"OK (updated {updated})"
        raise ValueError("Unsupported statement type")


def run_statement(engine: ExecutionEngine, statement: Statement) -> str:
    try:
        return engine.execute(statement)
    except DuplicateKeyError as exc:
        return f"ERROR: {exc}"
    except ValueError as exc:
        return f"ERROR: {exc}"
