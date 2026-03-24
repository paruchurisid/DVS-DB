from __future__ import annotations

import os

from dvsdb.constants import MAX_PAGES, PAGE_SIZE


class Pager:
    def __init__(self, path: str) -> None:
        self.path = path
        self._file = open(path, "r+b") if os.path.exists(path) else open(path, "w+b")
        self.pages: dict[int, bytearray] = {}
        self._file.seek(0, os.SEEK_END)
        self.file_length = self._file.tell()
        self.num_pages = max(1, (self.file_length + PAGE_SIZE - 1) // PAGE_SIZE)

    def get_page(self, page_num: int) -> bytearray:
        if page_num < 0 or page_num >= MAX_PAGES:
            raise ValueError(f"Invalid page number: {page_num}")
        if page_num not in self.pages:
            page = bytearray(PAGE_SIZE)
            offset = page_num * PAGE_SIZE
            if offset < self.file_length:
                self._file.seek(offset)
                data = self._file.read(PAGE_SIZE)
                page[: len(data)] = data
            self.pages[page_num] = page
            if page_num >= self.num_pages:
                self.num_pages = page_num + 1
        return self.pages[page_num]

    def flush_page(self, page_num: int) -> None:
        if page_num not in self.pages:
            return
        self._file.seek(page_num * PAGE_SIZE)
        self._file.write(self.pages[page_num])
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.seek(0, os.SEEK_END)
        self.file_length = self._file.tell()
        self.num_pages = max(self.num_pages, (self.file_length + PAGE_SIZE - 1) // PAGE_SIZE)

    def close(self) -> None:
        self.flush_all()
        self._file.close()

    def flush_all(self) -> None:
        for page_num in sorted(self.pages):
            self.flush_page(page_num)
