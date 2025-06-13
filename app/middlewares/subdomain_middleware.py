from fastapi import Response
from fastapi.responses import RedirectResponse
from starlette import status
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import API_URL, APP_URL, ID_URL, RAPID_URL
from app.middlewares.request_context_middleware import get_request


class SubdomainMiddleware:
    """
    Subdomain-based routing and path restriction middleware.

    Implements routing based on configured URLs:
    - Redirects /id* and /rapid* paths from main domain to specialized domains when configured
    - Restricts specialized domains to only serve their specific content paths
    - Returns 404 for URLs that don't match any configured domain
    """

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
        _api_prefix=API_URL + '/',
        _id_prefix=ID_URL + '/',
        _rapid_prefix=RAPID_URL + '/',
    ) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        request = get_request()
        url = str(request.url)
        path: str = request.url.path

        # Handle main domain (APP_URL) redirects
        if url.startswith(_app_prefix):
            # Redirect /id* paths to ID_URL if configured
            if path.startswith('/id') and ID_URL != APP_URL:
                return await Response(
                    None,
                    status.HTTP_301_MOVED_PERMANENTLY,
                    headers={'Location': f'{ID_URL}{path}?{request.url.query}'},
                )(scope, receive, send)

            # Redirect /rapid* paths to RAPID_URL if configured
            if path.startswith('/rapid') and RAPID_URL != APP_URL:
                return await Response(
                    None,
                    status.HTTP_301_MOVED_PERMANENTLY,
                    headers={'Location': f'{RAPID_URL}{path}?{request.url.query}'},
                )(scope, receive, send)

        # Handle API domain (API_URL) path restrictions
        elif url.startswith(_api_prefix):
            if not path.startswith('/api/') or path.startswith('/api/web/'):
                return await Response(None, status.HTTP_404_NOT_FOUND)(
                    scope, receive, send
                )

        # Handle iD domain (ID_URL) path restrictions
        elif url.startswith(_id_prefix):
            if path == '/':
                return await RedirectResponse(
                    APP_URL, status.HTTP_301_MOVED_PERMANENTLY
                )(scope, receive, send)
            if not path.startswith(('/static', '/id')):
                return await Response(None, status.HTTP_404_NOT_FOUND)(
                    scope, receive, send
                )

        # Handle Rapid domain (RAPID_URL) path restrictions
        elif url.startswith(_rapid_prefix):
            if path == '/':
                return await RedirectResponse(
                    APP_URL, status.HTTP_301_MOVED_PERMANENTLY
                )(scope, receive, send)
            if not path.startswith(('/static', '/rapid')):
                return await Response(None, status.HTTP_404_NOT_FOUND)(
                    scope, receive, send
                )

        # Fail if request URL doesn't match any configured URLs
        else:
            return await Response(
                f'Request URL {url} does not match any configured URLs',
                status.HTTP_404_NOT_FOUND,
            )(scope, receive, send)

        return await self.app(scope, receive, send)
