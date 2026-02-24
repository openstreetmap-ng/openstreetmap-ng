import logging
from asyncio import TaskGroup
from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import wraps
from time import perf_counter
from typing import Any, ParamSpec, TypeVar

import cython
from fastapi import HTTPException
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import (
    APP_URL,
    ENV,
    HSTS_MAX_AGE,
    ID_URL,
    RAPID_URL,
    RATE_LIMIT_OPTIMISTIC_BLACKLIST_EXPIRE,
    STATIC_CACHE_MAX_AGE,
    STATIC_CACHE_STALE,
    VERSION,
)
from app.lib.auth_context import auth_user
from app.lib.file_cache import FileCache
from app.lib.sentry import SENTRY_DSN
from app.lib.user_role_limits import UserRoleLimits
from app.middlewares.request_context_middleware import get_request
from app.models.types import StorageKey
from app.services.rate_limit_service import RateLimitService

# Please keep it CSP version 2-compatible for the time being.
CSP_HEADER = '; '.join(
    filter(
        None,
        (
            "default-src 'self'",
            (
                "script-src 'self' https://matomo.monicz.dev/matomo.js"
                + (' http://localhost:49568' if ENV == 'dev' else '')
            ),
            (
                # vite and sentry feedbackIntegration require unsafe-inline
                "style-src 'self' 'unsafe-inline' http://localhost:49568"
                if ENV == 'dev' or (SENTRY_DSN and ENV == 'test')
                else None
            ),
            (
                "font-src 'self' http://localhost:49568"
                if ENV == 'dev'  #
                else None
            ),
            'child-src blob:',  # TODO: worker-src in CSP 3
            'img-src * data:',
            'connect-src * data:',
            f'frame-src {" ".join({ID_URL, RAPID_URL})}',
            f'frame-ancestors {APP_URL}',
            (f'report-uri {SENTRY_DSN}' if SENTRY_DSN else None),
        ),
    )
)

_HSTS_HEADER = (
    f'max-age={int(HSTS_MAX_AGE.total_seconds())}; includeSubDomains; preload'
)

_STATIC_CACHE_CONTROL_HEADER = f'public, max-age={int(STATIC_CACHE_MAX_AGE.total_seconds())}, stale-while-revalidate={int(STATIC_CACHE_STALE.total_seconds())}, immutable'

_BLACKLIST = FileCache('RateLimit')

_P = ParamSpec('_P')
_R = TypeVar('_R')


class HeadersMiddleware:
    """Apply response headers in a single send-wrapper pass."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        _VERBOSE: cython.bint = ENV != 'prod',
    ):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        method: str = scope['method']
        path: str = scope['path']
        ts = perf_counter() if _VERBOSE else 0

        async def _wrapper(message: Message):
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(raw=message['headers'])
                headers.setdefault('Content-Security-Policy', CSP_HEADER)
                headers['Strict-Transport-Security'] = _HSTS_HEADER

                state: dict | None = scope.get('state')

                # cache-control
                if method in ('GET', 'HEAD'):
                    status_code: cython.size_t = message['status']
                    if 200 <= status_code < 300 or status_code == 301:
                        cache_control_header: str | None = (
                            state.get('cache_control_header')
                            if state is not None
                            else None
                        )
                        if cache_control_header is None and path.startswith('/static'):
                            cache_control_header = _STATIC_CACHE_CONTROL_HEADER
                        if cache_control_header is not None:
                            headers.setdefault('Cache-Control', cache_control_header)

                # rate-limit
                if state is not None:
                    rate_limit_headers: dict | None = state.get('rate_limit_headers')
                    if rate_limit_headers is not None:
                        headers.update(rate_limit_headers)

                if _VERBOSE:
                    headers['X-Version'] = VERSION
                    headers['X-Runtime'] = f'{perf_counter() - ts:.5f}'

            return await send(message)

        return await self.app(scope, receive, _wrapper)


def cache_control(max_age: timedelta, stale: timedelta):
    """Decorator to set the Cache-Control header for an endpoint."""
    _header = f'public, max-age={int(max_age.total_seconds())}, stale-while-revalidate={int(stale.total_seconds())}'

    def _decorator(func: Callable[_P, Coroutine[Any, Any, _R]]):
        @wraps(func)
        async def _wrapper(*args: _P.args, **kwargs: _P.kwargs):
            get_request().state.cache_control_header = _header
            return await func(*args, **kwargs)

        return _wrapper

    return _decorator


def rate_limit(*, weight: float = 1):
    """
    Decorator to rate limit an endpoint. The rate limit quota is global.
    The weight can be increased in runtime using the set_rate_limit_weight method.
    """

    def _decorator(func: Callable[_P, Coroutine[Any, Any, _R]]):
        @wraps(func)
        async def _wrapper(*args: _P.args, **kwargs: _P.kwargs):
            req = get_request()
            user = auth_user()
            if user is not None:
                key: StorageKey = f'id:{user["id"]}'  # type: ignore
                quota = UserRoleLimits.get_rate_limit_quota(user['roles'])
            else:
                key: StorageKey = f'ip:{req.client.host}'  # type: ignore
                quota = UserRoleLimits.get_rate_limit_quota(None)

            if await _BLACKLIST.get(key) is None:
                # If not blacklisted, perform optimistic checking to reduce latency.
                async with TaskGroup() as tg:
                    request_task = tg.create_task(func(*args, **kwargs))

                    try:
                        rate_limit_headers = await RateLimitService.update(
                            key, weight, quota
                        )
                    except HTTPException:
                        # If rate limit is hit, temporarily blacklist the user from optimistic checks.
                        request_task.cancel()
                        async with _BLACKLIST.lock(key) as lock:
                            if await _BLACKLIST.get(key) is None:
                                logging.info(
                                    'Rate limit hit for %r, '
                                    'blacklisting from optimistic checks',
                                    key,
                                )
                                await _BLACKLIST.set(
                                    lock,
                                    b'',
                                    ttl=RATE_LIMIT_OPTIMISTIC_BLACKLIST_EXPIRE,
                                )
                        raise

                result = request_task.result()

            else:
                # If blacklisted, perform sequential checking to save on resources.
                rate_limit_headers = await RateLimitService.update(key, weight, quota)
                result = await func(*args, **kwargs)

            # Check if the weight was increased.
            state = req.state._state  # noqa: SLF001
            weight_change: float = state.get('rate_limit_weight', weight) - weight
            if weight_change > 0:
                rate_limit_headers = await RateLimitService.update(
                    key, weight_change, quota, raise_on_limit=None
                )

            # Save the headers to the request state.
            state['rate_limit_headers'] = rate_limit_headers
            return result

        return _wrapper

    return _decorator


def set_rate_limit_weight(weight: float):
    """Increase the request weight for rate limiting. Decreasing weights are ignored."""
    logging.debug('Overriding rate limit weight to %s', weight)
    get_request().state.rate_limit_weight = weight
