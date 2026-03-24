from __future__ import annotations

from dataclasses import dataclass
import logging

from dvsdb.btree import DuplicateKeyError
from dvsdb.models import Row
from dvsdb.parser import DeleteStatement, InsertStatement, SelectStatement, Statement, UpdateStatement
from dvsdb.table import Table

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[object]]


def execute_statement(table: Table, statement: Statement) -> QueryResult:
    logger.info("query.execute statement=%s", type(statement).__name__)
    if isinstance(statement, InsertStatement):
        row = Row(id=statement.row_id, username=statement.username, email=statement.email)
        table.insert_transactional(row)
        return QueryResult(columns=["status"], rows=[["OK"]])
    if isinstance(statement, SelectStatement):
        rows = table.select_where(statement.where_column, statement.where_value)
        return QueryResult(
            columns=["id", "username", "email"],
            rows=[[r.id, r.username, r.email] for r in rows],
        )
    if isinstance(statement, DeleteStatement):
        deleted = table.delete_where(statement.where_column, statement.where_value)
        return QueryResult(columns=["deleted_rows"], rows=[[deleted]])
    if isinstance(statement, UpdateStatement):
        updated = table.update_where(
            statement.set_column,
            statement.set_value,
            statement.where_column,
            statement.where_value,
        )
        return QueryResult(columns=["updated_rows"], rows=[[updated]])
    raise ValueError("Unsupported statement type")


def safe_execute_statement(table: Table, statement: Statement) -> QueryResult:
    try:
        return execute_statement(table, statement)
    except DuplicateKeyError as exc:
        logger.warning("query.duplicate_key error=%s", exc)
        raise ValueError(str(exc)) from exc
