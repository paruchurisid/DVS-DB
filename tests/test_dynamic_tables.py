from __future__ import annotations

from pathlib import Path

from dvsdb.dynamic_tables import ColumnDef, DynamicTableStore


def test_store_initializes_json_in_flat_path(tmp_path: Path) -> None:
    path = tmp_path / "only_file.json"
    store = DynamicTableStore(str(path))
    store.reset()
    assert path.is_file()
    assert store.list_tables() == []


def test_create_or_replace_clears_prior_rows(tmp_path: Path) -> None:
    path = tmp_path / "dyn.json"
    store = DynamicTableStore(str(path))
    cols = [ColumnDef(name="id", type="INTEGER"), ColumnDef(name="v", type="TEXT")]
    store.create_or_replace_table("t", cols)
    assert store.insert_rows("t", [{"id": "1", "v": "a"}]) == 1
    store.create_or_replace_table("t", cols)
    assert store.insert_rows("t", [{"id": "2", "v": "b"}]) == 1
    _, rows = store.select_all("t")
    assert rows == [[2, "b"]]
