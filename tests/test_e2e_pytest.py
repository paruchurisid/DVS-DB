from __future__ import annotations

import importlib
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dvsdb.models import Row
from dvsdb.table import DuplicateKeyError, Table


@pytest.fixture
def db_paths(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "test.db"
    wal_path = tmp_path / "dvsdb.wal"
    return db_path, wal_path


def test_basic_insert_select(db_paths: tuple[Path, Path]) -> None:
    db_path, _ = db_paths
    table = Table(str(db_path))
    rows = [
        Row(id=1, username="sid", email="sid@email.com"),
        Row(id=2, username="jane", email="jane@email.com"),
        Row(id=3, username="john", email="john@email.com"),
    ]
    for row in rows:
        table.insert_transactional(row)
    out = table.select_all()
    table.close()
    assert out == rows


def test_persistence_across_restart(db_paths: tuple[Path, Path]) -> None:
    db_path, _ = db_paths
    table = Table(str(db_path))
    for i in range(1, 6):
        table.insert_transactional(Row(id=i, username=f"user{i}", email=f"user{i}@x.com"))
    table.close()

    reopened = Table(str(db_path))
    out = reopened.select_all()
    reopened.close()
    assert [r.id for r in out] == [1, 2, 3, 4, 5]


def test_wal_logging_contains_begin_and_commit(db_paths: tuple[Path, Path]) -> None:
    db_path, wal_path = db_paths
    table = Table(str(db_path))
    row = Row(id=11, username="wal_user", email="wal_user@x.com")
    operation = table._row_to_insert_sql(row)

    table.begin_transaction()
    table.log_operation(operation)

    wal_text = wal_path.read_text(encoding="utf-8")
    assert "BEGIN" in wal_text
    assert operation in wal_text
    assert table.get(11) is None

    table.insert(row)
    table.pager.flush_all()
    table.commit()
    wal_text_after = wal_path.read_text(encoding="utf-8")
    assert "COMMIT" in wal_text_after
    table.close()


def test_crash_recovery_ignores_uncommitted(db_paths: tuple[Path, Path]) -> None:
    db_path, wal_path = db_paths
    wal_path.write_text('BEGIN\nINSERT INTO users VALUES (21, "ghost", "ghost@x.com");\n', encoding="utf-8")

    table = Table(str(db_path))
    rows = table.select_all()
    table.close()
    assert [r.id for r in rows] == []


def test_wal_recovery_replays_committed(db_paths: tuple[Path, Path]) -> None:
    db_path, wal_path = db_paths
    wal_path.write_text(
        'BEGIN\nINSERT INTO users VALUES (22, "recover", "recover@x.com");\nCOMMIT\n',
        encoding="utf-8",
    )

    table = Table(str(db_path))
    rows = table.select_all()
    table.close()
    assert [r.id for r in rows] == [22]


def test_checkpoint_flushes_and_truncates_wal(db_paths: tuple[Path, Path]) -> None:
    db_path, wal_path = db_paths
    table = Table(str(db_path))
    for i in range(30, 35):
        table.insert_transactional(Row(id=i, username=f"u{i}", email=f"u{i}@x.com"))

    assert wal_path.exists()
    assert wal_path.read_text(encoding="utf-8").strip() != ""

    table.checkpoint_wal()
    assert wal_path.read_text(encoding="utf-8") == ""

    table.insert_transactional(Row(id=40, username="post_ckpt", email="post_ckpt@x.com"))
    table.close()

    reopened = Table(str(db_path))
    out = reopened.select_all()
    reopened.close()
    assert [r.id for r in out] == [30, 31, 32, 33, 34, 40]


def test_btree_integrity_with_many_rows(db_paths: tuple[Path, Path]) -> None:
    db_path, _ = db_paths
    table = Table(str(db_path))
    total = 500
    for i in range(total):
        table.insert_transactional(Row(id=i, username=f"user_{i}", email=f"user_{i}@x.com"))

    rows = table.select_all()
    assert len(rows) == total
    assert rows[0].id == 0
    assert rows[-1].id == total - 1
    by_id = {row.id: row for row in rows}

    sample_ids = random.sample(range(total), 30)
    for i in sample_ids:
        row = by_id.get(i)
        assert row is not None
        assert row.id == i
        assert row.username == f"user_{i}"
    table.close()


@pytest.fixture
def api_client(tmp_path: Path):
    api_main = importlib.import_module("api.main")
    api_main.DB_PATH = str(tmp_path / "api_test.db")
    importlib.reload(api_main)
    api_main.DB_PATH = str(tmp_path / "api_test.db")

    with TestClient(api_main.app) as client:
        yield client, tmp_path / "dvsdb.wal"


def test_query_endpoint_insert_select_and_error(api_client) -> None:
    client, _ = api_client
    insert_resp = client.post("/query", json={"query": 'INSERT INTO users VALUES (1, "sid", "sid@email.com");'})
    assert insert_resp.status_code == 200
    assert insert_resp.json()["rows"][0][0] == "OK"

    select_resp = client.post("/query", json={"query": "SELECT * FROM users;"})
    assert select_resp.status_code == 200
    assert select_resp.json()["columns"] == ["id", "username", "email"]
    assert select_resp.json()["rows"] == [[1, "sid", "sid@email.com"]]

    bad_resp = client.post("/query", json={"query": "SELCT * FRM users;"})
    assert bad_resp.status_code == 400
    assert "error" in bad_resp.json()


def test_checkpoint_endpoint_clears_wal(api_client) -> None:
    client, wal_path = api_client
    for i in range(5):
        resp = client.post(
            "/query",
            json={"query": f'INSERT INTO users VALUES ({100 + i}, "u{i}", "u{i}@x.com");'},
        )
        assert resp.status_code == 200

    assert wal_path.exists()
    assert wal_path.read_text(encoding="utf-8").strip() != ""

    ckpt = client.post("/checkpoint")
    assert ckpt.status_code == 200
    assert ckpt.json()["status"] == "ok"
    assert wal_path.read_text(encoding="utf-8") == ""


def test_edge_cases_long_strings_and_duplicate_id(db_paths: tuple[Path, Path]) -> None:
    db_path, _ = db_paths
    table = Table(str(db_path))
    row = Row(id=999, username="u" * 32, email="e" * 243 + "@x.com")
    table.insert_transactional(row)
    fetched = table.get(999)
    assert fetched == row

    with pytest.raises(DuplicateKeyError):
        table.insert_transactional(row)
    table.close()
