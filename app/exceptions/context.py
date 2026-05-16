from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, cast, override

if TYPE_CHECKING:
    from app.exceptions import Exceptions

# Importing `Exceptions` eagerly here would create a cycle: many `app.lib.*`
# modules import `raise_for` from this module, and the `Exceptions` class
# pulls in `app.lib.*` symbols transitively. The type annotation is enough.
_CTX: 'ContextVar[Exceptions]' = ContextVar('Exceptions')  # noqa: UP037


@contextmanager
def exceptions_context(implementation: 'Exceptions'):  # noqa: UP037
    """Context manager for setting the exceptions type in ContextVar."""
    with _CTX.set(implementation):
        yield


class _RaiseFor:
    @override
    def __getattribute__(self, name: str):
        return getattr(_CTX.get(), name)


raise_for = cast('Exceptions', cast(object, _RaiseFor()))

__all__ = ('raise_for',)
