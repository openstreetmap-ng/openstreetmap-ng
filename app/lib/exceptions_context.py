from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, cast, override

from app.exceptions import Exceptions

_CTX: ContextVar[Exceptions] = ContextVar('Exceptions')


@contextmanager
def exceptions_context(implementation: Exceptions):
    """Context manager for setting the exceptions type in ContextVar."""
    token = _CTX.set(implementation)
    try:
        yield
    finally:
        _CTX.reset(token)


class _RaiseFor:
    @override
    def __getattribute__(self, name: str) -> Any:
        return getattr(_CTX.get(), name)


raise_for = cast(Exceptions, cast(object, _RaiseFor()))

__all__ = ('raise_for',)
