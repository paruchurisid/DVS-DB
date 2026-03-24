import os
import tempfile
import unittest

from dvsdb.constants import PAGE_SIZE
from dvsdb.pager import Pager


class PagerTests(unittest.TestCase):
    def test_read_write_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.db")
            pager = Pager(path)
            page0 = pager.get_page(0)
            marker = b"hello-pager"
            page0[: len(marker)] = marker
            pager.flush_page(0)
            pager.close()

            pager2 = Pager(path)
            read_back = pager2.get_page(0)
            self.assertEqual(bytes(read_back[: len(marker)]), marker)
            self.assertEqual(len(read_back), PAGE_SIZE)
            pager2.close()


if __name__ == "__main__":
    unittest.main()
