import logging

import cython
from starlette import status
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import ENV
from app.lib.render_response import render_response
from app.lib.user_agent_check import is_browser_supported
from app.middlewares.request_context_middleware import get_request


class UnsupportedBrowserMiddleware:
    """Unsupported browser handling middleware."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        request = get_request()
        user_agent = request.headers.get('User-Agent')
        if (
            user_agent is None
            or is_browser_supported(user_agent)
            or request.method != 'GET'
            or request.cookies.get('unsupported_browser_override') is not None
        ) and not (ENV != 'prod' and 'unsupported_browser' in request.query_params):
            return await self.app(scope, receive, send)

        capture: cython.bint = False

        async def wrapper(message: Message) -> None:
            nonlocal capture

            if message['type'] == 'http.response.start':
                capture = _should_capture(message)

            if not capture:
                return await send(message)

            logging.debug('Client browser is not supported')
            response = await render_response(
                'unsupported-browser', status=status.HTTP_501_NOT_IMPLEMENTED
            )
            return await response(scope, receive, send)

        return await self.app(scope, receive, wrapper)


@cython.cfunc
def _should_capture(message: Message) -> cython.bint:
    status_code: cython.int = message['status']
    if status_code < 200 or status_code >= 300:
        return False

    headers = Headers(raw=message['headers'])
    content_type = headers.get('Content-Type', '')
    return content_type.startswith('text/html')
