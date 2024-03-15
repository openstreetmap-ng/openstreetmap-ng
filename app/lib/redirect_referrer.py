import logging
from urllib.parse import unquote_plus, urlsplit

import cython
from starlette import status
from starlette.responses import RedirectResponse

from app.middlewares.request_context_middleware import get_request


@cython.cfunc
def _process_referrer(referrer: str):
    """
    Process the referrer value.

    Returns None if the referrer is missing or is in a different domain.
    """

    if not referrer:
        return None

    # return relative values as-is
    if referrer[0] == '/':
        return referrer

    # otherwise, validate the referrer hostname
    parts = urlsplit(referrer, allow_fragments=False)

    referrer_hostname = parts.hostname
    request_hostname = get_request().url.hostname

    if referrer_hostname != request_hostname:
        logging.debug('Referrer hostname mismatch (%r != %r)', referrer_hostname, request_hostname)
        return None

    return referrer


@cython.cfunc
def _redirect_url() -> str:
    """
    Get the redirect URL from the request referrer.

    If the referrer is missing or is in a different domain, return '/'.
    """

    request = get_request()

    # referrer as a query parameter
    referrer = request.query_params.get('referer')
    if referrer is not None:
        processed = _process_referrer(unquote_plus(referrer))
        if processed is not None:
            return processed

    # referrer as a header
    referrer = request.headers.get('Referer')
    if referrer is not None:
        processed = _process_referrer(referrer)
        if processed is not None:
            return processed

    return '/'


def redirect_referrer() -> RedirectResponse:
    """
    Get a redirect response, respecting the referrer header.
    """

    return RedirectResponse(_redirect_url(), status.HTTP_303_SEE_OTHER)
