from collections.abc import Callable
from typing import Any, Generic, TypeVar
from weakref import WeakKeyDictionary

R = TypeVar('R')


# inspired by functools.cached_property
def updating_cached_property(watch_attr_name: str):
    """
    Decorator to cache the result of a property with an auto-update condition.

    The property is re-evaluated when the value of watch_attr_name changes.
    """

    def decorator(func: Callable[[Any], R]) -> R:
        return _UpdatingCachedProperty(watch_attr_name, func)  # pyright: ignore[reportReturnType]

    return decorator


class _UpdatingCachedProperty(Generic[R]):
    __slots__ = ('_cache', '_func', '_watch_attr_name')

    def __init__(
        self,
        watch_attr_name: str,
        func: Callable[[Any], R],
    ) -> None:
        self._cache: WeakKeyDictionary[object, tuple[Any, R]] = WeakKeyDictionary()
        self._watch_attr_name = watch_attr_name
        self._func = func

    def __get__(self, instance: object, _=None) -> R:
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
