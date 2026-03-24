import os
import tempfile
import unittest

from dvsdb.models import Row
from dvsdb.table import Table
from dvsdb.wal import WALManager


class WALTests(unittest.TestCase):
    def test_recover_replays_only_committed_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wal_path = os.path.join(tmp, "dvsdb.wal")
            with open(wal_path, "w", encoding="utf-8") as f:
                f.write("BEGIN\n")
                f.write('INSERT INTO users VALUES (1, "a", "a@x.com");\n')
                f.write("COMMIT\n")
                f.write("BEGIN\n")
                f.write('INSERT INTO users VALUES (2, "b", "b@x.com");\n')
                # Incomplete transaction: no COMMIT.

            applied: list[str] = []
            wal = WALManager(wal_path)
            wal.recover(applied.append)
            wal.close()

            self.assertEqual(len(applied), 1)
            self.assertIn('(1, "a", "a@x.com")', applied[0])

    def test_table_startup_recovery_from_wal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "dvsdb.db")
            wal_path = os.path.join(tmp, "dvsdb.wal")
            with open(wal_path, "w", encoding="utf-8") as f:
                f.write("BEGIN\n")
                f.write('INSERT INTO users VALUES (7, "alice", "alice@x.com");\n')
                f.write("COMMIT\n")

            table = Table(db_path)
            rows = table.select_all()
            table.close()

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], Row(id=7, username="alice", email="alice@x.com"))

            with open(wal_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "")

    def test_checkpoint_truncates_wal_and_preserves_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "dvsdb.db")
            wal_path = os.path.join(tmp, "dvsdb.wal")

            table = Table(db_path)
            table.insert_transactional(Row(id=1, username="u1", email="u1@x.com"))
            table.insert_transactional(Row(id=2, username="u2", email="u2@x.com"))

            with open(wal_path, "r", encoding="utf-8") as f:
                before = f.read()
            self.assertIn("BEGIN", before)
            self.assertIn("COMMIT", before)

            table.checkpoint_wal()
            table.close()

            with open(wal_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "")

            reopened = Table(db_path)
            rows = reopened.select_all()
            reopened.close()
            self.assertEqual([r.id for r in rows], [1, 2])

    def test_checkpoint_fails_on_incomplete_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wal_path = os.path.join(tmp, "dvsdb.wal")
            with open(wal_path, "w", encoding="utf-8") as f:
                f.write("BEGIN\n")
                f.write('INSERT INTO users VALUES (9, "x", "x@x.com");\n')

            wal = WALManager(wal_path)
            with self.assertRaises(RuntimeError):
                wal.checkpoint_wal(lambda: None)
            wal.close()


if __name__ == "__main__":
    unittest.main()
