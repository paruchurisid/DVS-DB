from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InsertStatement:
    row_id: int
    username: str
    email: str


@dataclass(frozen=True)
class SelectStatement:
    where_column: str | None = None
    where_value: int | str | None = None


@dataclass(frozen=True)
class DeleteStatement:
    where_column: str
    where_value: int | str


@dataclass(frozen=True)
class UpdateStatement:
    set_column: str
    set_value: int | str
    where_column: str
    where_value: int | str


Statement = InsertStatement | SelectStatement | DeleteStatement | UpdateStatement

INSERT_RE = re.compile(
    r"^\s*INSERT\s+INTO\s+users\s+VALUES\s*\(\s*(\d+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)\s*;?\s*$",
    re.IGNORECASE,
)
SELECT_RE = re.compile(r"^\s*SELECT\s+\*\s+FROM\s+users\s*;?\s*$", re.IGNORECASE)
SELECT_WHERE_RE = re.compile(
    r"^\s*SELECT\s+\*\s+FROM\s+users\s+WHERE\s+(\w+)\s*=\s*([^;]+?)\s*;?\s*$",
    re.IGNORECASE,
)
DELETE_RE = re.compile(
    r"^\s*DELETE\s+FROM\s+users\s+WHERE\s+(\w+)\s*=\s*([^;]+?)\s*;?\s*$",
    re.IGNORECASE,
)
UPDATE_RE = re.compile(
    r"^\s*UPDATE\s+users\s+SET\s+(\w+)\s*=\s*([^;]+?)\s+WHERE\s+(\w+)\s*=\s*([^;]+?)\s*;?\s*$",
    re.IGNORECASE,
)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    return value


def _parse_value(value: str) -> int | str:
    stripped = _strip_quotes(value.strip())
    if stripped.isdigit():
        return int(stripped)
    return stripped


def parse_sql(sql: str) -> Statement:
    if SELECT_RE.match(sql):
        return SelectStatement()
    m = SELECT_WHERE_RE.match(sql)
    if m:
        return SelectStatement(where_column=m.group(1).lower(), where_value=_parse_value(m.group(2)))
    m = INSERT_RE.match(sql)
    if m:
        row_id = int(m.group(1))
        username = _strip_quotes(m.group(2))
        email = _strip_quotes(m.group(3))
        return InsertStatement(row_id=row_id, username=username, email=email)
    m = DELETE_RE.match(sql)
    if m:
        return DeleteStatement(where_column=m.group(1).lower(), where_value=_parse_value(m.group(2)))
    m = UPDATE_RE.match(sql)
    if m:
        return UpdateStatement(
            set_column=m.group(1).lower(),
            set_value=_parse_value(m.group(2)),
            where_column=m.group(3).lower(),
            where_value=_parse_value(m.group(4)),
        )
    raise ValueError(
        "Unrecognized command. Supported: INSERT INTO users VALUES (...), SELECT * FROM users [WHERE ...], DELETE FROM users WHERE ..., UPDATE users SET ... WHERE ..."
    )


def statement_to_sql(statement: Statement) -> str:
    if isinstance(statement, InsertStatement):
        return f'INSERT INTO users VALUES ({statement.row_id}, "{statement.username}", "{statement.email}");'
    if isinstance(statement, SelectStatement):
        if statement.where_column is None:
            return "SELECT * FROM users;"
        val = f'"{statement.where_value}"' if isinstance(statement.where_value, str) else statement.where_value
        return f"SELECT * FROM users WHERE {statement.where_column} = {val};"
    if isinstance(statement, DeleteStatement):
        val = f'"{statement.where_value}"' if isinstance(statement.where_value, str) else statement.where_value
        return f"DELETE FROM users WHERE {statement.where_column} = {val};"
    if isinstance(statement, UpdateStatement):
        set_val = f'"{statement.set_value}"' if isinstance(statement.set_value, str) else statement.set_value
        where_val = f'"{statement.where_value}"' if isinstance(statement.where_value, str) else statement.where_value
        return f"UPDATE users SET {statement.set_column} = {set_val} WHERE {statement.where_column} = {where_val};"
    raise ValueError("Unsupported statement")
