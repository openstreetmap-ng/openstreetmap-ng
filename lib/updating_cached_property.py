from collections.abc import Callable
from types import GenericAlias
from typing import Self

# inspired by functools.cached_property

_NOT_FOUND = object()

class updating_cached_property:  # noqa: N801
    """
    A decorator to cache the result of a property with an auto-update condition.

    If watch_field changes, the property is re-evaluated.
    """

    def __init__(self, watch_field: str) -> None:
        self._watch_field = watch_field
        self._func = None
        self._attr_name = None
        self._cache_name = None

    def __call__(self, func: Callable) -> Self:
        self._func = func
        self.__doc__ = func.__doc__
        return self

    def __set_name__(self, owner: type, name: str) -> None:
        if self._attr_name is None:
            if self._watch_field == name:
                raise TypeError(
                    f'Cannot use {type(self).__name__} '
                    f'with the same property as the watch field ({name!r}).'
                )

            self._attr_name = name
            self._cache_name = f'_{type(self).__qualname__}_{name}'
        elif self._attr_name != name:
            raise TypeError(
                f'Cannot assign the same {type(self).__name__} '
                f'to two different names ({self._attr_name!r} and {name!r}).'
            )

    def __get__(self, instance: object, owner: type | None = None) -> object:
        if instance is None:
            return self

        if self._attr_name is None:
            raise TypeError(
                f'Cannot use {type(self).__name__} '
                f'instance without calling __set_name__ on it.'
            )

        try:
            cache_data = getattr(instance, self._cache_name)
        except AttributeError:
            cache_data = {}
            setattr(instance, self._cache_name, cache_data)

        watch_val = getattr(instance, self._watch_field)
        prev_watch_val = cache_data.get(self._watch_field, _NOT_FOUND)
        cached_val = cache_data.get(self._attr_name, _NOT_FOUND)

        if watch_val != prev_watch_val or cached_val is _NOT_FOUND:
            cached_val = self._func(instance)
            cache_data[self._watch_field] = watch_val
            cache_data[self._attr_name] = cached_val

        return cached_val

    __class_getitem__ = classmethod(GenericAlias)
