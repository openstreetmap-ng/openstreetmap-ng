from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import cython
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import STATIC_CACHE_MAX_AGE, STATIC_CACHE_STALE
from app.middlewares.request_context_middleware import get_request

_STATIC_HEADER = f'public, max-age={int(STATIC_CACHE_MAX_AGE.total_seconds())}, stale-while-revalidate={int(STATIC_CACHE_STALE.total_seconds())}, immutable'


class CacheControlMiddleware:
    """Add Cache-Control header from @cache_control decorator."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        method: str = scope['method']
        if method not in ('GET', 'HEAD'):
            return await self.app(scope, receive, send)

        async def wrapper(message: Message):
            if message['type'] == 'http.response.start':
                status_code: cython.size_t = message['status']

                if 200 <= status_code < 300 or status_code == 301:
                    state: dict = scope.setdefault('state', {})
                    header: str | None = state.get('cache_control_header')
                    path: str = scope['path']
                    if header is None and path.startswith('/static'):
                        header = _STATIC_HEADER
                    if header is not None:
                        headers = MutableHeaders(raw=message['headers'])
                        headers.setdefault('Cache-Control', header)

            return await send(message)

        return await self.app(scope, receive, wrapper)


_P = ParamSpec('_P')
_R = TypeVar('_R')


def cache_control(max_age: timedelta, stale: timedelta):
    """Decorator to set the Cache-Control header for an endpoint."""
    header = f'public, max-age={int(max_age.total_seconds())}, stale-while-revalidate={int(stale.total_seconds())}'

    def decorator(func: Callable[_P, Coroutine[Any, Any, _R]]):
        @wraps(func)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs):
            get_request().state.cache_control_header = header
            return await func(*args, **kwargs)

        return wrapper

    return decorator
