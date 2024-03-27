from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

from sqlalchemy.orm import joinedload

_joinedload_context = ContextVar('StatementContext_JoinedLoad')

T = TypeVar('T')


@contextmanager
def joinedload_context(*keys):
    """
    Context manager for setting joinedload keys in ContextVar.

    >>> with joinedload_context(Changeset.user):
    >>> with joinedload_context((Changeset.elements, Element.user)):
    """
    token = _joinedload_context.set(keys)
    try:
        yield
    finally:
        _joinedload_context.reset(token)


def apply_statement_context(stmt: T) -> T:
    """
    Apply statement post-processing context.
    """
    keys = _joinedload_context.get(None)
    if keys is not None:
        opts = []

        for key in keys:
            if isinstance(key, Sequence):
                key_iter = iter(key)
                current = joinedload(next(key_iter))
                for key in key_iter:
                    current = current.joinedload(key)
                opts.append(current)
            else:
                opts.append(joinedload(key))

        stmt = stmt.options(*opts)

    return stmt
