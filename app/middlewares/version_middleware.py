from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import VERSION


class VersionMiddleware(BaseHTTPMiddleware):
    """
    Add X-Version header to responses.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Version'] = VERSION
        return response
