from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from lib.exceptions.exceptions06 import Exceptions06


class HttpSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_size: int):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        total_size = 0
        chunks = []

        async for chunk in request.stream():
            total_size += len(chunk)
            if total_size > self.max_size:
                Exceptions06.raise_for_input_too_big(total_size)
            chunks.append(chunk)

        request._body = b''.join(chunks)
        return await call_next(request)
