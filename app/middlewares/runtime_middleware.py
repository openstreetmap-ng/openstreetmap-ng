import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RuntimeMiddleware:
    """
    Add X-Runtime header to responses.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        ts = time.perf_counter()

        async def wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                te = time.perf_counter()
                headers = MutableHeaders(raw=message['headers'])
                headers['X-Runtime'] = f'{te - ts:.5f}'

            await send(message)

        await self.app(scope, receive, wrapper)
