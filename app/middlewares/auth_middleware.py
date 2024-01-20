from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib.auth_context import auth_context


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Wrap request in auth context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        async with auth_context(request):
            return await super().dispatch(request, call_next)
