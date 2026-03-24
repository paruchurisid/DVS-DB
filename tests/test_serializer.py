import unittest

from dvsdb.models import Row
from dvsdb.serializer import deserialize_row, serialize_row


class SerializerTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        row = Row(id=7, username="alice", email="alice@example.com")
        raw = serialize_row(row)
        decoded = deserialize_row(raw)
        self.assertEqual(row, decoded)

    def test_field_too_long(self) -> None:
        row = Row(id=1, username="x" * 40, email="a@b.com")
        with self.assertRaises(ValueError):
            serialize_row(row)


if __name__ == "__main__":
    unittest.main()
