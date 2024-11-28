from starlette.types import ASGIApp, Receive, Scope, Send

from app.lib.exceptions_context import raise_for
from app.limits import REQUEST_PATH_QUERY_MAX_LENGTH
from app.middlewares.request_context_middleware import get_request


class LimitUrlSizeMiddleware:
    """
    URL size limiting middleware.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request_url = get_request().url
        path_query_length = len(request_url.path) + len(request_url.query)
        if path_query_length > REQUEST_PATH_QUERY_MAX_LENGTH:
            raise_for.request_uri_too_long()

        await self.app(scope, receive, send)
