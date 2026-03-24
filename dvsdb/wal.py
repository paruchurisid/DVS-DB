from __future__ import annotations

import os
from collections.abc import Callable


class WALManager:
    """
    Minimal write-ahead log manager.

    Log format per transaction:
    BEGIN
    <operation line>
    COMMIT
    """

    def __init__(self, wal_path: str) -> None:
        self.wal_path = wal_path
        self._file = open(wal_path, "a+", encoding="utf-8")
        self._in_transaction = False

    def begin_transaction(self) -> None:
        if self._in_transaction:
            raise RuntimeError("Transaction already active")
        self._append_and_sync("BEGIN")
        self._in_transaction = True

    def log_operation(self, operation_string: str) -> None:
        if not self._in_transaction:
            raise RuntimeError("No active transaction")
        if "\n" in operation_string:
            raise ValueError("Operation must be a single-line string")
        self._append_and_sync(operation_string)

    def commit(self) -> None:
        if not self._in_transaction:
            raise RuntimeError("No active transaction")
        self._append_and_sync("COMMIT")
        self._in_transaction = False

    def rollback(self) -> None:
        if not self._in_transaction:
            return
        self._append_and_sync("ROLLBACK")
        self._in_transaction = False

    def recover(self, apply_operation: Callable[[str], None]) -> None:
        """
        Replay only fully committed transactions from WAL.

        Recovery rule:
        - apply operations only from BEGIN ... COMMIT blocks
        - ignore incomplete blocks (missing COMMIT)
        - ignore explicit ROLLBACK blocks
        """
        committed_batches, _ = self._parse_transactions()

        for operations in committed_batches:
            for operation in operations:
                apply_operation(operation)

        self._truncate_wal()

    def checkpoint_wal(self, flush_pages: Callable[[], None]) -> None:
        """
        Manual checkpoint:
        1) refuse if app-level transaction is active
        2) refuse if WAL contains an incomplete transaction
        3) flush DB pages and fsync WAL
        4) truncate WAL safely
        """
        if self._in_transaction:
            raise RuntimeError("Cannot checkpoint while a transaction is active")
        _, has_incomplete = self._parse_transactions()
        if has_incomplete:
            raise RuntimeError("Cannot checkpoint with incomplete WAL transaction")
        flush_pages()
        self._file.flush()
        os.fsync(self._file.fileno())
        self._truncate_wal()

    def close(self) -> None:
        self._file.close()

    def _append_and_sync(self, line: str) -> None:
        self._file.write(line + "\n")
        self._file.flush()
        os.fsync(self._file.fileno())

    def _truncate_wal(self) -> None:
        self._file.seek(0)
        self._file.truncate(0)
        self._file.flush()
        os.fsync(self._file.fileno())

    def _parse_transactions(self) -> tuple[list[list[str]], bool]:
        committed_batches: list[list[str]] = []
        current_ops: list[str] | None = None

        with open(self.wal_path, "r", encoding="utf-8") as src:
            for raw_line in src:
                line = raw_line.strip()
                if not line:
                    continue
                if line == "BEGIN":
                    current_ops = []
                    continue
                if line == "COMMIT":
                    if current_ops is not None:
                        committed_batches.append(current_ops)
                    current_ops = None
                    continue
                if line == "ROLLBACK":
                    current_ops = None
                    continue
                if current_ops is not None:
                    current_ops.append(line)

        has_incomplete = current_ops is not None
        return committed_batches, has_incomplete
