from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib_cython.format_style_context import format_style_context


class FormatStyleMiddleware(BaseHTTPMiddleware):
    """
    Wrap request in format style context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        async with format_style_context(request):
            return await super().dispatch(request, call_next)
