from starlette.types import ASGIApp, Receive, Scope, Send

from app.lib.format_style_context import format_style_context


class FormatStyleMiddleware:
    """Wrap requests in format style context."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        with format_style_context():
            return await self.app(scope, receive, send)
