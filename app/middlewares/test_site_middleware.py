from fastapi.responses import RedirectResponse
from starlette import status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import APP_URL
from app.middlewares.request_context_middleware import get_request
from app.utils import extend_query_params


class TestSiteMiddleware:
    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        _app_prefix=APP_URL + '/',
    ) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        req = get_request()
        if (
            req.method != 'GET'
            or req.cookies.get('test_site_acknowledged') is not None
            or not str(req.url).startswith(_app_prefix)
            or req.url.path.startswith(('/test-site', '/static', '/api'))
        ):
            return await self.app(scope, receive, send)

        return await RedirectResponse(
            extend_query_params(
                '/test-site', {'referer': f'{req.url.path}?{req.url.query}'}
            ),
            status.HTTP_303_SEE_OTHER,
        )(scope, receive, send)
