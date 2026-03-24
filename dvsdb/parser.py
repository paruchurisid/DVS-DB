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
    pass


Statement = InsertStatement | SelectStatement

INSERT_RE = re.compile(
    r"^\s*INSERT\s+INTO\s+users\s+VALUES\s*\(\s*(\d+)\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)\s*;?\s*$",
    re.IGNORECASE,
)
SELECT_RE = re.compile(r"^\s*SELECT\s+\*\s+FROM\s+users\s*;?\s*$", re.IGNORECASE)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    return value


def parse_sql(sql: str) -> Statement:
    if SELECT_RE.match(sql):
        return SelectStatement()
    m = INSERT_RE.match(sql)
    if m:
        row_id = int(m.group(1))
        username = _strip_quotes(m.group(2))
        email = _strip_quotes(m.group(3))
        return InsertStatement(row_id=row_id, username=username, email=email)
    raise ValueError("Unrecognized command. Supported: INSERT INTO users VALUES (...), SELECT * FROM users")
