from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib.request_context import request_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Wrap requests in request context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        with request_context(request):
            return await call_next(request)
