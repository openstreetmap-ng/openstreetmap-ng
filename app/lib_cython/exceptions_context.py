from contextlib import contextmanager
from contextvars import ContextVar

import cython

from app.lib.exceptions import ExceptionsBase

if cython.compiled:
    print(f'{__name__}: 🐇 compiled')

_context = ContextVar('Exceptions_context')


@contextmanager
def exceptions_context(exceptions_type: type[ExceptionsBase]):
    """
    Context manager for setting the exceptions type in ContextVar.
    """

    token = _context.set(exceptions_type)
    try:
        yield
    finally:
        _context.reset(token)


def raise_for() -> type[ExceptionsBase]:
    """
    Get the configured exceptions base.
    """

    return _context.get()
