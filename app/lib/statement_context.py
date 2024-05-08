from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

_options_context = ContextVar('StatementContext_Options')

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


def apply_statement_context(stmt: T) -> T:
    """
    Apply statement post-processing context.
    """
    options = _options_context.get(None)
    if options is not None:
        stmt = stmt.options(*options)

    return stmt
