from contextlib import contextmanager
from contextvars import ContextVar

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


def raise_for() -> Exceptions:
    """
    Get the configured exceptions implementation.
    """
    return _context.get()
