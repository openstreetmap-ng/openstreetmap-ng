import functools
from datetime import timedelta

import cython
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.lib.request_context import get_request


@cython.cfunc
def _make_cache_control(max_age: timedelta, stale: timedelta):
    return f'public, max-age={int(max_age.total_seconds())}, stale-while-revalidate={int(stale.total_seconds())}'


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        request_method = request.method
        response_status_code: cython.int = response.status_code

        if request_method in ('GET', 'HEAD') and (200 <= response_status_code < 300 or response_status_code == 301):
            try:
                state = request.state
                max_age: timedelta = state.max_age
                stale: timedelta = state.stale

                response_headers = response.headers
                if 'Cache-Control' not in response_headers:
                    response_headers['Cache-Control'] = _make_cache_control(max_age, stale)

            except AttributeError:
                pass

        return response


def cache_control(max_age: timedelta, stale: timedelta):
    """
    Add Cache-Control header to the response.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = get_request()
            state = request.state
            state.max_age = max_age
            state.stale = stale
            return await func(*args, **kwargs)

        return wrapper

    return decorator
