import logging
from urllib.parse import urlsplit

import cython
from starlette import status
from starlette.responses import RedirectResponse

from app.middlewares.request_context_middleware import get_request


@cython.cfunc
def _get_redirect_url() -> str:
    """
    Get the redirect URL from the referrer header.

    If the referrer is missing or is in a different domain, return '/'.
    """

    request = get_request()
    referer = request.headers.get('Referer')

    if referer is None:
        return '/'

    # check if the referer is the same as the current host
    parts = urlsplit(referer, allow_fragments=False)

    referer_hostname = parts.hostname
    request_hostname = request.url.hostname

    if referer_hostname != request_hostname:
        logging.debug('Referrer hostname mismatch (%r != %r)', referer_hostname, request_hostname)
        return '/'

    return referer


def get_redirect_response() -> RedirectResponse:
    """
    Get a redirect response, respecting the referrer header.
    """

    return RedirectResponse(_get_redirect_url(), status.HTTP_303_SEE_OTHER)
