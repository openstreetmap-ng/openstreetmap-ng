from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import Request

_context = ContextVar('Request_context')


@contextmanager
def request_context(request: Request):
    """
    Context manager for setting request in ContextVar.
    """

    token = _context.set(request)
    try:
        yield
    finally:
        _context.reset(token)


def get_request() -> Request:
    """
    Get the request from the context.
    """

    return _context.get()
