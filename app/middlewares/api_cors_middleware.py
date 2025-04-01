from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import CORS_MAX_AGE
from app.middlewares.request_context_middleware import get_request


class APICorsMiddleware:
    """Enable CORS for API requests."""

    __slots__ = ('app', 'cors')

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.cors = CORSMiddleware(
            app,
            allow_origins=['*'],
            allow_methods=['*'],
            allow_headers=['*'],
            allow_credentials=False,
            max_age=int(CORS_MAX_AGE.total_seconds()),
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        path: str = get_request().url.path
        app = (
            self.cors  #
            if (path.startswith('/api/') and not path.startswith('/api/web/'))
            else self.app
        )
        return await app(scope, receive, send)
