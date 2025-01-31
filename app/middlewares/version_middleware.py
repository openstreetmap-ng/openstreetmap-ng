from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import VERSION


class VersionMiddleware:
    """Add X-Version header to responses."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async def wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(raw=message['headers'])
                headers['X-Version'] = VERSION

            await send(message)

        await self.app(scope, receive, wrapper)
