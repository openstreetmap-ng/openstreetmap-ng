from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import TEST_ENV, VERSION
from app.limits import HSTS_MAX_AGE

_HSTS_HEADER = f'max-age={int(HSTS_MAX_AGE.total_seconds())}; includeSubDomains; preload'


class DefaultHeadersMiddleware:
    """Add default headers to responses."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(raw=message['headers'])
                headers['Strict-Transport-Security'] = _HSTS_HEADER
                headers['X-Frame-Options'] = 'SAMEORIGIN'

                if TEST_ENV:
                    headers['X-Version'] = VERSION

            return await send(message)

        return await self.app(scope, receive, wrapper)
