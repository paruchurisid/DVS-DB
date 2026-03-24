from __future__ import annotations

from pathlib import Path

import pytest

from dvsdb.cursor import DVSCursor
from dvsdb.models import Row
from dvsdb.table import DuplicateKeyError, Table


def test_cursor_commit_applies_queued_changes_atomically(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "cursor.db"))
    cur = DVSCursor(table)
    cur.begin_transaction()
    cur.queue_insert(Row(id=1, username="sid", email="sid@x.com"))
    cur.queue_insert(Row(id=2, username="jane", email="jane@x.com"))
    cur.commit()
    rows = table.select_all()
    table.close()
    assert [r.id for r in rows] == [1, 2]


def test_cursor_rollback_discards_queued_changes(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "cursor.db"))
    cur = DVSCursor(table)
    cur.begin_transaction()
    cur.queue_insert(Row(id=10, username="x", email="x@x.com"))
    cur.rollback()
    assert table.select_all() == []
    table.close()


def test_cursor_validates_uniqueness_before_queue(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "cursor.db"))
    table.insert_transactional(Row(id=5, username="a", email="a@x.com"))
    cur = DVSCursor(table)
    cur.begin_transaction()
    with pytest.raises(DuplicateKeyError):
        cur.queue_insert(Row(id=5, username="dup", email="dup@x.com"))
    cur.rollback()
    table.close()


def test_cursor_scan_fetchone_btree_order(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "cursor.db"))
    table.insert_transactional(Row(id=3, username="u3", email="u3@x.com"))
    table.insert_transactional(Row(id=1, username="u1", email="u1@x.com"))
    table.insert_transactional(Row(id=2, username="u2", email="u2@x.com"))
    cur = DVSCursor(table)
    cur.execute_scan()
    out = []
    while True:
        row = cur.fetchone()
        if row is None:
            break
        out.append(row.id)
    table.close()
    assert out == [1, 2, 3]


def test_cursor_update_delete_and_read_view_in_tx(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "cursor.db"))
    table.insert_transactional(Row(id=7, username="before", email="before@x.com"))
    table.insert_transactional(Row(id=8, username="keep", email="keep@x.com"))

    cur = DVSCursor(table)
    cur.begin_transaction()
    cur.queue_update(7, username="after")
    cur.queue_delete(8)
    r7 = cur.search_by_key(7)
    visible_ids = [r.id for r in cur.iter_rows()]
    cur.commit()
    rows = table.select_all()
    table.close()

    assert r7 is not None and r7.username == "after"
    assert visible_ids == [7]
    assert [r.id for r in rows] == [7]


def test_cursor_rejects_invalid_state_calls(tmp_path: Path) -> None:
    table = Table(str(tmp_path / "cursor.db"))
    cur = DVSCursor(table)
    with pytest.raises(RuntimeError):
        cur.commit()
    with pytest.raises(RuntimeError):
        cur.queue_delete(1)
    table.close()
