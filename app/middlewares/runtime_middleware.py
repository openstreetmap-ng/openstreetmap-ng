import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RuntimeMiddleware(BaseHTTPMiddleware):
    """
    Add X-Runtime header to responses.
    """

    async def dispatch(self, request: Request, call_next):
        ts = time.perf_counter()
        response = await call_next(request)
        te = time.perf_counter()
        response.headers['X-Runtime'] = f'{te - ts:.3f}'
        return response
