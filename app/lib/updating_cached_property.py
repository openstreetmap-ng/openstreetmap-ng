from collections.abc import Callable
from types import GenericAlias
from typing import Self

_not_found = object()


# inspired by functools.cached_property
class updating_cached_property:  # noqa: N801
    """
    A decorator to cache the result of a property with an auto-update condition.

    If `watch_attr_name` changes, the property is re-evaluated.
    """

    __slots__ = ('_watch_attr_name', '_set_attr_name', '_cache_name', '_func')

    def __init__(self, watch_attr_name: str) -> None:
        self._watch_attr_name = watch_attr_name
        self._set_attr_name = None
        self._cache_name = None
        self._func = None

    def __call__(self, func: Callable) -> Self:
        self._func = func
        return self

    def __set_name__(self, owner: type, name: str) -> None:
        if self._set_attr_name is None:
            if self._watch_attr_name == name:
                raise TypeError(
                    f'Cannot use {type(self).__name__} with the same property as the watch field ({name!r}).'
                )

            self._set_attr_name = name
            self._cache_name = f'_{type(self).__qualname__}_{name}'

        elif self._set_attr_name != name:
            raise TypeError(
                f'Cannot assign the same {type(self).__name__} '
                f'to two different names ({self._set_attr_name!r} and {name!r}).'
            )

    def __get__(self, instance: object, owner: type | None = None):
        if instance is None:
            return self

        # read property once for performance
        watch_attr_name = self._watch_attr_name
        set_attr_name = self._set_attr_name
        cache_name = self._cache_name

        if set_attr_name is None:
            raise TypeError(f'Cannot use {type(self).__name__} instance without calling __set_name__ on it.')

        # check for existing cache data
        try:
            cache_data = getattr(instance, cache_name)
        except AttributeError:
            cache_data = {}
            setattr(instance, cache_name, cache_data)

        watch_val = getattr(instance, watch_attr_name)
        prev_watch_val = cache_data.get(watch_attr_name, _not_found)
        cached_val = cache_data.get(set_attr_name, _not_found)

        if watch_val != prev_watch_val or cached_val is _not_found:
            cached_val = self._func(instance)
            cache_data[watch_attr_name] = watch_val
            cache_data[set_attr_name] = cached_val

        return cached_val

    __class_getitem__ = classmethod(GenericAlias)
