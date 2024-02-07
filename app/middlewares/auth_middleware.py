from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib.auth_context import auth_context
from app.services.auth_service import AuthService


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Wrap requests in auth context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        user, scopes = await AuthService.authenticate_request(request)
        with auth_context(user, scopes):
            return await call_next(request)
