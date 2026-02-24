from starlette.types import ASGIApp, Receive, Scope, Send

from app.exceptions import Exceptions
from app.exceptions06 import Exceptions06
from app.lib.auth_context import auth_context
from app.lib.exceptions_context import exceptions_context
from app.lib.format_style_context import format_style_context
from app.lib.translation import translation_context
from app.services.auth_service import AuthService

_EXCEPTIONS = Exceptions()
_EXCEPTIONS_06 = Exceptions06()


class ContextMiddleware:
    """Wrap requests in exceptions, auth, translation and format contexts."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        path: str = scope['path']

        with (
            exceptions_context(
                _EXCEPTIONS_06
                if path.startswith((
                    '/api/0.6/',
                    '/api/versions',
                    '/api/capabilities',
                ))
                else _EXCEPTIONS
            ),
            auth_context(*await AuthService.authenticate_request()),
            translation_context(None),
            format_style_context(),
        ):
            return await self.app(scope, receive, send)
