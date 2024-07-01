from collections import OrderedDict
from typing import Generic, TypeVar, overload

K = TypeVar('K')
V = TypeVar('V')
D = TypeVar('D')

_not_found = object()


class LRUCache(Generic[K, V]):
    __slots__ = ('_maxsize', '_cache')

    def __init__(self, maxsize: int) -> None:
        self._maxsize = maxsize
        self._cache: OrderedDict[K, V] = OrderedDict()

    def __setitem__(self, key: K, value: V) -> None:
        cache = self._cache  # read property once for performance
        if key in cache:
            cache.move_to_end(key)
        else:
            if len(cache) >= self._maxsize:
                cache.popitem(last=False)
            cache[key] = value

    @overload
    def get(self, key: K, /) -> V | None: ...

    @overload
    def get(self, key: K, /, default: D) -> V | D: ...

    def get(self, key: K, /, default: D | None = None) -> V | D | None:
        # read property once for performance
        cache = self._cache
        not_found = _not_found

        value = cache.get(key, not_found)
        if value is not_found:
            return default
        cache.move_to_end(key)
        return value  # type: ignore
