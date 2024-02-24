from contextvars import ContextVar
from functools import wraps

import cython
from fastapi import HTTPException, Request
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware

from app.db import redis
from app.lib.auth_context import auth_user
from app.middlewares.request_context_middleware import get_request
from app.models.user_role import UserRole

_weight_context: ContextVar[list[int]] = ContextVar('RateLimit_Weight')


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limit middleware.

    The endpoint must be decorated with `@rate_limit` to enable rate limiting.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        state: dict = request.state._state  # noqa: SLF001
        rate_limit_headers: dict | None = state.get('rate_limit_headers')
        if rate_limit_headers is not None:
            response.headers.update(rate_limit_headers)

        return response


async def _increase_counter(key: str, change: int, quota: int) -> dict[str, str]:
    """
    Increase the rate limit counter and raise if the limit is exceeded.

    Returns the rate limit headers.
    """

    async with redis() as conn, conn.pipeline() as pipe:
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
    if current_usage > quota:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
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
    Decorator for rate limiting an endpoint.

    The rate limit quota is global and per-deployment.

    The weight can be overridden during execution using `set_rate_limit_weight` function.
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

            rate_limit_headers = await _increase_counter(key, weight, quota)

            # proceed with the request
            token = _weight_context.set([weight])
            try:
                result = await func(*args, **kwargs)

                # check if the weight was overridden (only increasing)
                weight_change = _weight_context.get()[0] - weight
                if weight_change > 0:
                    rate_limit_headers = await _increase_counter(key, weight_change, quota)

                # save the headers to the request state
                state: dict = get_request().state._state  # noqa: SLF001
                state['rate_limit_headers'] = rate_limit_headers

                return result
            finally:
                _weight_context.reset(token)

        return wrapper

    return decorator


def set_rate_limit_weight(weight: int) -> None:
    """
    Override the request weight for rate limiting.
    """

    _weight_context.get()[0] = weight
