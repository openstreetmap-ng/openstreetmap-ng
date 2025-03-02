from datetime import timedelta
from functools import wraps

import cython
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.middlewares.request_context_middleware import get_request


class CacheControlMiddleware:
    """Add Cache-Control header from @cache_control decorator."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request = get_request()
        request_method = request.method
        if request_method not in {'GET', 'HEAD'}:
            await self.app(scope, receive, send)
            return

        async def wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                status_code: cython.int = message['status']

                if 200 <= status_code < 300 or status_code == 301:
                    state: dict = request.state._state  # noqa: SLF001
                    header = state.get('cache_control_header')
                    if header is not None:
                        headers = MutableHeaders(raw=message['headers'])
                        headers.setdefault('Cache-Control', header)

            await send(message)

        await self.app(scope, receive, wrapper)


def cache_control(max_age: timedelta, stale: timedelta):
    """Decorator to set the Cache-Control header for an endpoint."""
    header = f'public, max-age={int(max_age.total_seconds())}, stale-while-revalidate={int(stale.total_seconds())}'

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            state: dict = get_request().state._state  # noqa: SLF001
            state['cache_control_header'] = header
            return await func(*args, **kwargs)

        return wrapper

    return decorator
