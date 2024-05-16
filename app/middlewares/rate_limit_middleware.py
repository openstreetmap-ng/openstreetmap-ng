import logging
from functools import wraps

import cython
from fastapi import HTTPException
from starlette import status
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db import valkey
from app.lib.auth_context import auth_user
from app.middlewares.request_context_middleware import get_request
from app.models.user_role import UserRole


class RateLimitMiddleware:
    """
    Rate limiting middleware.

    The endpoint must be decorated with `@rate_limit` to enable rate limiting.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async def wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                state: dict = get_request().state._state  # noqa: SLF001
                rate_limit_headers: dict | None = state.get('rate_limit_headers')
                if rate_limit_headers is not None:
                    headers = MutableHeaders(raw=message['headers'])
                    headers.update(rate_limit_headers)

            await send(message)

        await self.app(scope, receive, wrapper)


async def _increase_counter(key: str, change: int, quota: int, *, raise_on_limit: bool) -> dict[str, str]:
    """
    Increase the rate limit counter and raise HTTPException if the limit is exceeded.

    Returns the rate limit response headers.
    """
    async with valkey() as conn, conn.pipeline() as pipe:
        pipe.incrby(key, change)
        pipe.expire(key, 3600, nx=True)
        pipe.ttl(key)
        result = await pipe.execute()

    current_usage: int = result[0]
    expires_in: int = result[2]

    remaining_quota: cython.int = quota - current_usage
    if remaining_quota < 0:
        remaining_quota = 0

    rate_limit_header = f'limit={quota}, remaining={remaining_quota}, reset={expires_in}'
    rate_limit_policy_header = f'{quota};w=3600;burst=0'

    # check if the rate limit is exceeded
    if current_usage > quota and raise_on_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Rate limit exceeded',
            headers={
                'RateLimit': rate_limit_header,
                'RateLimit-Policy': rate_limit_policy_header,
                'Retry-After': str(expires_in),
            },
        )

    return {
        'RateLimit': rate_limit_header,
        'RateLimit-Policy': rate_limit_policy_header,
    }


def rate_limit(*, weight: int = 1):
    """
    Decorator to rate-limit an endpoint.

    The rate limit quota is global and per-deployment.

    The weight can be overridden during execution using `set_rate_limit_weight` method.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key: str
            quota: cython.int
            user = auth_user()

            if user is not None:
                key = f'RateLimit:user:{user.id}'
                quota = UserRole.get_rate_limit_quota(user.roles)
            else:
                request = get_request()
                key = f'RateLimit:host:{request.client.host}'
                quota = UserRole.get_rate_limit_quota(())

            rate_limit_headers = await _increase_counter(key, weight, quota, raise_on_limit=True)

            # proceed with the request
            result = await func(*args, **kwargs)

            state: dict = get_request().state._state  # noqa: SLF001

            # check if the weight was overridden (only increasing)
            weight_change: int = state.get('rate_limit_weight', weight) - weight
            if weight_change > 0:
                rate_limit_headers = await _increase_counter(key, weight_change, quota, raise_on_limit=False)

            # save the headers to the request state
            state['rate_limit_headers'] = rate_limit_headers

            return result

        return wrapper

    return decorator


def set_rate_limit_weight(weight: int) -> None:
    """
    Override the request weight for rate limiting.
    """
    logging.debug('Overriding rate limit weight to %d', weight)
    state: dict = get_request().state._state  # noqa: SLF001
    state['rate_limit_weight'] = weight
