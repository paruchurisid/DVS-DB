from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional

from dvsdb.models import Row
from dvsdb.serializer import serialize_row
from dvsdb.table import DuplicateKeyError, Table


@dataclass(frozen=True)
class InsertOp:
    row: Row

    def to_sql(self) -> str:
        username = self.row.username.replace('"', '\\"')
        email = self.row.email.replace('"', '\\"')
        return f'INSERT INTO users VALUES ({self.row.id}, "{username}", "{email}");'

    def apply(self, table: Table) -> None:
        table.insert(self.row)


@dataclass(frozen=True)
class UpdateOp:
    row_id: int
    updates: dict[str, str]

    def to_sql(self) -> str:
        if "username" in self.updates:
            value = self.updates["username"].replace('"', '\\"')
            return f'UPDATE users SET username = "{value}" WHERE id = {self.row_id};'
        if "email" in self.updates:
            value = self.updates["email"].replace('"', '\\"')
            return f'UPDATE users SET email = "{value}" WHERE id = {self.row_id};'
        raise ValueError("No supported update fields")

    def apply(self, table: Table) -> None:
        for col, val in self.updates.items():
            table._update_where_non_tx(col, val, "id", self.row_id)


@dataclass(frozen=True)
class DeleteOp:
    row_id: int

    def to_sql(self) -> str:
        return f"DELETE FROM users WHERE id = {self.row_id};"

    def apply(self, table: Table) -> None:
        table._delete_where_non_tx("id", self.row_id)


class DVSCursor:
    """
    High-level table cursor abstraction with queued transactional CRUD operations.

    Current scope:
    - single-table users cursor
    - single-threaded transaction model
    - WAL-first commit semantics (log before apply)
    """

    def __init__(self, table: Table, use_snapshot: bool = True) -> None:
        self.table = table
        self.use_snapshot = use_snapshot
        self._in_transaction = False
        self._pending: list[InsertOp | UpdateOp | DeleteOp] = []
        self._snapshot_rows: list[Row] = []
        self._scan_rows: list[Row] = []
        self._scan_pos = 0

    def begin_transaction(self) -> None:
        if self._in_transaction:
            raise RuntimeError("Transaction already active")
        self._in_transaction = True
        self._pending = []
        self._scan_rows = []
        self._scan_pos = 0
        self._snapshot_rows = self.table.select_all(include_deleted=True) if self.use_snapshot else []

    def queue_insert(self, row: Row) -> None:
        self._ensure_transaction()
        self._validate_row(row)
        state = self._view_rows(include_deleted=True)
        if any(r.id == row.id for r in state):
            raise DuplicateKeyError(f"Duplicate key: {row.id}")
        self._pending.append(InsertOp(row=row))

    def queue_update(self, row_id: int, *, username: str | None = None, email: str | None = None) -> None:
        self._ensure_transaction()
        updates: dict[str, str] = {}
        if username is not None:
            updates["username"] = username
        if email is not None:
            updates["email"] = email
        if not updates:
            raise ValueError("No fields provided for update")
        current = self.search_by_key(row_id)
        if current is None or current.is_deleted:
            raise ValueError(f"Row not found: id={row_id}")
        temp = Row(
            id=current.id,
            username=updates.get("username", current.username),
            email=updates.get("email", current.email),
            is_deleted=current.is_deleted,
        )
        self._validate_row(temp)
        self._pending.append(UpdateOp(row_id=row_id, updates=updates))

    def queue_delete(self, row_id: int) -> None:
        self._ensure_transaction()
        current = self.search_by_key(row_id)
        if current is None or current.is_deleted:
            raise ValueError(f"Row not found: id={row_id}")
        self._pending.append(DeleteOp(row_id=row_id))

    def commit(self) -> None:
        self._ensure_transaction()
        if not self._pending:
            self._finish_transaction()
            return
        self.table.begin_transaction()
        try:
            for op in self._pending:
                self.table.log_operation(op.to_sql())
                op.apply(self.table)
            self.table.pager.flush_all()
            self.table.commit()
            self._finish_transaction()
        except Exception:
            self.table.rollback()
            self._finish_transaction()
            raise

    def rollback(self) -> None:
        self._ensure_transaction()
        self._finish_transaction()

    def search_by_key(self, row_id: int) -> Optional[Row]:
        if self._in_transaction:
            for row in self._view_rows(include_deleted=True):
                if row.id == row_id:
                    return row
            return None
        return self.table.get(row_id)

    def iter_rows(self) -> Iterator[Row]:
        rows = self._view_rows(include_deleted=False) if self._in_transaction else self.table.select_all()
        for row in rows:
            yield row

    def execute_scan(self) -> None:
        self._scan_rows = list(self.iter_rows())
        self._scan_pos = 0

    def fetchone(self) -> Optional[Row]:
        if self._scan_pos >= len(self._scan_rows):
            return None
        row = self._scan_rows[self._scan_pos]
        self._scan_pos += 1
        return row

    def _view_rows(self, include_deleted: bool) -> list[Row]:
        base = list(self._snapshot_rows) if self._in_transaction and self.use_snapshot else self.table.select_all(include_deleted=True)
        by_id = {r.id: r for r in base}
        for op in self._pending:
            if isinstance(op, InsertOp):
                by_id[op.row.id] = op.row
            elif isinstance(op, UpdateOp):
                current = by_id.get(op.row_id)
                if current is None:
                    continue
                by_id[op.row_id] = Row(
                    id=current.id,
                    username=op.updates.get("username", current.username),
                    email=op.updates.get("email", current.email),
                    is_deleted=current.is_deleted,
                )
            else:
                current = by_id.get(op.row_id)
                if current is None:
                    continue
                by_id[op.row_id] = Row(
                    id=current.id,
                    username=current.username,
                    email=current.email,
                    is_deleted=True,
                )
        ordered = [by_id[k] for k in sorted(by_id)]
        return ordered if include_deleted else [r for r in ordered if not r.is_deleted]

    def _validate_row(self, row: Row) -> None:
        if row.id < 0:
            raise ValueError("id must be non-negative")
        # Reuse serializer constraints for field lengths/encoding.
        serialize_row(row)

    def _ensure_transaction(self) -> None:
        if not self._in_transaction:
            raise RuntimeError("No active transaction. Call begin_transaction() first.")

    def _finish_transaction(self) -> None:
        self._in_transaction = False
        self._pending = []
        self._snapshot_rows = []
        self._scan_rows = []
        self._scan_pos = 0
