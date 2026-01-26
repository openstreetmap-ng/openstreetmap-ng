from fastapi import Response
from starlette import status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import REQUEST_TARGET_MAX_BYTES


class LimitUrlSizeMiddleware:
    """URL size limiting middleware."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        raw_path: bytes = scope['raw_path']
        query_string: bytes = scope['query_string']
        request_target_size = len(raw_path) + (
            1 + len(query_string) if query_string else 0
        )
        if request_target_size > REQUEST_TARGET_MAX_BYTES:
            return await Response(
                f'Request target exceeded {REQUEST_TARGET_MAX_BYTES} byte limit',
                status.HTTP_414_REQUEST_URI_TOO_LONG,
            )(scope, receive, send)

        return await self.app(scope, receive, send)
