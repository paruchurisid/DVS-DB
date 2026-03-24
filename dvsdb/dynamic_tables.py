from __future__ import annotations

import csv
import io
import json
import os
import re
from dataclasses import dataclass

MAX_CSV_BYTES = 2 * 1024 * 1024  # 2MB safety limit


@dataclass(frozen=True)
class ColumnDef:
    name: str
    type: str


class DynamicTableStore:
    """
    Lightweight JSON-backed dynamic table registry used for CSV ingestion.
    This is intentionally simple and separate from the fixed users/B-tree path.
    """

    def __init__(self, storage_path: str) -> None:
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        if not os.path.exists(storage_path):
            self._write({"tables": {}})

    def reset(self) -> None:
        self._write({"tables": {}})

    def list_tables(self) -> list[str]:
        payload = self._read()
        return sorted(payload["tables"].keys())

    def infer_schema_and_rows(self, csv_text: str, sample_size: int = 25) -> tuple[list[ColumnDef], list[dict[str, str]], int]:
        if not csv_text.strip():
            raise ValueError("CSV file is empty")
        if len(csv_text.encode("utf-8")) > MAX_CSV_BYTES:
            raise ValueError("CSV file too large (max 2MB)")

        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            raise ValueError("CSV missing header row")

        fieldnames = [self._normalize_column_name(name) for name in reader.fieldnames]
        raw_rows: list[dict[str, str]] = []
        for row in reader:
            raw_rows.append({fieldnames[i]: (row.get(reader.fieldnames[i]) or "").strip() for i in range(len(fieldnames))})

        if not raw_rows:
            raise ValueError("CSV has header but no data rows")

        sample_rows = raw_rows[:sample_size]
        columns = [ColumnDef(name=col, type=self._infer_type([r[col] for r in sample_rows])) for col in fieldnames]
        return columns, raw_rows, len(raw_rows)

    def create_or_replace_table(self, table_name: str, columns: list[ColumnDef]) -> None:
        payload = self._read()
        name = self._normalize_table_name(table_name)
        payload["tables"][name] = {
            "columns": [{"name": c.name, "type": c.type} for c in columns],
            "rows": [],
        }
        self._write(payload)

    def insert_rows(self, table_name: str, rows: list[dict[str, str]]) -> int:
        payload = self._read()
        name = self._normalize_table_name(table_name)
        if name not in payload["tables"]:
            raise ValueError(f"Table not found: {name}")
        columns = payload["tables"][name]["columns"]
        col_names = [c["name"] for c in columns]
        typed_rows: list[list[object]] = []
        for row in rows:
            typed_rows.append([self._coerce_value(row.get(col, ""), self._type_of(columns, col)) for col in col_names])
        payload["tables"][name]["rows"].extend(typed_rows)
        self._write(payload)
        return len(typed_rows)

    def select_all(self, table_name: str) -> tuple[list[str], list[list[object]]]:
        payload = self._read()
        name = self._normalize_table_name(table_name)
        if name not in payload["tables"]:
            raise ValueError(f"Table not found: {name}")
        columns = [c["name"] for c in payload["tables"][name]["columns"]]
        rows = payload["tables"][name]["rows"]
        return columns, rows

    def select_where_eq(self, table_name: str, where_col: str, where_value: str) -> tuple[list[str], list[list[object]]]:
        columns, rows = self.select_all(table_name)
        where_col = self._normalize_column_name(where_col)
        if where_col not in columns:
            raise ValueError(f"Unknown column: {where_col}")
        idx = columns.index(where_col)
        out = [r for r in rows if str(r[idx]) == where_value]
        return columns, out

    def _infer_type(self, values: list[str]) -> str:
        non_empty = [v for v in values if v != ""]
        if not non_empty:
            return "TEXT"
        if all(re.fullmatch(r"[+-]?\d+", v) for v in non_empty):
            return "INTEGER"
        if all(re.fullmatch(r"[+-]?\d+(\.\d+)?", v) for v in non_empty):
            return "FLOAT"
        return "TEXT"

    def _coerce_value(self, raw: str, dtype: str) -> object:
        if raw == "":
            return None
        if dtype == "INTEGER":
            if not re.fullmatch(r"[+-]?\d+", raw):
                raise ValueError(f"Type mismatch for INTEGER value: {raw}")
            return int(raw)
        if dtype == "FLOAT":
            if not re.fullmatch(r"[+-]?\d+(\.\d+)?", raw):
                raise ValueError(f"Type mismatch for FLOAT value: {raw}")
            return float(raw)
        return raw

    def _type_of(self, columns: list[dict[str, str]], name: str) -> str:
        for col in columns:
            if col["name"] == name:
                return col["type"]
        return "TEXT"

    def _normalize_table_name(self, name: str) -> str:
        value = (name or "").strip().lower()
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", value):
            raise ValueError("Invalid table name")
        return value

    def _normalize_column_name(self, name: str) -> str:
        value = (name or "").strip().lower().replace(" ", "_")
        value = re.sub(r"[^a-z0-9_]", "", value)
        if not value:
            raise ValueError("Invalid CSV column name")
        return value

    def _read(self) -> dict:
        with open(self.storage_path, "r", encoding="utf-8") as src:
            return json.load(src)

    def _write(self, payload: dict) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as dst:
            json.dump(payload, dst)
