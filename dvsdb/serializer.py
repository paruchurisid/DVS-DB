import struct

from dvsdb.constants import EMAIL_SIZE, ID_SIZE, ROW_SIZE, USERNAME_SIZE
from dvsdb.models import Row


def _encode_fixed(text: str, size: int) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) > size:
        raise ValueError(f"Field too long. Max bytes: {size}")
    return raw.ljust(size, b"\x00")


def _decode_fixed(raw: bytes) -> str:
    return raw.rstrip(b"\x00").decode("utf-8")


def serialize_row(row: Row) -> bytes:
    if row.id < 0:
        raise ValueError("id must be non-negative")
    id_part = struct.pack("<I", row.id)
    username_part = _encode_fixed(row.username, USERNAME_SIZE)
    email_part = _encode_fixed(row.email, EMAIL_SIZE)
    output = id_part + username_part + email_part
    if len(output) != ROW_SIZE:
        raise RuntimeError("Serialized row has invalid length")
    return output


def deserialize_row(raw: bytes) -> Row:
    if len(raw) != ROW_SIZE:
        raise ValueError(f"Expected {ROW_SIZE} bytes, got {len(raw)}")
    id_bytes = raw[:ID_SIZE]
    username_bytes = raw[ID_SIZE : ID_SIZE + USERNAME_SIZE]
    email_bytes = raw[ID_SIZE + USERNAME_SIZE :]
    row_id = struct.unpack("<I", id_bytes)[0]
    return Row(
        id=row_id,
        username=_decode_fixed(username_bytes),
        email=_decode_fixed(email_bytes),
    )
