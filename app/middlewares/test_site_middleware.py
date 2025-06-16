from fastapi.responses import RedirectResponse
from starlette import status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.middlewares.request_context_middleware import get_request
from app.utils import extend_query_params


class TestSiteMiddleware:
    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        request = get_request()
        if (
            request.method != 'GET'
            or request.cookies.get('test_site_acknowledged') is not None
            or request.url.path.startswith(('/test', '/static'))
        ):
            return await self.app(scope, receive, send)

        return await RedirectResponse(
            extend_query_params(
                '/test', {'referer': f'{request.url.path}?{request.url.query}'}
            ),
            status.HTTP_303_SEE_OTHER,
        )(scope, receive, send)
