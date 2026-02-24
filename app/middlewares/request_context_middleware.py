from asyncio import Task, gather
from contextvars import ContextVar
from ipaddress import IPv4Address, IPv6Address, ip_address

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import ENV
from app.lib.ip import anonymize_ip

_CTX = ContextVar[Request]('Request')
_AUDIT_CTX = ContextVar[set[Task[None]]]('RequestAuditTasks')


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


def get_request_audit_tasks():
    return _AUDIT_CTX.get()


class RequestContextMiddleware:
    """Wrap HTTP requests in request context."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        token = _CTX.set(Request(scope, receive))
        audit_tasks: set[Task[None]] = set()
        audit_tasks_token = _AUDIT_CTX.set(audit_tasks)
        try:
            return await self.app(scope, receive, send)
        finally:
            await gather(*audit_tasks, return_exceptions=True)
            _CTX.reset(token)
            _AUDIT_CTX.reset(audit_tasks_token)
