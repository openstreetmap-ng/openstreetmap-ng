from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import APP_URL, ID_URL, RAPID_URL, SENTRY_DSN, TEST_ENV, VERSION
from app.limits import HSTS_MAX_AGE

# Please keep it CSP version 2-compatible for the time being.
CSP_HEADER = '; '.join(
    filter(
        None,
        (
            "default-src 'self'",
            "script-src 'self' https://matomo.monicz.dev/matomo.js",
            'child-src blob:',  # TODO: worker-src in CSP 3
            'img-src * data:',
            'connect-src *',
            f'frame-src {" ".join({ID_URL, RAPID_URL})}',
            f'frame-ancestors {APP_URL}',
            (f'report-uri {SENTRY_DSN}' if SENTRY_DSN else None),
        ),
    )
)

_HSTS_HEADER = f'max-age={int(HSTS_MAX_AGE.total_seconds())}; includeSubDomains; preload'


class DefaultHeadersMiddleware:
    """Add default headers to responses."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(raw=message['headers'])
                headers.setdefault('Content-Security-Policy', CSP_HEADER)
                headers['Strict-Transport-Security'] = _HSTS_HEADER

                if TEST_ENV:
                    headers['X-Version'] = VERSION

            return await send(message)

        return await self.app(scope, receive, wrapper)
