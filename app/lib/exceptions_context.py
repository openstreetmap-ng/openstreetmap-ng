from contextlib import contextmanager
from contextvars import ContextVar
from typing import cast, override

from app.exceptions import Exceptions

_CTX = ContextVar[Exceptions]('Exceptions')


@contextmanager
def exceptions_context(implementation: Exceptions):
    """Context manager for setting the exceptions type in ContextVar."""
    with _CTX.set(implementation):
        yield


class _RaiseFor:
    @override
    def __getattribute__(self, name: str):
        return getattr(_CTX.get(), name)


raise_for = cast(Exceptions, cast(object, _RaiseFor()))

__all__ = ('raise_for',)
