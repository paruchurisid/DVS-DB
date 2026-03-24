from __future__ import annotations

import os

from dvsdb.btree import BTree, DuplicateKeyError
from dvsdb.models import Row
from dvsdb.parser import InsertStatement, parse_sql
from dvsdb.pager import Pager
from dvsdb.wal import WALManager


class Table:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.pager = Pager(db_path)
        self.btree = BTree(self.pager)
        wal_dir = os.path.dirname(os.path.abspath(db_path)) or "."
        self.wal = WALManager(os.path.join(wal_dir, "dvsdb.wal"))
        self.wal.recover(self._apply_logged_operation)

    def close(self) -> None:
        # Best-effort checkpoint on clean shutdown to avoid replaying
        # already-applied committed records on next startup.
        try:
            self.checkpoint_wal()
        except RuntimeError:
            pass
        self.wal.close()
        self.btree.close()

    def insert(self, row: Row) -> None:
        self.btree.insert(row)

    def insert_transactional(self, row: Row) -> None:
        operation = self._row_to_insert_sql(row)
        self.begin_transaction()
        try:
            self.log_operation(operation)
            self.insert(row)
            # Keep DB pages durable for committed transactions as well.
            self.pager.flush_all()
            self.commit()
        except Exception:
            self.rollback()
            raise

    def select_all(self) -> list[Row]:
        return self.btree.all_rows()

    def get(self, row_id: int) -> Row | None:
        return self.btree.get(row_id)

    def begin_transaction(self) -> None:
        self.wal.begin_transaction()

    def log_operation(self, operation_string: str) -> None:
        self.wal.log_operation(operation_string)

    def commit(self) -> None:
        self.wal.commit()

    def rollback(self) -> None:
        self.wal.rollback()

    def checkpoint_wal(self) -> None:
        self.wal.checkpoint_wal(self.pager.flush_all)

    def _apply_logged_operation(self, operation_string: str) -> None:
        statement = parse_sql(operation_string)
        if isinstance(statement, InsertStatement):
            self.insert(
                Row(
                    id=statement.row_id,
                    username=statement.username,
                    email=statement.email,
                )
            )
            self.pager.flush_all()

    @staticmethod
    def _row_to_insert_sql(row: Row) -> str:
        username = row.username.replace('"', '\\"')
        email = row.email.replace('"', '\\"')
        return f'INSERT INTO users VALUES ({row.id}, "{username}", "{email}");'


__all__ = ["Table", "DuplicateKeyError"]
