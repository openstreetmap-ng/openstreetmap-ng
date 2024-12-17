from pyinstrument import Profiler
from starlette.responses import HTMLResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.middlewares.request_context_middleware import get_request


class ProfilerMiddleware:
    """
    Request profiling middleware.

    Simply add profile=1 to the query params.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        if 'profile' not in get_request().query_params:
            await self.app(scope, receive, send)
            return

        profiler = Profiler()
        profiler.start()

        async def wrapper(message: Message) -> None:
            if message['type'] != 'http.response.start':
                return

            profiler.stop()
            response = HTMLResponse(profiler.output_html())
            await response(scope, receive, send)

        try:
            await self.app(scope, receive, wrapper)
        finally:
            if profiler.is_running:
                profiler.stop()
