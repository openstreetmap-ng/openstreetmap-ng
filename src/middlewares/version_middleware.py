from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import VERSION


class VersionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Version'] = VERSION
        return response
