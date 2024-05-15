from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

_options_context = ContextVar('OptionsContext')

T = TypeVar('T')


@contextmanager
def options_context(*options):
    """
    Context manager for setting options in ContextVar.

    >>> with options_context(joinedload(Changeset.user).load_only(User.id)):
    """
    token = _options_context.set(options)
    try:
        yield
    finally:
        _options_context.reset(token)


def apply_options_context(stmt: T) -> T:
    """
    Apply options context.
    """
    options = _options_context.get(None)
    if options is not None:
        stmt = stmt.options(*options)

    return stmt
