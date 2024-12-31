from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, cast, override

from app.exceptions import Exceptions

_context: ContextVar[Exceptions] = ContextVar('ExceptionsContext')


@contextmanager
def exceptions_context(implementation: Exceptions):
    """
    Context manager for setting the exceptions type in ContextVar.
    """
    token = _context.set(implementation)
    try:
        yield
    finally:
        _context.reset(token)


class _RaiseFor:
    @override
    def __getattribute__(self, name: str) -> Any:
        return getattr(_context.get(), name)


raise_for = cast(Exceptions, cast(object, _RaiseFor()))

__all__ = ('raise_for',)
