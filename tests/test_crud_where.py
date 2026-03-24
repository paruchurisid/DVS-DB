from __future__ import annotations

from pathlib import Path

from dvsdb.models import Row
from dvsdb.parser import parse_sql
from dvsdb.query_service import execute_statement
from dvsdb.table import Table


def test_select_where_id_uses_lookup_path_and_returns_single(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "crud.db"))
    table.insert_transactional(Row(id=1, username="a", email="a@x.com"))
    table.insert_transactional(Row(id=2, username="b", email="b@x.com"))

    stmt = parse_sql("SELECT * FROM users WHERE id = 2;")
    result = execute_statement(table, stmt)
    table.close()

    assert result.columns == ["id", "username", "email"]
    assert result.rows == [[2, "b", "b@x.com"]]


def test_update_where_id_changes_single_row(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "crud.db"))
    table.insert_transactional(Row(id=10, username="old", email="old@x.com"))
    stmt = parse_sql('UPDATE users SET username = "newname" WHERE id = 10;')
    result = execute_statement(table, stmt)
    rows = table.select_where("id", 10)
    table.close()

    assert result.rows == [[1]]
    assert rows[0].username == "newname"


def test_delete_soft_delete_and_select_ignores_deleted(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "crud.db"))
    table.insert_transactional(Row(id=20, username="u20", email="u20@x.com"))
    table.insert_transactional(Row(id=21, username="u21", email="u21@x.com"))

    delete_stmt = parse_sql("DELETE FROM users WHERE id = 20;")
    delete_result = execute_statement(table, delete_stmt)
    visible_rows = table.select_all()
    all_rows = table.select_all(include_deleted=True)
    table.close()

    assert delete_result.rows == [[1]]
    assert [r.id for r in visible_rows] == [21]
    assert any(r.id == 20 and r.is_deleted for r in all_rows)


def test_where_full_scan_on_non_indexed_column(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "crud.db"))
    table.insert_transactional(Row(id=31, username="same", email="a@x.com"))
    table.insert_transactional(Row(id=32, username="same", email="b@x.com"))
    table.insert_transactional(Row(id=33, username="other", email="c@x.com"))

    stmt = parse_sql('SELECT * FROM users WHERE username = "same";')
    result = execute_statement(table, stmt)
    table.close()

    assert len(result.rows) == 2
    assert [r[0] for r in result.rows] == [31, 32]
