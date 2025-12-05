from fastapi import Response
from starlette import status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import REQUEST_PATH_QUERY_MAX_LENGTH
from app.middlewares.request_context_middleware import get_request


class LimitUrlSizeMiddleware:
    """URL size limiting middleware."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        url = get_request().url
        path_query_length = len(url.path) + len(url.query)
        if path_query_length > REQUEST_PATH_QUERY_MAX_LENGTH:
            return await Response(
                f'Request URI exceeded {REQUEST_PATH_QUERY_MAX_LENGTH} character limit',
                status.HTTP_414_REQUEST_URI_TOO_LONG,
            )(scope, receive, send)

        return await self.app(scope, receive, send)
