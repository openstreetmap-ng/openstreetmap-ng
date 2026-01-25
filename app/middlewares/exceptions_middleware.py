from starlette.types import ASGIApp, Receive, Scope, Send

from app.exceptions import Exceptions
from app.exceptions06 import Exceptions06
from app.lib.exceptions_context import exceptions_context


class ExceptionsMiddleware:
    """Wrap requests in exceptions context."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        path: str = scope['path']
        implementation = (
            Exceptions06()
            if path.startswith((
                '/api/0.6/',
                '/api/versions',
                '/api/capabilities',
            ))
            else Exceptions()
        )

        with exceptions_context(implementation):
            return await self.app(scope, receive, send)
