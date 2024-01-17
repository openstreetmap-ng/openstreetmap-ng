import logging
import re
from collections.abc import Sequence
from functools import lru_cache

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import DEFAULT_LANGUAGE
from app.lib_cython.auth_context import auth_user
from app.lib_cython.locale import normalize_locale_case
from app.lib_cython.translation import translation_context
from app.limits import LANGUAGE_CODE_MAX_LENGTH

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Language#language
# limit to matches only supported by our translation files: config/locale
_accept_language_re = re.compile(r'(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{1,8})?|\*)(?:;q=(?P<q>[0-9.]+))?')


# TODO: is cache any good here?
@lru_cache(maxsize=128)
def _parse_accept_language(accept_language: str) -> Sequence[str]:
    """
    Parse the accept language header.

    Asterisk (*) is replaced with the default language.

    Returns a tuple of the languages, from most to least preferred.

    >>> _parse_accept_language('en-US,pl;q=0.8,es;q=0.9,*;q=0.5')
    ('en-US', 'es', 'pl', 'en')
    """

    # small optimization
    if not accept_language:
        return (DEFAULT_LANGUAGE,)

    temp: list[tuple[float, str]] = []

    # process accept language codes
    for match in _accept_language_re.finditer(accept_language):
        lang = match['lang']
        q = match['q']

        # skip weird accept language codes
        if (lang_len := len(lang)) > LANGUAGE_CODE_MAX_LENGTH:
            logging.debug('Accept language code is too long %d', lang_len)
            continue

        # replace asterisk with default language
        if lang == '*':
            lang = DEFAULT_LANGUAGE
        # normalize language case and check if it's supported
        else:
            try:
                lang = normalize_locale_case(lang, raise_on_not_found=True)
            except KeyError:
                logging.debug('Unknown accept language %r', lang)
                continue

        # parse q-factor
        if q is None:
            q = 1
        else:
            try:
                q = float(q)
            except ValueError:
                logging.debug('Invalid accept language q-factor %r', q)
                continue

        temp.append((q, lang))

    # sort by q-factor, descending
    temp.sort(reverse=True)

    return tuple(lang for _, lang in temp)


class TranslationMiddleware(BaseHTTPMiddleware):
    """
    Wrap request in translation context.
    """

    async def dispatch(self, request: Request, call_next):
        # check user's preferred languages before parsing the accept language header
        if (user := auth_user()) and user.languages:
            languages = user.languages
        else:
            accept_language = request.headers.get('accept-language', '')
            languages = _parse_accept_language(accept_language)

        with translation_context(languages):
            return await call_next(request)
