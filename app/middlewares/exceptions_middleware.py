from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.exceptions import Exceptions
from app.exceptions06 import Exceptions06
from app.lib.exceptions_context import exceptions_context


class ExceptionsMiddleware(BaseHTTPMiddleware):
    """
    Wrap requests in exceptions context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith(('/api/0.6/', '/api/versions', '/api/capabilities')):
            implementation = Exceptions06()
        else:
            implementation = Exceptions()

        async with exceptions_context(implementation):
            return await super().dispatch(request, call_next)
