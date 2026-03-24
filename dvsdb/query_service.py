from __future__ import annotations

from dataclasses import dataclass

from dvsdb.btree import DuplicateKeyError
from dvsdb.models import Row
from dvsdb.parser import InsertStatement, SelectStatement, Statement
from dvsdb.table import Table


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[object]]


def execute_statement(table: Table, statement: Statement) -> QueryResult:
    if isinstance(statement, InsertStatement):
        row = Row(id=statement.row_id, username=statement.username, email=statement.email)
        table.insert_transactional(row)
        return QueryResult(columns=["status"], rows=[["OK"]])
    if isinstance(statement, SelectStatement):
        rows = table.select_all()
        return QueryResult(
            columns=["id", "username", "email"],
            rows=[[r.id, r.username, r.email] for r in rows],
        )
    raise ValueError("Unsupported statement type")


def safe_execute_statement(table: Table, statement: Statement) -> QueryResult:
    try:
        return execute_statement(table, statement)
    except DuplicateKeyError as exc:
        raise ValueError(str(exc)) from exc
