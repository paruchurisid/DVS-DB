from __future__ import annotations

import os
import logging

from dvsdb.btree import BTree, DuplicateKeyError
from dvsdb.models import Row
from dvsdb.parser import DeleteStatement, InsertStatement, SelectStatement, UpdateStatement, parse_sql, statement_to_sql
from dvsdb.pager import Pager
from dvsdb.wal import WALManager

logger = logging.getLogger(__name__)


class Table:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._closed = False
        self.pager = Pager(db_path)
        self.btree = BTree(self.pager)
        wal_dir = os.path.dirname(os.path.abspath(db_path)) or "."
        self.wal = WALManager(os.path.join(wal_dir, "dvsdb.wal"))
        self.wal.recover(self._apply_logged_operation)

    def close(self) -> None:
        if self._closed:
            return
        # Best-effort checkpoint on clean shutdown to avoid replaying
        # already-applied committed records on next startup.
        try:
            self.checkpoint_wal()
        except RuntimeError:
            pass
        self.wal.close()
        self.btree.close()
        self._closed = True

    def insert(self, row: Row) -> None:
        self.btree.insert(row)

    def insert_transactional(self, row: Row) -> None:
        operation = self._row_to_insert_sql(row)
        self._run_transactional_operation(operation, lambda: self.insert(row))

    def delete_where(self, where_column: str, where_value: int | str) -> int:
        stmt = DeleteStatement(where_column=where_column, where_value=where_value)
        return self._run_transactional_operation(
            statement_to_sql(stmt),
            lambda: self._delete_where_non_tx(where_column, where_value),
        )

    def update_where(self, set_column: str, set_value: int | str, where_column: str, where_value: int | str) -> int:
        if set_column not in {"username", "email"}:
            raise ValueError("Only username and email are updatable")

        stmt = UpdateStatement(
            set_column=set_column,
            set_value=set_value,
            where_column=where_column,
            where_value=where_value,
        )
        return self._run_transactional_operation(
            statement_to_sql(stmt),
            lambda: self._update_where_non_tx(set_column, set_value, where_column, where_value),
        )

    def select_where(self, where_column: str | None = None, where_value: int | str | None = None) -> list[Row]:
        if where_column is None:
            return self.select_all()
        if where_column == "id" and isinstance(where_value, int):
            row = self.get(where_value)
            return [] if row is None or row.is_deleted else [row]
        rows = self.select_all()
        return [row for row in rows if self._row_matches(row, where_column, where_value)]

    def _run_transactional_operation(self, operation: str, action):
        logger.info("table.tx.begin op=%s", operation[:120])
        self.begin_transaction()
        try:
            self.log_operation(operation)
            result = action()
            # Keep DB pages durable for committed transactions as well.
            self.pager.flush_all()
            self.commit()
            logger.info("table.tx.commit op=%s", operation[:120])
            return result
        except Exception:
            self.rollback()
            logger.exception("table.tx.rollback op=%s", operation[:120])
            raise

    def select_all(self, include_deleted: bool = False) -> list[Row]:
        rows = self.btree.all_rows()
        if include_deleted:
            return rows
        return [row for row in rows if not row.is_deleted]

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

    @property
    def has_active_transaction(self) -> bool:
        return self.wal.in_transaction

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
            return
        if isinstance(statement, DeleteStatement):
            # Recovery re-applies committed delete operations.
            self._delete_where_non_tx(statement.where_column, statement.where_value)
            self.pager.flush_all()
            return
        if isinstance(statement, UpdateStatement):
            # Recovery re-applies committed update operations.
            self._update_where_non_tx(
                statement.set_column,
                statement.set_value,
                statement.where_column,
                statement.where_value,
            )
            self.pager.flush_all()
            return
        if isinstance(statement, SelectStatement):
            return

    @staticmethod
    def _row_to_insert_sql(row: Row) -> str:
        username = row.username.replace('"', '\\"')
        email = row.email.replace('"', '\\"')
        return f'INSERT INTO users VALUES ({row.id}, "{username}", "{email}");'

    @staticmethod
    def _row_matches(row: Row, where_column: str, where_value: int | str | None) -> bool:
        if where_column == "id":
            return isinstance(where_value, int) and row.id == where_value
        if where_column == "username":
            return str(row.username) == str(where_value)
        if where_column == "email":
            return str(row.email) == str(where_value)
        return False

    @staticmethod
    def _updated_row(row: Row, set_column: str, set_value: int | str) -> Row:
        if set_column == "username":
            return Row(id=row.id, username=str(set_value), email=row.email, is_deleted=row.is_deleted)
        if set_column == "email":
            return Row(id=row.id, username=row.username, email=str(set_value), is_deleted=row.is_deleted)
        raise ValueError("Unsupported column update")

    def _delete_where_non_tx(self, where_column: str, where_value: int | str) -> int:
        if where_column == "id" and isinstance(where_value, int):
            row = self.get(where_value)
            if row is None or row.is_deleted:
                return 0
            self.btree.replace(where_value, Row(id=row.id, username=row.username, email=row.email, is_deleted=True))
            return 1
        rows = self.select_all(include_deleted=True)
        count = 0
        for row in rows:
            if row.is_deleted:
                continue
            if self._row_matches(row, where_column, where_value):
                self.btree.replace(row.id, Row(id=row.id, username=row.username, email=row.email, is_deleted=True))
                count += 1
        return count

    def _update_where_non_tx(self, set_column: str, set_value: int | str, where_column: str, where_value: int | str) -> int:
        if where_column == "id" and isinstance(where_value, int):
            row = self.get(where_value)
            if row is None or row.is_deleted:
                return 0
            updated = self._updated_row(row, set_column, set_value)
            self.btree.replace(where_value, updated)
            return 1
        rows = self.select_all(include_deleted=True)
        count = 0
        for row in rows:
            if row.is_deleted:
                continue
            if self._row_matches(row, where_column, where_value):
                self.btree.replace(row.id, self._updated_row(row, set_column, set_value))
                count += 1
        return count


__all__ = ["Table", "DuplicateKeyError"]
