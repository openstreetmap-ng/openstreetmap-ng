from contextlib import contextmanager
from contextvars import ContextVar
from ipaddress import IPv4Address, IPv6Address, ip_address

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_context: ContextVar[Request] = ContextVar('RequestContext')


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


def get_request_ip() -> IPv4Address | IPv6Address:
    """
    Get the request IP address.
    """

    return ip_address(_context.get().client.host)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Wrap requests in request context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        with request_context(request):
            return await call_next(request)
