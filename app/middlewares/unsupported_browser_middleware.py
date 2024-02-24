import logging

from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.lib.render_response import render_response
from app.lib.user_agent_analyzer import is_browser_supported


class UnsupportedBrowserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        user_agent = request.headers.get('User-Agent')

        if is_browser_supported(user_agent):
            return response

        # capture successful html responses
        if (
            request.method == 'GET'
            and response.status_code == 200  # OK
            and response.headers.get('Content-Type').startswith('text/html')
            and not request.session.get('unsupported_browser_override')
        ):
            logging.debug('Unsupported browser detected, rewriting response')
            response = render_response('unsupported_browser.jinja2')
            response.status_code = status.HTTP_501_NOT_IMPLEMENTED
            return response

        # pass through all other responses (failures, non-html, etc.)
        return response
