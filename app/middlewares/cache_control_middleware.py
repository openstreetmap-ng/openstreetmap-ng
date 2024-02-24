from datetime import timedelta
from functools import wraps

import cython
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.middlewares.request_context_middleware import get_request


class CacheControlMiddleware(BaseHTTPMiddleware):
    """
    Process the Cache-Control header from `@cache_control` decorator.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        state: dict = request.state._state  # noqa: SLF001
        cache_control: str | None = state.get('cache_control_header')
        if cache_control is not None:
            request_method = request.method
            response_status_code: cython.int = response.status_code

            # consider only successful responses and permanent redirects
            if (
                (request_method == 'GET' or request_method == 'HEAD')  #
                and (200 <= response_status_code < 300 or response_status_code == 301)
            ):
                response.headers.setdefault('Cache-Control', cache_control)

        return response


def cache_control(max_age: timedelta, stale: timedelta):
    """
    Decorator to set the Cache-Control header for an endpoint.
    """

    header = f'public, max-age={int(max_age.total_seconds())}, stale-while-revalidate={int(stale.total_seconds())}'

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            state: dict = get_request().state._state  # noqa: SLF001
            state['cache_control_header'] = header
            return await func(*args, **kwargs)

        return wrapper

    return decorator
