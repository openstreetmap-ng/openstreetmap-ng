from contextvars import ContextVar
from ipaddress import IPv4Address, IPv6Address, ip_address

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import ENV
from app.lib.anonymizer import anonymize_ip

_CTX = ContextVar[Request]('Request')


def get_request() -> Request:
    """Get the request from the context."""
    return _CTX.get()


def get_request_ip() -> IPv4Address | IPv6Address:
    """Get the request IP address."""
    ip = ip_address(_CTX.get().client.host)  # pyright: ignore[reportOptionalMemberAccess]
    return anonymize_ip(ip) if ENV == 'test' else ip


class RequestContextMiddleware:
    """Wrap requests in request context."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        token = _CTX.set(Request(scope, receive))
        try:
            return await self.app(scope, receive, send)
        finally:
            _CTX.reset(token)
