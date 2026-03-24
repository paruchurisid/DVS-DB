from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client(tmp_path: Path):
    api_main = importlib.import_module("api.main")
    importlib.reload(api_main)
    api_main.DB_PATH = str(tmp_path / "audit.db")
    api_main.WAL_PATH = str(tmp_path / "dvsdb.wal")
    api_main.DYNAMIC_TABLES_PATH = str(tmp_path / "dynamic_tables.json")
    with TestClient(api_main.app) as client:
        yield client, tmp_path


def test_query_endpoint_response_contract_success_and_error(api_client) -> None:
    client, _ = api_client
    ok = client.post("/query", json={"query": 'INSERT INTO users VALUES (1, "a", "a@x.com");'})
    assert ok.status_code == 200
    body = ok.json()
    assert "columns" in body and "rows" in body

    bad = client.post("/query", json={"query": "BAD SQL"})
    assert bad.status_code == 400
    assert "error" in bad.json()


def test_query_missing_values_and_duplicate_key(api_client) -> None:
    client, _ = api_client
    missing = client.post("/query", json={"query": 'INSERT INTO users VALUES (1, "only_two_values");'})
    assert missing.status_code == 400
    assert "error" in missing.json()

    first = client.post("/query", json={"query": 'INSERT INTO users VALUES (7, "x", "x@x.com");'})
    assert first.status_code == 200
    dup = client.post("/query", json={"query": 'INSERT INTO users VALUES (7, "x2", "x2@x.com");'})
    assert dup.status_code == 400
    assert "duplicate key" in dup.json()["error"].lower()


def test_invalid_where_and_limit_edge_cases(api_client) -> None:
    client, _ = api_client
    invalid_where = client.post("/query", json={"query": "SELECT * FROM users WHERE nonexist = 1;"})
    assert invalid_where.status_code == 200
    assert invalid_where.json()["rows"] == []

    for q in ["SELECT * FROM users LIMIT 0;", "SELECT * FROM users LIMIT -1;", "SELECT * FROM users LIMIT 999999;"]:
        resp = client.post("/query", json={"query": q})
        assert resp.status_code == 400
        assert "error" in resp.json()


def test_checkpoint_endpoint_contract(api_client) -> None:
    client, _ = api_client
    client.post("/query", json={"query": 'INSERT INTO users VALUES (20, "u", "u@x.com");'})
    ck = client.post("/checkpoint")
    assert ck.status_code == 200
    body = ck.json()
    assert body.get("status") == "ok"


def test_database_reset_endpoint_contract_and_effect(api_client) -> None:
    client, tmp_path = api_client
    client.post("/query", json={"query": 'INSERT INTO users VALUES (33, "r", "r@x.com");'})
    resp = client.delete("/database")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"

    after = client.post("/query", json={"query": "SELECT * FROM users;"})
    assert after.status_code == 200
    assert after.json()["rows"] == []
    assert (tmp_path / "audit.db").exists()


def test_upload_csv_valid_and_invalid_cases(api_client) -> None:
    client, _ = api_client
    csv_ok = "id,name,score\n1,a,10\n2,b,12.5\n"
    preview = client.post("/upload_csv", json={"csv_text": csv_ok, "table_name": "t1", "confirm": False})
    assert preview.status_code == 200
    assert preview.json()["status"] == "preview"
    assert isinstance(preview.json()["columns"], list)

    confirm = client.post("/upload_csv", json={"csv_text": csv_ok, "table_name": "t1", "confirm": True})
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "ok"
    assert confirm.json()["inserted_rows"] == 2

    empty = client.post("/upload_csv", json={"csv_text": "   ", "table_name": "t2", "confirm": False})
    assert empty.status_code == 400
    assert "error" in empty.json()

    invalid = client.post("/upload_csv", json={"csv_text": "no_header_row_data_only", "table_name": "t3", "confirm": False})
    assert invalid.status_code == 400
    assert "error" in invalid.json()

    mixed = client.post(
        "/upload_csv",
        json={"csv_text": "a,b\n1,hello\n2,3.14\nx,world\n", "table_name": "mixed_data", "confirm": True},
    )
    assert mixed.status_code == 200
    assert mixed.json()["status"] == "ok"


def test_tables_lists_users_only_when_non_empty_and_dynamic_tables(api_client) -> None:
    client, _ = api_client
    empty = client.get("/tables")
    assert empty.status_code == 200
    assert empty.json()["tables"] == []

    client.post("/upload_csv", json={"csv_text": "id,v\n1,a\n", "table_name": "dyn_x", "confirm": True})
    with_users = client.get("/tables")
    assert with_users.status_code == 200
    assert "dyn_x" in with_users.json()["tables"]
    assert "users" not in with_users.json()["tables"]

    client.post("/query", json={"query": 'INSERT INTO users VALUES (1, "u", "u@x.com");'})
    with_both = client.get("/tables")
    names = with_both.json()["tables"]
    assert "users" in names and "dyn_x" in names


def test_dynamic_select_where_bad_column_returns_400(api_client) -> None:
    client, _ = api_client
    client.post("/upload_csv", json={"csv_text": "id,v\n1,a\n2,b\n", "table_name": "dyn_y", "confirm": True})
    bad = client.post("/query", json={"query": "SELECT * FROM dyn_y WHERE nosuchcol = 1;"})
    assert bad.status_code == 400
    assert "error" in bad.json()


def test_csv_same_table_name_replaces_and_new_query_data(api_client) -> None:
    client, _ = api_client
    client.post("/upload_csv", json={"csv_text": "id,v\n1,first\n", "table_name": "dyn_z", "confirm": True})
    client.post("/upload_csv", json={"csv_text": "id,v\n9,replaced\n", "table_name": "dyn_z", "confirm": True})
    sel = client.post("/query", json={"query": "SELECT * FROM dyn_z;"})
    assert sel.status_code == 200
    rows = sel.json()["rows"]
    assert len(rows) == 1 and rows[0][0] == 9
