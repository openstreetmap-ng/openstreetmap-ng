from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.middlewares.request_context_middleware import get_request


class LocalhostRedirectMiddleware:
    """Simply redirect 127.0.0.1 requests to localhost for consistency."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        req = get_request()
        if req.url.hostname == '127.0.0.1':
            return await RedirectResponse(req.url.replace(hostname='localhost'))(
                scope, receive, send
            )

        return await self.app(scope, receive, send)
