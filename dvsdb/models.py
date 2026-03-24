from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    id: int
    username: str
    email: str
