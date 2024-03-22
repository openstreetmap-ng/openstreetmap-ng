from collections import OrderedDict

_not_found = object()


class LRUCache:
    __slots__ = ('_maxsize', '_cache')

    def __init__(self, maxsize: int) -> None:
        self._maxsize = maxsize
        self._cache = OrderedDict()

    def __setitem__(self, key, value) -> None:
        cache = self._cache  # read property once for performance
        if key in cache:
            cache.move_to_end(key)
        else:
            if len(cache) >= self._maxsize:
                cache.popitem(last=False)
            cache[key] = value

    def get(self, key, default=None):
        # read property once for performance
        cache = self._cache
        not_found = _not_found

        value = cache.get(key, not_found)
        if value is not_found:
            return default
        cache.move_to_end(key)
        return value
