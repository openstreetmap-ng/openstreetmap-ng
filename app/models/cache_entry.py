from typing import NamedTuple


class CacheEntry(NamedTuple):
    id: bytes
    value: str
