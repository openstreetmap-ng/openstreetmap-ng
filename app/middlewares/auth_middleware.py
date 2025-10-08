from starlette.types import ASGIApp, Receive, Scope, Send

from app.lib.auth_context import auth_context
from app.services.auth_service import AuthService


class AuthMiddleware:
    """Wrap requests in auth context."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        with auth_context(*await AuthService.authenticate_request()):
            return await self.app(scope, receive, send)
