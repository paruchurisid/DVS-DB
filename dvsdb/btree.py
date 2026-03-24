from __future__ import annotations

import struct
from typing import Optional

from dvsdb.constants import PAGE_SIZE, ROW_SIZE
from dvsdb.models import Row
from dvsdb.pager import Pager
from dvsdb.serializer import deserialize_row, serialize_row

NODE_TYPE_OFFSET = 0
IS_ROOT_OFFSET = 1
NUM_KEYS_OFFSET = 2
COMMON_NODE_HEADER_SIZE = 6

NODE_INTERNAL = 0
NODE_LEAF = 1

LEAF_NEXT_LEAF_OFFSET = COMMON_NODE_HEADER_SIZE
LEAF_HEADER_SIZE = COMMON_NODE_HEADER_SIZE + 4
LEAF_CELL_SIZE = 4 + ROW_SIZE
LEAF_MAX_CELLS = (PAGE_SIZE - LEAF_HEADER_SIZE) // LEAF_CELL_SIZE

INTERNAL_RIGHT_CHILD_OFFSET = COMMON_NODE_HEADER_SIZE
INTERNAL_HEADER_SIZE = COMMON_NODE_HEADER_SIZE + 4
INTERNAL_CELL_SIZE = 8  # child pointer + key
INTERNAL_MAX_CELLS = (PAGE_SIZE - INTERNAL_HEADER_SIZE) // INTERNAL_CELL_SIZE


def _u16_get(page: bytearray, offset: int) -> int:
    return struct.unpack_from("<H", page, offset)[0]


