import os
import tempfile
import unittest

from dvsdb.btree import DuplicateKeyError
from dvsdb.models import Row
from dvsdb.table import Table


class BTreeTests(unittest.TestCase):
    def test_insert_and_select(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "test.db")
            table = Table(db)
            for i in [3, 1, 2]:
                table.insert(Row(id=i, username=f"user{i}", email=f"user{i}@x.com"))
            rows = table.select_all()
            table.close()
            self.assertEqual([r.id for r in rows], [1, 2, 3])

    def test_duplicate_key_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "test.db")
            table = Table(db)
            table.insert(Row(id=1, username="a", email="a@x.com"))
            with self.assertRaises(DuplicateKeyError):
                table.insert(Row(id=1, username="b", email="b@x.com"))
            table.close()

    def test_persists_across_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "test.db")
            table = Table(db)
            for i in range(80):
                table.insert(Row(id=i, username=f"u{i}", email=f"u{i}@x.com"))
            table.close()

            reopened = Table(db)
            rows = reopened.select_all()
            reopened.close()
            self.assertEqual(len(rows), 80)
            self.assertEqual(rows[0].id, 0)
            self.assertEqual(rows[-1].id, 79)


if __name__ == "__main__":
    unittest.main()
