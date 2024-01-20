from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.lib.exceptions_context import raise_for
from app.limits import REQUEST_PATH_QUERY_MAX_LENGTH


class RequestUrlMiddleware(BaseHTTPMiddleware):
    """
    Limit request URL length.
    """

    async def dispatch(self, request: Request, call_next):
        request_url = request.url
        path_query_length = len(request_url.path) + len(request_url.query)

        if path_query_length > REQUEST_PATH_QUERY_MAX_LENGTH:
            raise_for().request_uri_too_long()

        return await call_next(request)
