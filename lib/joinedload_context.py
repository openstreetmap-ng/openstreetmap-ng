from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy.orm import joinedload

_context = ContextVar('JoinedLoad_context')


@contextmanager
def joinedload_context(*keys):
    """
    Context manager for setting joinedload in ContextVar.
    """

    token = _context.set(joinedload(keys))
    try:
        yield
    finally:
        _context.reset(token)


def get_joinedload() -> joinedload:
    """
    Get the joinedload from the context.
    """

    return _context.get() or joinedload(())
