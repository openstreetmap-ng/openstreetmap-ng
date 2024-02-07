from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib.format_style_context import format_style_context


class FormatStyleMiddleware(BaseHTTPMiddleware):
    """
    Wrap requests in format style context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        with format_style_context(request):
            return await call_next(request)
