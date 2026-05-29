import cython
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class LocalhostRedirectMiddleware:
    """Simply redirect 127.0.0.1 requests to localhost for consistency."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        host = _get_host(scope)
        if host is not None:
            hostname, sep, port = host.partition(b':')
            if hostname == b'127.0.0.1':
                query_string: bytes = scope['query_string']
                location = (
                    f'{scope["scheme"]}://localhost'
                    + (f':{port.decode("latin-1")}' if sep else '')
                    + scope['path']
                    + (f'?{query_string.decode("latin-1")}' if query_string else '')
                )
                return await RedirectResponse(location)(scope, receive, send)

        return await self.app(scope, receive, send)


@cython.cfunc
def _get_host(scope: Scope):
    headers: list[tuple[bytes, bytes]] = scope['headers']
    for key, value in headers:
        if key == b'host':
            return value
    return None
