from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib.exceptions06 import Exceptions06
from app.lib_cython.exceptions_context import exceptions_context


class ExceptionsMiddleware(BaseHTTPMiddleware):
    """
    Wrap request in exceptions context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith(('/api/0.6/', '/api/versions', '/api/capabilities')):
            type = Exceptions06
        else:
            type = Exceptions06  # TODO: just Exceptions when implemented

        async with exceptions_context(type):
            return await super().dispatch(request, call_next)
