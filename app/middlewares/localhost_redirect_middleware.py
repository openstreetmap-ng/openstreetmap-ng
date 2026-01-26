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
        if host is not None and host.startswith('127.0.0.1'):
            hostname, sep, port = host.partition(':')
            if hostname == '127.0.0.1':
                location = (
                    f'{scope["scheme"]}://localhost'
                    + (f':{port}' if sep else '')
                    + scope['path']
                    + (
                        f'?{query}'
                        if (query := scope['query_string'].decode('latin-1'))
                        else ''
                    )
                )
                return await RedirectResponse(location)(scope, receive, send)

        return await self.app(scope, receive, send)


@cython.cfunc
def _get_host(scope: Scope):
    headers: list[tuple[bytes, bytes]] = scope['headers']
    for key, value in headers:
        if key == b'host':
            return value.decode('latin-1')
    return None
