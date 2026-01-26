import cython
from pyinstrument import Profiler
from starlette.responses import HTMLResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class ProfilerMiddleware:
    """
    Request profiling middleware.

    Simply add profile=1 to the query params.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        if not _has_query_param(scope['query_string'], b'profile'):
            return await self.app(scope, receive, send)

        profiler = Profiler()
        profiler.start()

        async def wrapper(message: Message):
            if message['type'] == 'http.response.start':
                profiler.stop()
                response = HTMLResponse(profiler.output_html())
                response.headers['Content-Security-Policy'] = ''
                return await response(scope, receive, send)

        try:
            return await self.app(scope, receive, wrapper)
        finally:
            if profiler.is_running:
                profiler.stop()


@cython.cfunc
def _has_query_param(query_string: bytes, name: bytes):
    if not query_string:
        return False

    for part in query_string.split(b'&'):
        if part.split(b'=', 1)[0] == name:
            return True

    return False
