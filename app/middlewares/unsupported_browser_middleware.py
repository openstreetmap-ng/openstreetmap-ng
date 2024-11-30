import logging

import cython
from starlette import status
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import TEST_ENV
from app.lib.render_response import render_response
from app.lib.user_agent_check import is_browser_supported
from app.middlewares.request_context_middleware import get_request


class UnsupportedBrowserMiddleware:
    """
    Unsupported browser handling middleware.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request = get_request()
        user_agent = request.headers.get('User-Agent')
        if (
            user_agent is None
            or is_browser_supported(user_agent)
            or request.method != 'GET'
            or request.cookies.get('unsupported_browser_override') is not None
        ) and not (TEST_ENV and 'unsupported_browser' in request.query_params):
            await self.app(scope, receive, send)
            return

        capture: cython.char = False

        async def wrapper(message: Message) -> None:
            nonlocal capture

            if message['type'] == 'http.response.start':
                capture = _should_capture(message)

            if not capture:
                await send(message)
                return

            logging.debug('Client browser is not supported')
            response = await render_response('unsupported_browser.jinja2')
            response.status_code = status.HTTP_501_NOT_IMPLEMENTED
            await response(scope, receive, send)

        await self.app(scope, receive, wrapper)


@cython.cfunc
def _should_capture(message: Message) -> cython.char:
    status_code: cython.int = message['status']
    if status_code != 200:
        return False
    headers = Headers(raw=message['headers'])
    content_type: str | None = headers.get('Content-Type')
    return content_type is not None and content_type.startswith('text/html')
