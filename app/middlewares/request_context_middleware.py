from contextvars import ContextVar
from ipaddress import IPv4Address, IPv6Address, ip_address

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import ENV
from app.lib.anonymizer import anonymize_ip

_CTX = ContextVar[Request]('Request')


def is_request():
    """Check if running in a HTTP request context."""
    return _CTX.get(None) is not None


def is_rpc_request():
    """Check if current request is an RPC (Connect) request."""
    req = _CTX.get(None)
    return req is not None and req.url.path.startswith('/rpc')


def get_request():
    """Get the HTTP request."""
    return _CTX.get()


def get_request_ip() -> IPv4Address | IPv6Address:
    """Get the HTTP request's IP address."""
    ip = ip_address(_CTX.get().client.host)  # pyright: ignore[reportOptionalMemberAccess]
    return anonymize_ip(ip) if ENV == 'test' else ip


class RequestContextMiddleware:
    """Wrap HTTP requests in request context."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        token = _CTX.set(Request(scope, receive))
        try:
            return await self.app(scope, receive, send)
        finally:
            _CTX.reset(token)
