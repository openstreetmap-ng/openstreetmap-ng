from collections.abc import Callable
from typing import Any, TypeVar
from weakref import WeakKeyDictionary

R = TypeVar('R')


# inspired by functools.cached_property
class updating_cached_property:  # noqa: N801
    """
    Decorator to cache the result of a property with an auto-update condition.

    If watch_attr_name changes, the property is re-evaluated.
    """

    __slots__ = ('_watch_attr_name', '_cache')

    def __init__(self, watch_attr_name: str) -> None:
        self._watch_attr_name = watch_attr_name
        self._cache: WeakKeyDictionary[object, tuple[Any, Any]] = WeakKeyDictionary()

    def __call__(self, func: Callable[[Any], R]) -> R:
        return _UpdatingCachedPropertyImpl(self._watch_attr_name, self._cache, func)  # type: ignore


class _UpdatingCachedPropertyImpl:
    __slots__ = ('_watch_attr_name', '_cache', '_func')

    def __init__(
        self,
        watch_attr_name: str,
        cache: WeakKeyDictionary[object, tuple[Any, Any]],
        func: Callable[[Any], R],
    ) -> None:
        self._watch_attr_name = watch_attr_name
        self._cache = cache
        self._func = func

    def __get__(self, instance: object, _=None):
        cache = self._cache
        cached = cache.get(instance)
        watch_val = getattr(instance, self._watch_attr_name)

        if cached is not None:
            prev_watch_val, cached_val = cached
            if prev_watch_val != watch_val:
                cached_val = self._func(instance)
                cache[instance] = (watch_val, cached_val)
        else:
            cached_val = self._func(instance)
            cache[instance] = (watch_val, cached_val)

        return cached_val