def _u16_set(page: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", page, offset, value)


def _u32_get(page: bytearray, offset: int) -> int:
    return struct.unpack_from("<I", page, offset)[0]


def _u32_set(page: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", page, offset, value)


def _node_type(page: bytearray) -> int:
    return page[NODE_TYPE_OFFSET]


def _set_node_type(page: bytearray, node_type: int) -> None:
    page[NODE_TYPE_OFFSET] = node_type


def _is_root(page: bytearray) -> bool:
    return bool(page[IS_ROOT_OFFSET])


def _set_is_root(page: bytearray, value: bool) -> None:
    page[IS_ROOT_OFFSET] = 1 if value else 0


def _num_keys(page: bytearray) -> int:
    return _u16_get(page, NUM_KEYS_OFFSET)


def _set_num_keys(page: bytearray, value: int) -> None:
    _u16_set(page, NUM_KEYS_OFFSET, value)


def _leaf_next(page: bytearray) -> int:
    return _u32_get(page, LEAF_NEXT_LEAF_OFFSET)


def _set_leaf_next(page: bytearray, page_num: int) -> None:
    _u32_set(page, LEAF_NEXT_LEAF_OFFSET, page_num)


def _leaf_cell_offset(cell_num: int) -> int:
    return LEAF_HEADER_SIZE + cell_num * LEAF_CELL_SIZE


def _leaf_key(page: bytearray, cell_num: int) -> int:
    return _u32_get(page, _leaf_cell_offset(cell_num))


def _leaf_set_key(page: bytearray, cell_num: int, key: int) -> None:
    _u32_set(page, _leaf_cell_offset(cell_num), key)


def _leaf_value(page: bytearray, cell_num: int) -> bytes:
    start = _leaf_cell_offset(cell_num) + 4
    return bytes(page[start : start + ROW_SIZE])


def _leaf_set_value(page: bytearray, cell_num: int, value: bytes) -> None:
    start = _leaf_cell_offset(cell_num) + 4
    page[start : start + ROW_SIZE] = value


def _internal_cell_offset(cell_num: int) -> int:
    return INTERNAL_HEADER_SIZE + cell_num * INTERNAL_CELL_SIZE


def _internal_child(page: bytearray, cell_num: int) -> int:
    return _u32_get(page, _internal_cell_offset(cell_num))


def _internal_set_child(page: bytearray, cell_num: int, child_page_num: int) -> None:
    _u32_set(page, _internal_cell_offset(cell_num), child_page_num)


def _internal_key(page: bytearray, cell_num: int) -> int:
    return _u32_get(page, _internal_cell_offset(cell_num) + 4)


def _internal_set_key(page: bytearray, cell_num: int, key: int) -> None:
    _u32_set(page, _internal_cell_offset(cell_num) + 4, key)


def _internal_right_child(page: bytearray) -> int:
    return _u32_get(page, INTERNAL_RIGHT_CHILD_OFFSET)


def _internal_set_right_child(page: bytearray, page_num: int) -> None:
    _u32_set(page, INTERNAL_RIGHT_CHILD_OFFSET, page_num)


def _initialize_leaf(page: bytearray, is_root: bool = False) -> None:
    page[:] = b"\x00" * PAGE_SIZE
    _set_node_type(page, NODE_LEAF)
    _set_is_root(page, is_root)
    _set_num_keys(page, 0)
    _set_leaf_next(page, 0)


def _initialize_internal(page: bytearray, is_root: bool = False) -> None:
    page[:] = b"\x00" * PAGE_SIZE
    _set_node_type(page, NODE_INTERNAL)
    _set_is_root(page, is_root)
    _set_num_keys(page, 0)
    _internal_set_right_child(page, 0)


class DuplicateKeyError(Exception):
    pass


class TableFullError(Exception):
    pass


class BTree:
    def __init__(self, pager: Pager, root_page_num: int = 0) -> None:
        self.pager = pager
        self.root_page_num = root_page_num
        root = self.pager.get_page(self.root_page_num)
        if all(b == 0 for b in root):
            _initialize_leaf(root, is_root=True)

    def close(self) -> None:
        self.pager.close()

    def _find_leaf(self, page_num: int, key: int) -> int:
        page = self.pager.get_page(page_num)
        if _node_type(page) == NODE_LEAF:
            return page_num
        num_keys = _num_keys(page)
        idx = 0
        while idx < num_keys and key > _internal_key(page, idx):
            idx += 1
        if idx == num_keys:
            child = _internal_right_child(page)
        else:
            child = _internal_child(page, idx)
        return self._find_leaf(child, key)

    def get(self, key: int) -> Optional[Row]:
        leaf_page_num = self._find_leaf(self.root_page_num, key)
        leaf = self.pager.get_page(leaf_page_num)
        num_cells = _num_keys(leaf)
        lo, hi = 0, num_cells
        while lo < hi:
            mid = (lo + hi) // 2
            mid_key = _leaf_key(leaf, mid)
            if key == mid_key:
                return deserialize_row(_leaf_value(leaf, mid))
            if key < mid_key:
                hi = mid
            else:
                lo = mid + 1
        return None

    def all_rows(self) -> list[Row]:
        rows: list[Row] = []
        page_num = self._leftmost_leaf(self.root_page_num)
        while True:
            leaf = self.pager.get_page(page_num)
            for idx in range(_num_keys(leaf)):
                rows.append(deserialize_row(_leaf_value(leaf, idx)))
            nxt = _leaf_next(leaf)
            if nxt == 0:
                break
            page_num = nxt
        return rows

    def _leftmost_leaf(self, page_num: int) -> int:
        page = self.pager.get_page(page_num)
        if _node_type(page) == NODE_LEAF:
            return page_num
        return self._leftmost_leaf(_internal_child(page, 0))

    def insert(self, row: Row) -> None:
        payload = serialize_row(row)
        result = self._insert_recursive(self.root_page_num, row.id, payload)
        if result is not None:
            split_key, right_child = result
            old_root_num = self.root_page_num
            old_root = self.pager.get_page(old_root_num)
            old_root_is_leaf = _node_type(old_root) == NODE_LEAF

            new_left_num = self.pager.num_pages
            if new_left_num >= 1024:
                raise TableFullError("Maximum page count reached")
            new_left = self.pager.get_page(new_left_num)
            new_left[:] = old_root[:]
            _set_is_root(new_left, False)

            _initialize_internal(old_root, is_root=True)
            _set_num_keys(old_root, 1)
            _internal_set_child(old_root, 0, new_left_num)
            _internal_set_key(old_root, 0, split_key)
            _internal_set_right_child(old_root, right_child)

            if old_root_is_leaf:
                left = self.pager.get_page(new_left_num)
                if _leaf_next(left) == 0:
                    _set_leaf_next(left, right_child)

    def _insert_recursive(self, page_num: int, key: int, payload: bytes) -> Optional[tuple[int, int]]:
        page = self.pager.get_page(page_num)
        if _node_type(page) == NODE_LEAF:
            return self._insert_into_leaf(page_num, key, payload)
        return self._insert_into_internal(page_num, key, payload)

    def _insert_into_leaf(self, page_num: int, key: int, payload: bytes) -> Optional[tuple[int, int]]:
        page = self.pager.get_page(page_num)
        num_cells = _num_keys(page)

        idx = 0
        while idx < num_cells and _leaf_key(page, idx) < key:
            idx += 1
        if idx < num_cells and _leaf_key(page, idx) == key:
            raise DuplicateKeyError(f"Duplicate key: {key}")

        if num_cells < LEAF_MAX_CELLS:
            for move_idx in range(num_cells, idx, -1):
                src = _leaf_cell_offset(move_idx - 1)
                dst = _leaf_cell_offset(move_idx)
                page[dst : dst + LEAF_CELL_SIZE] = page[src : src + LEAF_CELL_SIZE]
            _leaf_set_key(page, idx, key)
            _leaf_set_value(page, idx, payload)
            _set_num_keys(page, num_cells + 1)
            return None

        all_cells: list[tuple[int, bytes]] = []
        for i in range(num_cells):
            all_cells.append((_leaf_key(page, i), _leaf_value(page, i)))
        all_cells.insert(idx, (key, payload))

        split = len(all_cells) // 2
        left_cells = all_cells[:split]
        right_cells = all_cells[split:]
        split_key = right_cells[0][0]

        _initialize_leaf(page, is_root=_is_root(page))
        _set_num_keys(page, len(left_cells))
        for i, (k, v) in enumerate(left_cells):
            _leaf_set_key(page, i, k)
            _leaf_set_value(page, i, v)

        right_page_num = self.pager.num_pages
        right_page = self.pager.get_page(right_page_num)
        _initialize_leaf(right_page, is_root=False)
        _set_num_keys(right_page, len(right_cells))
        for i, (k, v) in enumerate(right_cells):
            _leaf_set_key(right_page, i, k)
            _leaf_set_value(right_page, i, v)

        _set_leaf_next(right_page, _leaf_next(page))
        _set_leaf_next(page, right_page_num)
        return (split_key, right_page_num)

    def _insert_into_internal(self, page_num: int, key: int, payload: bytes) -> Optional[tuple[int, int]]:
        page = self.pager.get_page(page_num)
        num_keys = _num_keys(page)
        child_idx = 0
        while child_idx < num_keys and key > _internal_key(page, child_idx):
            child_idx += 1
        child_page_num = _internal_right_child(page) if child_idx == num_keys else _internal_child(page, child_idx)

        child_split = self._insert_recursive(child_page_num, key, payload)
        if child_split is None:
            return None

        split_key, right_child = child_split
        insert_idx = 0
        while insert_idx < num_keys and _internal_key(page, insert_idx) < split_key:
            insert_idx += 1

        if num_keys < INTERNAL_MAX_CELLS:
            if insert_idx == num_keys:
                old_right = _internal_right_child(page)
                _internal_set_child(page, num_keys, old_right)
                _internal_set_key(page, num_keys, split_key)
                _internal_set_right_child(page, right_child)
            else:
                for move in range(num_keys, insert_idx, -1):
                    src = _internal_cell_offset(move - 1)
                    dst = _internal_cell_offset(move)
                    page[dst : dst + INTERNAL_CELL_SIZE] = page[src : src + INTERNAL_CELL_SIZE]
                _internal_set_key(page, insert_idx, split_key)
                _internal_set_child(page, insert_idx, child_page_num)
                _internal_set_child(page, insert_idx + 1, right_child)
            _set_num_keys(page, num_keys + 1)
            return None

        temp_children: list[int] = []
        temp_keys: list[int] = []
        for i in range(num_keys):
            temp_children.append(_internal_child(page, i))
            temp_keys.append(_internal_key(page, i))
        temp_children.append(_internal_right_child(page))

        temp_keys.insert(insert_idx, split_key)
        temp_children.insert(insert_idx + 1, right_child)

        mid = len(temp_keys) // 2
        promote = temp_keys[mid]

        left_keys = temp_keys[:mid]
        left_children = temp_children[: mid + 1]
        right_keys = temp_keys[mid + 1 :]
        right_children = temp_children[mid + 1 :]

        _initialize_internal(page, is_root=_is_root(page))
        _set_num_keys(page, len(left_keys))
        for i, k in enumerate(left_keys):
            _internal_set_child(page, i, left_children[i])
            _internal_set_key(page, i, k)
        _internal_set_right_child(page, left_children[-1])

        right_page_num = self.pager.num_pages
        right_page = self.pager.get_page(right_page_num)
        _initialize_internal(right_page, is_root=False)
        _set_num_keys(right_page, len(right_keys))
        for i, k in enumerate(right_keys):
            _internal_set_child(right_page, i, right_children[i])
            _internal_set_key(right_page, i, k)
        _internal_set_right_child(right_page, right_children[-1])
        return (promote, right_page_num)
